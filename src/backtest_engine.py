import pandas as pd
import numpy as np
import logging
import matplotlib.pyplot as plt
import sqlite3
from src.data_manager import DataManager

logger = logging.getLogger("PYL.backtest_engine")

class BacktestEngine:
    def __init__(self):
        self.db = DataManager()
        
    def _get_universe(self):
        """
        获取全市场股票列表 
        🔥 关键修复：必须严格剔除宏观因子和非股票资产，
        否则会导致数据对齐时长度被切短，甚至归零。
        """
        try:
            with sqlite3.connect(self.db.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT DISTINCT ticker FROM stock_prices")
                
                # 1. 基础排除 (指数 ETF 等)
                basic_exclude = ['SPY', 'QQQ', 'TLT', 'GLD', 'IWM', 'USDOLLAR', '^GSPC', '^VIX']
                
                # 2. 🔥 宏观因子排除
                # 必须把它们拉黑，否则回测引擎会试图交易“CPI通胀率”，导致逻辑崩溃
                macro_exclude = [
                    'DGS10', 'T5YIE', 'T10Y2Y', 'BAMLC0A0CM', # 利率/信用
                    'VIXCLS', 'DCOILWTICO', 'DTWEXBGS',       # VIX/油/美元
                    'CPIAUCSL', 'M2SL', 'UNRATE'              # 其他可能的宏观数据
                ]
                
                exclude = basic_exclude + macro_exclude
                
                all_tickers = [row[0] for row in cursor.fetchall()]
                
                # 过滤
                clean_list = [t for t in all_tickers if t not in exclude]
                
                # 3. 简单的日志，让你知道回测到底在跑谁
                logger.info(f"Scanning Universe: Found {len(all_tickers)} raw, {len(clean_list)} valid stocks.")
                return clean_list
        except Exception as e:
            logger.error(f"Failed to get universe: {e}")
            return ['AAPL', 'MSFT'] # 保底

    def run_backtest(self, strategy_name="Trend_Following_Plus", top_n=5, min_history_days=252, mom_window=126):
        """
        全功能回测引擎
        """
        universe = self._get_universe()
        if not universe:
            logger.error("❌ Universe is empty! Check your exclusion list.")
            return None

        logger.info(f"🔍 [Universe Scan] Preparing to backtest {len(universe)} stocks...")
        
        # 1. 获取全量数据 (价格 + SPY基准)
        # 注意：这里我们明确只取 universe + SPY，不取别的
        raw_df = self.db.get_aligned_data(universe + ['SPY'])
        
        if raw_df is None or raw_df.empty: 
            logger.warning("❌ No data found for backtest.")
            return None
            
        # ==========================================
        # 🛡️ 步骤 1: 历史长度清洗
        # ==========================================
        valid_cols = []
        dropped_count = 0
        
        for col in raw_df.columns:
            if col == 'SPY': 
                valid_cols.append(col)
                continue
            
            # 统计非空交易日数量
            count = raw_df[col].count()
            if count >= min_history_days:
                valid_cols.append(col)
            else:
                dropped_count += 1
                # 调试打印，看看到底是谁被剔除了
                # logger.debug(f"Dropped {col}: {count} days < {min_history_days}")
        
        logger.info(f"📉 [Filtering] Dropped {dropped_count} short-history stocks. Retaining {len(valid_cols)} candidates.")
        
        # 重新切片并去空
        df_clean = raw_df[valid_cols].dropna()
        
        if df_clean.empty or len(df_clean) < 126: # 至少要有半年的数据才能算动量
            logger.warning(f"❌ Data became empty after alignment. Overlap length: {len(df_clean)}")
            return None

        # ==========================================
        # ⚙️ 步骤 2: 数据准备
        # ==========================================
        # 提取个股价格 (排除因子列和 SPY)
        price_cols = [c for c in df_clean.columns if c not in ['smb', 'hml', 'mom', 'mkt', 'SPY']]
        prices = df_clean[price_cols]
        
        if prices.empty:
            logger.warning("❌ No stock price columns left.")
            return None

        # 提取基准 (SPY)
        if 'SPY' in df_clean.columns:
            spy = df_clean['SPY']
            spy_ret = spy.pct_change().fillna(0)
        else:
            logger.warning("⚠️ SPY not found. Market Filter disabled.")
            spy = pd.Series(100, index=prices.index)
            spy_ret = pd.Series(0, index=prices.index)

        logger.info(f"🚀 [Start Backtest] Range: {prices.index[0].date()} -> {prices.index[-1].date()} ({len(prices)} days)")

        # ==========================================
        # 🚦 步骤 3: 大盘风控 (MA200)
        # ==========================================
        spy_ma200 = spy.rolling(window=200).mean()
        # 昨天的收盘价 > 昨天的200日均线 = 今天敢买
        market_signal = (spy > spy_ma200).astype(int).shift(1).fillna(1)
        
        # ==========================================
        # 📈 步骤 4: 选股策略 (Momentum)
        # ==========================================
        momentum = prices.pct_change(mom_window)
        ranks = momentum.rank(axis=1, ascending=False)
        raw_signals = (ranks <= top_n).astype(int)
        
        # 权重计算 (等权)
        row_sums = raw_signals.sum(axis=1)
        raw_weights = raw_signals.div(row_sums, axis=0).fillna(0)
        
        # ==========================================
        # ⚖️ 步骤 5: 交易执行 (含大盘风控)
        # ==========================================
        # 如果 Market=0，仓位全平
        final_weights = raw_weights.mul(market_signal, axis=0)
        
        stock_daily_ret = prices.pct_change().fillna(0)
        
        # 策略收益 = 昨天权重 * 今天个股涨幅
        gross_strat_ret = (final_weights.shift(1) * stock_daily_ret).sum(axis=1)
        
        # 交易成本 (Impact Cost + Commission)
        turnover = abs(final_weights - final_weights.shift(1)).fillna(0).sum(axis=1)
        cost_rate = 0.001 # 万10
        txn_costs = turnover * cost_rate
        
        net_strat_ret = gross_strat_ret - txn_costs
        
        # ==========================================
        # 📊 步骤 6: 绩效统计
        # ==========================================
        cum_strat = (1 + net_strat_ret).cumprod() * 100
        cum_bench = (1 + spy_ret).cumprod() * 100
        
        total_days = (cum_strat.index[-1] - cum_strat.index[0]).days
        years = total_days / 365.25
        total_return = cum_strat.iloc[-1] / 100 - 1
        ann_ret = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0
        
        ann_vol = net_strat_ret.std() * np.sqrt(252)
        rf = 0.04 
        excess_ret = net_strat_ret - (rf / 252)
        sharpe = (excess_ret.mean() / excess_ret.std()) * np.sqrt(252) if excess_ret.std() > 0 else 0
        
        roll_max = cum_strat.cummax()
        drawdown = (cum_strat - roll_max) / roll_max
        max_dd = drawdown.min()
        
        # 胜率
        win_days = len(net_strat_ret[net_strat_ret > 0])
        trade_days = len(net_strat_ret[net_strat_ret != 0])
        win_rate = win_days / trade_days if trade_days > 0 else 0

        metrics = {
            'ann_ret': ann_ret,
            'sharpe': sharpe,
            'max_dd': max_dd,
            'win_rate': win_rate
        }
        
        logger.info(f"🏁 [Result] CAGR: {ann_ret:.1%} | Sharpe: {sharpe:.2f}")
        return self._plot(cum_strat, cum_bench, drawdown, strategy_name, len(price_cols), metrics)

    def _plot(self, strat, bench, drawdown, name, count, metrics):
        try:
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), gridspec_kw={'height_ratios': [3, 1]}, sharex=True)
            
            ax1.plot(strat.index, strat.values, label='Strategy (Trend + Market Filter)', linewidth=2, color='#2980b9')
            ax1.plot(bench.index, bench.values, label='S&P 500', linestyle='--', color='gray', alpha=0.7)
            
            ax1.fill_between(strat.index, strat.values, bench.values, where=(strat.values >= bench.values), color='green', alpha=0.1)
            ax1.fill_between(strat.index, strat.values, bench.values, where=(strat.values < bench.values), color='red', alpha=0.1)

            title_str = (f"{name} (Pool: {count} Stocks)\n"
                         f"CAGR: {metrics['ann_ret']:.1%} | Sharpe: {metrics['sharpe']:.2f} | "
                         f"MaxDD: {metrics['max_dd']:.1%} | WinRate: {metrics['win_rate']:.1%}")
            ax1.set_title(title_str, fontsize=11, fontweight='bold')
            ax1.set_ylabel("Net Asset Value")
            ax1.legend(loc='upper left')
            ax1.grid(True, alpha=0.3)
            
            ax2.plot(drawdown.index, drawdown.values, label='Drawdown', color='#c0392b', linewidth=1)
            ax2.fill_between(drawdown.index, drawdown.values, 0, color='#c0392b', alpha=0.3)
            ax2.set_ylabel("Drawdown")
            ax2.set_ylim([min(metrics['max_dd']*1.1, -0.2), 0.05])
            ax2.grid(True, alpha=0.3)
            
            plt.tight_layout()
            return fig
        except Exception as e:
            logger.error(f"Plotting failed: {e}")
            return None