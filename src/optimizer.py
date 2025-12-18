import pandas as pd
import numpy as np
import logging
import scipy.optimize as sco
import matplotlib.pyplot as plt
import pandas_datareader.data as web
import datetime
import random
from src.data_manager import DataManager
from src.config import FULL_BLOCKLIST # ✅ 引入统一配置

logger = logging.getLogger("PYL.optimizer")

class PortfolioOptimizer:
    def __init__(self):
        self.db = DataManager()

    def _get_valid_universe(self):
        """
        获取全市场股票池，并应用 Config 中的排除名单。
        ✅ 逻辑更新：不再直接操作 SQL，而是调用 DataManager 接口
        """
        try:
            # 1. 从 DB 获取所有 Ticker
            raw_tickers = self.db.get_all_tickers_in_db()
            
            # 2. 应用统一黑名单进行过滤
            valid_tickers = [t for t in raw_tickers if t not in FULL_BLOCKLIST]
            
            logger.info(f"Optimizer Universe: {len(raw_tickers)} raw -> {len(valid_tickers)} cleaned.")
            return valid_tickers
        except Exception as e:
            logger.error(f"Error fetching tickers: {e}")
            # 保底列表
            return ['AAPL', 'MSFT', 'NVDA', 'JPM'] 

    def _get_risk_free_rate(self):
        """动态获取无风险利率 (3个月美债 DGS3MO)"""
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
        
        # 1. 获取清洗后的股票池
        all_tickers = self._get_valid_universe()
        
        # 限制 50 只以保证计算速度 (可根据机器性能调整)
        if len(all_tickers) > 50:
            target_tickers = random.sample(all_tickers, 50)
            logger.info(f"Selecting 50 random stocks from {len(all_tickers)} available.")
        else:
            target_tickers = all_tickers
            
        # 2. 获取数据 (需包含 SPY 作为基准参考，即便不在目标池中)
        tickers_to_fetch = list(set(target_tickers + ['SPY']))
        raw_df = self.db.get_aligned_data(tickers_to_fetch)
        
        if raw_df is None or raw_df.empty:
            logger.error("❌ Optimization failed: No data.")
            return None, {}
            
        rf_rate = self._get_risk_free_rate()
            
        # 3. 数据准备 (仅保留目标池的股票价格)
        # 过滤掉因子列和不在 target_tickers 里的列
        valid_cols = [c for c in raw_df.columns if c in target_tickers]
        prices = raw_df[valid_cols]
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
        min_vol_val = 0
        max_ret_val = 0

        # --- A. 求解最小波动 (Min Vol) ---
        try:
            res_mv = sco.minimize(portfolio_volatility, init_guess, method='SLSQP', bounds=bounds, constraints=constraints)
            if res_mv.success:
                mv_vol = res_mv.fun
                mv_ret = np.sum(res_mv.x * mean_returns)
                min_vol_val = mv_vol
                
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
                max_ret_val = ms_ret
                
                star_points.append((ms_vol, ms_ret, "Max Sharpe", "red"))
                logger.info(f"✅ [Max Sharpe] Solved! Sharpe: {(ms_ret-rf_rate)/ms_vol:.2f}")
                
                df_ms = pd.DataFrame({'Ticker': asset_names, 'Weight': res_ms.x}).sort_values('Weight', ascending=False)
                portfolios['weights_max_sharpe.csv'] = df_ms[df_ms['Weight'] > 0.0001]
        except Exception as e: logger.error(f"Max Sharpe failed: {e}")

        # --- C. 保底机制 ---
        if not portfolios:
            df_eq = pd.DataFrame({'Ticker': asset_names, 'Weight': [1.0/num_assets]*num_assets})
            portfolios['weights_equal_backup.csv'] = df_eq

        # --- D. 生成有效前沿曲线 (Efficient Frontier Line) ---
        frontier_x = []
        frontier_y = []
        
        if min_vol_val > 0 and max_ret_val > 0:
            logger.info("📐 Calculating Efficient Frontier Curve (20 points)...")
            min_ret = star_points[0][1] if star_points else 0
            max_ret = max(p[1] for p in star_points) if star_points else 0.5
            target_returns = np.linspace(min_ret, max_ret * 1.1, 20)

            for trets in target_returns:
                cons = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1},
                        {'type': 'eq', 'fun': lambda x: np.sum(x * mean_returns) - trets})
                try:
                    res = sco.minimize(portfolio_volatility, init_guess, method='SLSQP', bounds=bounds, constraints=cons)
                    if res.success:
                        frontier_x.append(res.fun)   # Volatility
                        frontier_y.append(trets)     # Return
                except: pass

        # --- E. 蒙特卡洛模拟 (5000次) ---
        logger.info("🎲 Running Monte Carlo (5000 iters)...")
        results = np.zeros((3, 5000))
        for i in range(5000):
            w = np.random.random(num_assets); w /= np.sum(w)
            p_std = np.sqrt(np.dot(w.T, np.dot(cov_matrix, w)))
            p_ret = np.sum(w * mean_returns)
            results[:,i] = [p_std, p_ret, (p_ret-rf_rate)/(p_std+1e-9)]
            
        fig = self._plot(results, star_points, frontier_x, frontier_y, len(target_tickers), rf_rate)
        
        return fig, portfolios

    def _plot(self, results, star_points, frontier_x, frontier_y, num_stocks, rf_rate):
        try:
            fig, ax = plt.subplots(figsize=(10, 6))
            
            # 1. 散点云
            sc = ax.scatter(results[0,:], results[1,:], c=results[2,:], 
                           cmap='viridis', s=10, alpha=0.4, label='Random Portfolios')
            cbar = plt.colorbar(sc)
            cbar.set_label(f'Sharpe Ratio (Rf={rf_rate:.1%})', rotation=270, labelpad=15)
            
            # 2. 曲线
            if len(frontier_x) > 1:
                ax.plot(frontier_x, frontier_y, 'k--', linewidth=2.5, label='Efficient Frontier')
            
            # 3. 特殊点
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