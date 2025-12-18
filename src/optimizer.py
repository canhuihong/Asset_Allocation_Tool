import pandas as pd
import numpy as np
import logging
import scipy.optimize as sco
import matplotlib.pyplot as plt
import sqlite3
import pandas_datareader.data as web
import datetime
import random
from src.data_manager import DataManager

logger = logging.getLogger("PYL.optimizer")

class PortfolioOptimizer:
    def __init__(self):
        self.db = DataManager()

    def _get_all_tickers(self):
        """
        获取全市场股票池，执行严格的排除名单。
        """
        try:
            with sqlite3.connect(self.db.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT DISTINCT ticker FROM stock_prices")
                tickers = [row[0] for row in cursor.fetchall()]
            
            # 完整的排除列表 (Full Exclude List)
            exclude = [
                'SPY', 'QQQ', 'TLT', 'GLD', 'IWM', 'USDOLLAR', '^GSPC', '^VIX', '^IXIC',
                'IVV', 'VOO', 'AGG', 'BND', 'LQD', 'HYG', 'EEM', 'EFA', 'SLV', 'USO',
                'SHY', 'IEF', 'TIP', 'VNQ', 'XLK', 'XLF', 'XLV', 'XLE', 'XLY', 'XLP'
            ]
            return [t for t in tickers if t not in exclude]
        except Exception as e:
            logger.error(f"Error fetching tickers from DB: {e}")
            return ['AAPL', 'MSFT', 'NVDA', 'JPM'] 

    def _get_risk_free_rate(self):
        """
        动态获取无风险利率 (3个月美债 DGS3MO)。
        """
        default_rf = 0.04
        try:
            end = datetime.datetime.now()
            start = end - datetime.timedelta(days=20)
            df = web.DataReader('DGS3MO', 'fred', start, end)
            if df is not None and not df.empty:
                rf = df['DGS3MO'].dropna().iloc[-1] / 100.0
                logger.info(f"✅ Fetched dynamic Risk-Free Rate (DGS3MO): {rf:.2%}")
                return rf
            else:
                return default_rf
        except: return default_rf

    def optimize(self):
        logger.info("Initializing Full-Market Optimization (Max Features)...")
        
        # 1. 获取股票池
        all_tickers = self._get_all_tickers()
        # 限制 50 只以保证计算边界线时不卡死
        if len(all_tickers) > 50:
            target_tickers = random.sample(all_tickers, 50)
            logger.info(f"Selecting 50 random stocks from {len(all_tickers)} available.")
        else:
            target_tickers = all_tickers
            
        # 2. 获取数据
        tickers_to_fetch = target_tickers + ['SPY'] if 'SPY' not in target_tickers else target_tickers
        raw_df = self.db.get_aligned_data(tickers_to_fetch)
        
        if raw_df is None or raw_df.empty:
            logger.error("❌ Optimization failed: No data.")
            return None, {}
            
        rf_rate = self._get_risk_free_rate()
            
        # 3. 数据准备
        price_cols = [c for c in raw_df.columns if c not in ['smb', 'hml', 'mom', 'mkt', 'SPY']]
        prices = raw_df[price_cols]
        returns = prices.pct_change().dropna()
        
        if returns.shape[1] < 2 or len(returns) < 60: 
            logger.error("❌ Optimization failed: Not enough data.")
            return None, {}
        
        mean_returns = returns.mean() * 252
        cov_matrix = returns.cov() * 252
        num_assets = len(mean_returns)
        asset_names = returns.columns
        
        # 4. 定义优化目标函数
        def portfolio_volatility(weights):
            return np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
            
        def neg_sharpe_ratio(weights):
            p_ret = np.sum(weights * mean_returns)
            p_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
            return -(p_ret - rf_rate) / (p_vol + 1e-9)

        constraints = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1})
        bounds = tuple((0.0, 1.0) for _ in range(num_assets))
        init_guess = num_assets * [1. / num_assets,]
        
        star_points = []
        portfolios = {} 

        # 变量用于画线
        min_vol_val = 0
        max_ret_val = 0

        # --- A. 求解最小波动 (Min Vol) ---
        try:
            res_mv = sco.minimize(portfolio_volatility, init_guess, method='SLSQP', bounds=bounds, constraints=constraints)
            if res_mv.success:
                mv_vol = res_mv.fun
                mv_ret = np.sum(res_mv.x * mean_returns)
                min_vol_val = mv_vol # 记录用于画线
                
                star_points.append((mv_vol, mv_ret, "Min Volatility", "gold"))
                logger.info(f"✅ [Min Vol] Solved! Vol: {mv_vol:.1%}")
                
                df_mv = pd.DataFrame({'Ticker': asset_names, 'Weight': res_mv.x}).sort_values('Weight', ascending=False)
                portfolios['weights_min_vol.csv'] = df_mv[df_mv['Weight'] > 0.0001]
        except Exception as e: logger.error(f"Min Vol failed: {e}")

        # --- B. 求解最大夏普 (Max Sharpe) ---
        try:
            res_ms = sco.minimize(neg_sharpe_ratio, init_guess, method='SLSQP', bounds=bounds, constraints=constraints)
            if res_ms.success:
                ms_vol = np.sqrt(np.dot(res_ms.x.T, np.dot(cov_matrix, res_ms.x)))
                ms_ret = np.sum(res_ms.x * mean_returns)
                max_ret_val = ms_ret # 记录用于画线
                
                star_points.append((ms_vol, ms_ret, "Max Sharpe", "red"))
                logger.info(f"✅ [Max Sharpe] Solved! Sharpe: {(ms_ret-rf_rate)/ms_vol:.2f}")
                
                df_ms = pd.DataFrame({'Ticker': asset_names, 'Weight': res_ms.x}).sort_values('Weight', ascending=False)
                portfolios['weights_max_sharpe.csv'] = df_ms[df_ms['Weight'] > 0.0001]
        except Exception as e: logger.error(f"Max Sharpe failed: {e}")

        # --- C. 保底机制 ---
        if not portfolios:
            df_eq = pd.DataFrame({'Ticker': asset_names, 'Weight': [1.0/num_assets]*num_assets})
            portfolios['weights_equal_backup.csv'] = df_eq

        # ==========================================
        # 🟢 D. 生成有效前沿曲线 (Efficient Frontier Line)
        # 这就是之前被缩掉的关键部分！
        # ==========================================
        frontier_x = []
        frontier_y = []
        
        if min_vol_val > 0 and max_ret_val > 0:
            logger.info("📐 Calculating Efficient Frontier Curve (20 points)...")
            # 在最小波动和最大收益之间插值 20 个点
            target_returns = np.linspace(min_vol_val, max_ret_val * 1.2, 20) # 用收益率更合理，这里简化用线性插值
            # 修正：应该在收益率区间上插值
            min_ret = star_points[0][1] if star_points else 0
            max_ret = max(p[1] for p in star_points) if star_points else 0.5
            target_returns = np.linspace(min_ret, max_ret * 1.1, 20)

            for trets in target_returns:
                # 约束：权重和=1 且 收益率=目标值
                cons = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1},
                        {'type': 'eq', 'fun': lambda x: np.sum(x * mean_returns) - trets})
                
                try:
                    res = sco.minimize(portfolio_volatility, init_guess, method='SLSQP', bounds=bounds, constraints=cons)
                    if res.success:
                        frontier_x.append(res.fun)   # Volatility
                        frontier_y.append(trets)     # Return
                except: pass

        # ==========================================
        # E. 蒙特卡洛模拟 (5000次)
        # ==========================================
        logger.info("🎲 Running Monte Carlo (5000 iters)...")
        results = np.zeros((3, 5000))
        for i in range(5000):
            w = np.random.random(num_assets); w /= np.sum(w)
            p_std = np.sqrt(np.dot(w.T, np.dot(cov_matrix, w)))
            p_ret = np.sum(w * mean_returns)
            results[:,i] = [p_std, p_ret, (p_ret-rf_rate)/(p_std+1e-9)]
            
        # 传入所有数据进行绘图
        fig = self._plot(results, star_points, frontier_x, frontier_y, len(target_tickers), rf_rate)
        
        return fig, portfolios

    def _plot(self, results, star_points, frontier_x, frontier_y, num_stocks, rf_rate):
        try:
            fig, ax = plt.subplots(figsize=(10, 6))
            
            # 1. 散点云 (Monte Carlo)
            sc = ax.scatter(results[0,:], results[1,:], c=results[2,:], 
                           cmap='viridis', s=10, alpha=0.4, label='Random Portfolios')
            cbar = plt.colorbar(sc)
            cbar.set_label(f'Sharpe Ratio (Rf={rf_rate:.1%})', rotation=270, labelpad=15)
            
            # 2. 🟢 曲线 (Frontier Line)
            # 如果算出来了，画一条黑色虚线
            if len(frontier_x) > 1:
                ax.plot(frontier_x, frontier_y, 'k--', linewidth=2.5, label='Efficient Frontier')
            
            # 3. 特殊点 (MinVol, MaxSharpe)
            for (vol, ret, label, color) in star_points:
                ax.scatter(vol, ret, marker='*', color=color, s=300, 
                          edgecolors='black', linewidth=1.5, label=label, zorder=10)
            
            ax.set_title(f'Efficient Frontier (Universe: {num_stocks} Stocks)', fontsize=12, fontweight='bold')
            ax.set_ylabel('Annualized Expected Return')
            ax.set_xlabel('Annualized Volatility (Risk)')
            ax.legend(loc='upper left')
            ax.grid(True, alpha=0.3)
            
            return fig
        except Exception as e: 
            logger.error(f"Plotting failed: {e}")
            return None