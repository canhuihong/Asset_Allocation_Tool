import pandas as pd
import numpy as np
from pathlib import Path
from src.config import DATA_DIR

class FactorEngine:
    def __init__(self):
        self.price_dir = DATA_DIR / "prices"
        self.fund_dir = DATA_DIR / "fundamentals"
        
    def run(self):
        """
        主执行函数：从数据加载到因子计算的全流程
        """
        # 1. 加载所有数据
        print("📥 正在加载价格与基本面数据...")
        df_panel = self._load_and_merge_data()
        
        if df_panel is None or df_panel.empty:
            print("❌ 数据加载失败或合并后为空，无法计算因子。")
            return None

        print(f"✅ 数据合并成功: 共 {len(df_panel)} 条观测值")

        # 2. 计算每日收益率
        # 按照股票代码分组，计算 pct_change
        df_panel['ret'] = df_panel.groupby('symbol')['close'].pct_change()
        
        # 3. 核心：每日构建多空组合 (Simplified Fama-French)
        print("🧮 正在计算每日 SMB / HML 因子...")
        
        # 这种 groupby 可能会产生 warnings，这是正常的
        factors = df_panel.groupby('date').apply(self._calculate_daily_factors)
        
        return factors

    def _load_and_merge_data(self):
        """
        读取所有 CSV 并合并为一个大的 Panel DataFrame
        """
        # --- A. 读取价格数据 ---
        price_files = list(self.price_dir.glob("*.csv"))
        if not price_files:
            print("⚠️ 未找到价格数据，请先运行下载器。")
            return None
            
        dfs = []
        for p in price_files:
            try:
                df = pd.read_csv(p, parse_dates=['date'])
                df['symbol'] = p.stem  # 文件名即代码 (AAPL.csv -> AAPL)
                df = df[['date', 'symbol', 'close']] # 只取收盘价
                dfs.append(df)
            except Exception as e:
                print(f"⚠️ 读取 {p.name} 失败: {e}")
        
        if not dfs: return None
        df_prices = pd.concat(dfs)
        
        # --- B. 读取基本面数据 ---
        fund_files = list(self.fund_dir.glob("*_fundamentals.csv"))
        dfs_fund = []
        for f in fund_files:
            try:
                df = pd.read_csv(f, parse_dates=['date'])
                # 文件名是 AAPL_fundamentals.csv -> 提取 AAPL
                symbol = f.name.split('_')[0] 
                df['symbol'] = symbol
                
                # 兼容性检查：确保有 shares 列
                if 'shares' not in df.columns:
                    # 如果之前 FMP 的旧数据残留，可能只有 marketCap
                    if 'marketCap' in df.columns and 'close' in df.columns:
                        # 尝试倒推 shares (不推荐，但为了容错)
                        df['shares'] = df['marketCap'] / df['close'] 
                    else:
                        continue # 跳过无效数据
                
                # 只取需要的列
                cols_to_keep = ['date', 'symbol', 'book_value', 'shares']
                df = df[[c for c in cols_to_keep if c in df.columns]]
                dfs_fund.append(df)
            except Exception as e:
                print(f"⚠️ 读取基本面 {f.name} 失败: {e}")
            
        if not dfs_fund:
            print("⚠️ 未找到基本面数据。")
            return None
            
        df_funds = pd.concat(dfs_fund)
        
        # --- C. 合并策略 (Merge Logic) ---
        # 🌟【关键修复 1】：pd.merge_asof 要求左表(prices)必须严格按 date 排序
        # 之前按 ['symbol', 'date'] 排序会导致 date 不是单调递增的，从而报错
        df_prices = df_prices.sort_values('date')
        df_funds = df_funds.sort_values('date')
        
        # 使用 merge_asof 将财报数据匹配到每天
        df_merge = pd.merge_asof(
            df_prices,
            df_funds,
            on='date',
            by='symbol',
            direction='backward' # 使用最近一次已知的财报
        )
        
        # --- D. 计算衍生指标 (适配 Yahoo 数据) ---
        # 🌟【关键修复 2】：使用 shares 计算每日动态市值
        if 'shares' in df_merge.columns:
            # Size = 每日股价 * 历史股本
            df_merge['size'] = df_merge['close'] * df_merge['shares']
        else:
            print("❌ 数据中缺少 'shares' 列，无法计算市值。")
            return None

        # BM = 账面价值 / 动态市值
        df_merge['bm'] = df_merge['book_value'] / df_merge['size']
        
        # 清理无穷大或空值
        df_merge.replace([np.inf, -np.inf], np.nan, inplace=True)
        df_merge.dropna(subset=['size', 'bm', 'close'], inplace=True)
        
        # 过滤掉市值过小的数据 (例如小于 1000 万) 防止噪音
        df_merge = df_merge[df_merge['size'] > 1e7]
        
        return df_merge

    def _calculate_daily_factors(self, daily_df):
        """
        每天被调用一次。
        """
        # 如果当天的股票数量太少，无法有效分组，返回空
        # 既然我们用了 nanmean，可以稍微放宽限制，只要有数据就行
        if len(daily_df) < 2: 
            return pd.Series({'SMB': np.nan, 'HML': np.nan})
            
        try:
            # --- 1. Size 分组 (Small vs Big) ---
            median_size = daily_df['size'].median()
            small_cap = daily_df[daily_df['size'] <= median_size]
            big_cap = daily_df[daily_df['size'] > median_size]
            
            # --- 2. Value 分组 (30%, 70%) ---
            bm_30 = daily_df['bm'].quantile(0.3)
            bm_70 = daily_df['bm'].quantile(0.7)
            
            # --- 3. 计算六个组合的平均收益率 ---
            # 如果某组为空，mean() 会返回 NaN
            
            # S/L, S/M, S/H
            sl = small_cap[small_cap['bm'] <= bm_30]['ret'].mean()
            sm = small_cap[(small_cap['bm'] > bm_30) & (small_cap['bm'] < bm_70)]['ret'].mean()
            sh = small_cap[small_cap['bm'] >= bm_70]['ret'].mean()
            
            # B/L, B/M, B/H
            bl = big_cap[big_cap['bm'] <= bm_30]['ret'].mean()
            bm = big_cap[(big_cap['bm'] > bm_30) & (big_cap['bm'] < bm_70)]['ret'].mean()
            bh = big_cap[big_cap['bm'] >= bm_70]['ret'].mean()
            
            # --- 4. 因子构建 (Robust 版本) ---
            # 🌟 关键修改：使用 np.nanmean 自动忽略空值 (NaN)
            # 这样即使 "Small-Medium" 组里没股票，也能用 S/L 和 S/H 算出 SMB
            
            small_ret = np.nanmean([sl, sm, sh])
            big_ret = np.nanmean([bl, bm, bh])
            
            # 如果 Small 或 Big 整体都没数据，结果就是 NaN
            smb = small_ret - big_ret
            
            high_ret = np.nanmean([sh, bh])
            low_ret = np.nanmean([sl, bl])
            
            hml = high_ret - low_ret
            
            return pd.Series({'SMB': smb, 'HML': hml})
            
        except Exception:
            return pd.Series({'SMB': np.nan, 'HML': np.nan})