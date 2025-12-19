import pandas as pd
import numpy as np
import yfinance as yf
import statsmodels.api as sm
import matplotlib.pyplot as plt
import logging
import time
from src.data_manager import DataManager
from src.config import IMAGES_DIR

logger = logging.getLogger("PYL.factor_engine")

class FactorEngine:
    def __init__(self):
        self.db = DataManager()
        # 定义因子构建的代理 ETF
        # 逻辑: 
        # SMB (规模) = 小盘股(IWM) - 大盘股(SPY)
        # HML (价值) = 价值股(VTV) - 成长股(VUG)
        # MOM (动量) = 动量股(MTUM) - 市场(SPY) [注: MTUM历史较短，早期数据可能用SPY代替或截断]
        self.proxies = {
            'MKT': 'SPY',
            'SMALL': 'IWM',
            'LARGE': 'SPY',
            'VALUE': 'VTV',
            'GROWTH': 'VUG',
            'MOMENTUM': 'MTUM'
        }

    def calculate_factors(self, start_date="2015-01-01"):
        """
        构建 Fama-French 代理因子序列
        """
        logger.info("⚙️ Building Micro Factors using ETF Proxies...")
        
        tickers = list(self.proxies.values())
        try:
            # 1. 临时下载代理 ETF 数据 (不存入主数据库，以免污染个股池)
            # 使用 auto_adjust=True 确保拿到复权价格
            data = yf.download(tickers, start=start_date, progress=False, auto_adjust=True)['Close']
            
            if data is None or data.empty:
                logger.error("❌ Failed to download proxy data.")
                return None
                
            # 2. 计算日收益率
            returns = data.pct_change().dropna()
            
            # 3. 构建因子 (Factor Construction)
            factors = pd.DataFrame(index=returns.index)
            
            # Market Factor (MKT)
            factors['mkt'] = returns[self.proxies['MKT']]
            
            # Size Factor (SMB): Small Caps - Large Caps
            factors['smb'] = returns[self.proxies['SMALL']] - returns[self.proxies['LARGE']]
            
            # Value Factor (HML): Value - Growth
            factors['hml'] = returns[self.proxies['VALUE']] - returns[self.proxies['GROWTH']]
            
            # Momentum Factor (MOM): Momentum - Market
            # 注意: MTUM 可能数据较短，如果缺失则填充 0
            if self.proxies['MOMENTUM'] in returns.columns:
                factors['mom'] = returns[self.proxies['MOMENTUM']] - returns[self.proxies['MKT']]
            else:
                factors['mom'] = 0.0
                
            # 清洗空值
            factors = factors.dropna()
            
            logger.info(f"✅ Factors constructed: {len(factors)} days.")
            logger.info(f"   - MKT Ann Ret: {factors['mkt'].mean()*252:.1%}")
            logger.info(f"   - SMB Ann Ret: {factors['smb'].mean()*252:.1%}")
            
            return factors
            
        except Exception as e:
            logger.error(f"❌ Error constructing factors: {e}")
            return None

    def analyze_portfolio(self, portfolio_tickers, window=126):
        """
        对给定持仓进行因子归因分析 (Rolling Regression)
        """
        logger.info(f"🔎 Analyzing Portfolio Exposures: {portfolio_tickers}")
        
        # 1. 获取持仓数据
        df_port = self.db.get_aligned_data(portfolio_tickers)
        if df_port is None or df_port.empty:
            logger.warning("   - No portfolio data found.")
            return
            
        # 2. 获取因子数据 (从 DB 读取)
        # 注意: 这里假设 factors 表已经被 init_data.py 填充满了
        conn = self.db._get_conn()
        try:
            df_factors = pd.read_sql("SELECT * FROM factors", conn)
            df_factors['date'] = pd.to_datetime(df_factors['date'])
            df_factors.set_index('date', inplace=True)
        except:
            logger.warning("   - Factors not found in DB. Calculating on the fly...")
            df_factors = self.calculate_factors()
            
        if df_factors is None or df_factors.empty:
            return

        # 3. 对齐数据
        # 假设投资组合是等权持有的 (为了简化分析)
        # 过滤掉因子列，只留股票列
        stock_cols = [c for c in df_port.columns if c in portfolio_tickers]
        port_prices = df_port[stock_cols]
        port_ret = port_prices.pct_change().mean(axis=1).dropna() # 组合日收益率
        
        # 合并
        combined = pd.concat([port_ret, df_factors], axis=1).dropna()
        combined.columns = ['Portfolio', 'SMB', 'HML', 'MOM', 'MKT']
        
        if len(combined) < window:
            logger.warning("   - Not enough overlapping data for regression.")
            return

        # 4. 滚动回归 (Rolling Regression)
        betas = []
        dates = []
        
        # 使用 numpy 高速计算
        y = combined['Portfolio'].values
        X = combined[['MKT', 'SMB', 'HML', 'MOM']].values
        X = sm.add_constant(X) # 添加 Alpha 项
        
        for i in range(window, len(combined)):
            y_window = y[i-window:i]
            X_window = X[i-window:i]
            
            try:
                model = sm.OLS(y_window, X_window).fit()
                # model.params 顺序: const(Alpha), MKT, SMB, HML, MOM
                betas.append(model.params)
                dates.append(combined.index[i])
            except: pass
            
        if not betas:
            return

        # 5. 绘图
        df_betas = pd.DataFrame(betas, index=dates, columns=['Alpha', 'Beta_MKT', 'Beta_SMB', 'Beta_HML', 'Beta_MOM'])
        
        self._plot_attribution(df_betas, combined)
        
    def _plot_attribution(self, df_betas, combined):
        """绘制归因分析图"""
        try:
            fig, axes = plt.subplots(3, 1, figsize=(12, 12), sharex=True)
            
            # A. 市场 Beta
            axes[0].plot(df_betas.index, df_betas['Beta_MKT'], color='black', label='Market Beta')
            axes[0].axhline(1.0, linestyle='--', color='gray', alpha=0.5)
            axes[0].set_title('Market Exposure (Beta)')
            axes[0].legend(loc='upper left')
            
            # B. 风格因子 (SMB, HML, MOM)
            axes[1].plot(df_betas.index, df_betas['Beta_SMB'], label='Size (SMB)', alpha=0.8)
            axes[1].plot(df_betas.index, df_betas['Beta_HML'], label='Value (HML)', alpha=0.8)
            axes[1].plot(df_betas.index, df_betas['Beta_MOM'], label='Momentum (MOM)', alpha=0.8)
            axes[1].axhline(0, linestyle='--', color='black', alpha=0.3)
            axes[1].set_title('Style Factor Exposures')
            axes[1].legend(loc='upper left')
            
            # C. 滚动 Alpha (年化)
            ann_alpha = df_betas['Alpha'] * 252 * 100
            axes[2].fill_between(df_betas.index, ann_alpha, 0, where=(ann_alpha>=0), color='green', alpha=0.3)
            axes[2].fill_between(df_betas.index, ann_alpha, 0, where=(ann_alpha<0), color='red', alpha=0.3)
            axes[2].plot(df_betas.index, ann_alpha, color='darkgreen', linewidth=1)
            axes[2].set_title('Rolling Annualized Alpha (%)')
            
            plt.tight_layout()
            save_path = IMAGES_DIR / "factor_attribution.png"
            plt.savefig(save_path)
            logger.info(f"📸 Factor attribution plot saved: {save_path}")
            plt.close()
            
        except Exception as e:
            logger.error(f"Plotting failed: {e}")

if __name__ == "__main__":
    # 测试代码
    fe = FactorEngine()
    factors = fe.calculate_factors()
    if factors is not None:
        print(factors.tail())