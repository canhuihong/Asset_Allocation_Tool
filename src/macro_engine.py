import pandas as pd
import numpy as np
import pandas_datareader.data as web
import statsmodels.api as sm
import matplotlib.pyplot as plt
import seaborn as sns
import logging
from src.data_manager import DataManager

logger = logging.getLogger("PYL.macro_engine")

class MacroEngine:
    def __init__(self):
        self.db = DataManager()
        
        # 定义宏观因子及其对应的 FRED 代码
        self.indicators = {
            'DGS10': 'Rates (10Y)',       # 利率
            'T5YIE': 'Inflation (5Y)',    # 通胀预期
            'T10Y2Y': 'Recession (Curve)',# 期限利差
            'BAMLC0A0CM': 'Credit Spread',# 信用利差
            'VIXCLS': 'VIX (Fear)',       # 恐慌指数
            'DCOILWTICO': 'Oil (WTI)',    # 原油
            'DTWEXBGS': 'USD Index'       # 美元
        }
        
        # 定义压力测试的情景 (Scenarios)
        # 这里的数值代表“变化量” (Change)
        # 例如：Rates: +0.01 代表利率上行 1% (100bps)
        self.scenarios = {
            'Rates Shock (+1%)':   {'DGS10': 1.0},        # 利率暴涨 100bps
            'Inflation Spike':     {'T5YIE': 0.5},        # 通胀预期涨 50bps
            'Oil Crisis (+20%)':   {'DCOILWTICO': 20.0},  # 油价暴涨 20美元
            'Market Panic (VIX+10)':{'VIXCLS': 10.0},     # VIX 飙升 10点
            'Recession (Spread-1%)':{'T10Y2Y': -1.0},     # 倒挂加深 100bps
            'USD Crash (-10%)':    {'DTWEXBGS': -10.0}    # 美元贬值 10点
        }

    def run_analysis(self, portfolio_weights):
        logger.info("Running Macro Stress Test & Sensitivity Analysis...")
        
        # 1. 准备组合数据
        tickers = list(portfolio_weights.keys())
        df_assets = self.db.get_aligned_data(tickers)
        if df_assets is None or df_assets.empty: return None
            
        price_cols = [c for c in df_assets.columns if c in tickers]
        returns = df_assets[price_cols].pct_change().dropna()
        
        weights = pd.Series(portfolio_weights)
        valid_tickers = returns.columns.intersection(weights.index)
        
        # 计算组合日收益序列
        port_ret = returns[valid_tickers].dot(weights[valid_tickers])
        port_ret.name = "Portfolio"

        # 2. 下载宏观数据
        try:
            start_date = port_ret.index[0]
            end_date = port_ret.index[-1]
            macro_data = web.DataReader(list(self.indicators.keys()), 'fred', start_date, end_date)
            # 计算宏观因子的每日变化量 (Diff)
            macro_changes = macro_data.diff().dropna()
        except Exception as e:
            logger.error(f"Macro data download failed: {e}")
            return None

        # 3. 对齐回归
        df_final = pd.concat([port_ret, macro_changes], axis=1).dropna()
        if len(df_final) < 60: return None

        # 4. 计算敏感度 (Betas)
        X = df_final[list(self.indicators.keys())]
        X = sm.add_constant(X)
        Y = df_final["Portfolio"]
        model = sm.OLS(Y, X).fit()
        betas = model.params.drop('const')
        
        # 5. 🔥 核心升级：执行压力测试
        stress_results = self._run_stress_test(betas)

        # 6. 生成图表 (两个图：Beta柱状图 + 压力测试热力图)
        fig = self._plot_combined(betas, stress_results)
        
        return fig

    def _run_stress_test(self, betas):
        """
        根据计算出的 Beta，估算在不同极端情景下组合的 PnL 变化
        公式: Estimated Impact = Beta * Scenario_Change
        """
        results = {}
        
        # 遍历每一个设定好的情景
        for scenario_name, shock_map in self.scenarios.items():
            total_impact = 0.0
            
            # 一个情景可能包含多个因子的变化 (这里简化为单一因子冲击)
            for factor_code, shock_value in shock_map.items():
                if factor_code in betas.index:
                    # Beta * 冲击量 = 预期组合收益变化
                    # 注意：宏观数据的单位要对齐。
                    # FRED 的利率 4.5 代表 4.5%，我们这里直接用数值计算即可
                    # 但需要注意 Beta 是基于“变化值”回归出来的。
                    
                    # 修正系数：
                    # 收益率是小数 (0.01)，但 FRED 数据通常是整数 (如 VIX=20) 或百分数 (Yield=4.5)
                    # 我们之前的回归是用 diff() 算的。
                    # 如果 DGS10 变动 +0.1 (即10bps)，diff就是0.1。
                    # 所以直接乘是可以的，但要注意单位量级。
                    
                    # 比如 Beta_Oil = 0.0005 (油价涨1美元，组合涨0.05%)
                    # shock_value = 20 (涨20美元)
                    # impact = 0.0005 * 20 = 0.01 (1%)
                    
                    beta = betas[factor_code]
                    impact = beta * shock_value
                    total_impact += impact
            
            results[scenario_name] = total_impact
            
        return pd.Series(results)

    def _plot_combined(self, betas, stress_results):
        try:
            # 创建画布：左边画 Beta，右边画压力测试
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))
            
            # --- 图1: 敏感度 (Beta) ---
            # 替换名字
            plot_betas = betas.copy()
            plot_betas.index = [self.indicators.get(x, x) for x in plot_betas.index]
            plot_betas = plot_betas.sort_values()
            
            colors = ['#e74c3c' if x < 0 else '#2ecc71' for x in plot_betas]
            plot_betas.plot(kind='barh', ax=ax1, color=colors, alpha=0.8)
            ax1.set_title('Portfolio Macro Sensitivities (Betas)')
            ax1.set_xlabel('Sensitivity (Beta)')
            ax1.grid(axis='x', linestyle='--', alpha=0.3)
            ax1.axvline(0, color='black', linewidth=0.8)

            # --- 图2: 压力测试 (Stress Test) ---
            # 将 Series 转为 DataFrame 以便画热力图
            stress_df = pd.DataFrame(stress_results, columns=['Est. PnL Impact'])
            
            # 颜色映射：亏钱是红，赚钱是绿
            sns.heatmap(stress_df, annot=True, fmt='.2%', cmap='RdYlGn', center=0, 
                        ax=ax2, cbar=False, annot_kws={"size": 12, "weight": "bold"})
            
            ax2.set_title('Stress Test: Estimated PnL Impact', fontsize=12)
            ax2.set_ylabel('')
            
            plt.tight_layout()
            return fig
            
        except Exception as e:
            logger.error(f"Plotting failed: {e}")
            return None