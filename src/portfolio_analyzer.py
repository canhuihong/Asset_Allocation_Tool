import pandas as pd
import numpy as np
import logging
import statsmodels.api as sm
from statsmodels.regression.rolling import RollingOLS
import matplotlib.pyplot as plt
from src.data_manager import DataManager  # 引入新管家

logger = logging.getLogger("PYL.portfolio_analyzer")

class PortfolioAnalyzer:
    def __init__(self):
        # 初始化数据库连接
        self.db = DataManager()

    def analyze(self, portfolio_dict):
        logger.info("Analyzing portfolio (static) from Database...")
        
        # 1. 准备数据 (这是改动最大的地方，变得极简)
        df = self._prepare_data(portfolio_dict)
        
        if df is None or df.empty or len(df) < 30:
            logger.warning("❌ Insufficient data in DB for regression.")
            return None
        
        try:
            # 2. 确定回归因子 (数据库里有啥用啥)
            target_cols = ['Mkt']
            for col in ['SMB', 'HML', 'MOM']:
                if col in df.columns and df[col].sum() != 0:
                    target_cols.append(col)
            
            logger.info(f"Regression Features: {target_cols}")
            
            X = df[target_cols]
            X = sm.add_constant(X)
            Y = df['Port']
            
            # 3. 运行回归
            model = sm.OLS(Y, X).fit()
            
            # 4. 画图
            self._plot_cumulative_return(df)
            return  self._plot_static(model)
            
        except Exception as e:
            logger.error(f"Analysis failed: {e}", exc_info=True)
            return None

    def rolling_analyze(self, portfolio_dict, window=252):
        df = self._prepare_data(portfolio_dict)
        if df is None or df.empty or len(df) < window + 20: return None
        try:
            target_cols = ['Mkt']
            for col in ['SMB', 'HML', 'MOM']:
                if col in df.columns and df[col].sum() != 0:
                    target_cols.append(col)
                    
            X = df[target_cols]
            X = sm.add_constant(X)
            Y = df['Port']
            rols = RollingOLS(Y, X, window=window)
            rres = rols.fit()
            params = rres.params.copy()
            if 'const' in params.columns:
                params['const'] = params['const'] * 252
                params.rename(columns={'const': 'Annualized Alpha'}, inplace=True)
            return self._plot_rolling(params)
        except: return None

    def _prepare_data(self, portfolio_dict):
        """
        从数据库获取对齐好的数据，并计算收益率
        """
        tickers = list(portfolio_dict.keys())
        
        # 1. 直接问数据库要数据 (包含 持仓股票 + SPY + 因子)
        # 这一步会自动完成所有的 Date Join 和 补0 操作
        # SQL 已经在底层帮我们处理好了所有脏活
        required_tickers = tickers + ['SPY']
        raw_df = self.db.get_aligned_data(required_tickers)
        
        if raw_df is None or raw_df.empty:
            logger.warning("DB returned empty data. Did you run 'python init_data.py'?")
            return None

        # 2. 分离股价和因子
        # 假设 factor 列是 smb, hml, mom, mkt (小写)
        factor_cols = [c for c in raw_df.columns if c in ['smb', 'hml', 'mom', 'mkt']]
        price_cols = [c for c in raw_df.columns if c not in factor_cols]
        
        # 3. 计算收益率 (Prices -> Returns)
        prices = raw_df[price_cols]
        returns = prices.pct_change().dropna()
        
        if returns.empty: return None
        
        # 4. 构建组合收益率
        port_ret = pd.Series(0.0, index=returns.index)
        for t, w in portfolio_dict.items():
            if t in returns.columns:
                port_ret += returns[t] * w
        
        # 5. 组装最终 DataFrame
        # 注意：returns 的行数可能比 raw_df 少一行 (因为 pct_change)，所以要再次对齐
        final_df = pd.DataFrame({'Port': port_ret})
        
        if 'SPY' in returns.columns:
            final_df['Mkt'] = returns['SPY'] # 用 SPY 作为 Mkt (或者用数据库里的 mkt 因子也可以)
        elif 'mkt' in raw_df.columns:
            final_df['Mkt'] = raw_df.loc[final_df.index, 'mkt']
            
        # 把因子拼回来 (注意列名转大写以匹配模型习惯)
        for f in ['smb', 'hml', 'mom']:
            if f in raw_df.columns:
                final_df[f.upper()] = raw_df.loc[final_df.index, f]
        
        return final_df.dropna()

    def _plot_cumulative_return(self, df):
        try:
            cum_port = (1 + df['Port']).cumprod()
            cum_mkt = (1 + df['Mkt']).cumprod()
            fig = plt.figure(figsize=(10, 5))
            plt.plot(cum_port, label='My Portfolio', linewidth=2)
            plt.plot(cum_mkt, label='S&P 500', linestyle='--', color='gray')
            plt.title('Portfolio vs Benchmark (Cumulative Return)')
            plt.legend()
            plt.grid(True, alpha=0.3)
            return fig
        except: pass

    def _plot_static(self, model):
        try:
            params = model.params.drop('const', errors='ignore')
            fig = plt.figure(figsize=(10, 6))
            if len(params) > 0: 
                colors = ['#1f77b4' if 'Mkt' in idx else '#ff7f0e' for idx in params.index]
                params.plot(kind='bar', alpha=0.8, color=colors)
            plt.title('Factor Exposure (Beta)')
            plt.grid(axis='y', linestyle='--', alpha=0.5)
            return fig
        except: return None

    def _plot_rolling(self, params):
        try:
            fig, axes = plt.subplots(3, 1, figsize=(12, 12), sharex=True)
            if 'Annualized Alpha' in params.columns:
                axes[0].plot(params.index, params['Annualized Alpha'], color='green')
                axes[0].set_title('Rolling Alpha (Annualized)')
            if 'Mkt' in params.columns:
                axes[1].plot(params.index, params['Mkt'], color='gray')
                axes[1].set_title('Rolling Market Beta')
            
            factor_cols = [c for c in params.columns if c in ['SMB', 'HML', 'MOM']]
            if factor_cols:
                for col in factor_cols:
                    axes[2].plot(params.index, params[col], label=col)
                axes[2].legend()
            axes[2].set_title('Factor Betas')
            plt.tight_layout()
            return fig
        except: return None