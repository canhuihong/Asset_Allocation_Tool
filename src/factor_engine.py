import pandas as pd
import numpy as np
import logging
from pathlib import Path
from src.config import DATA_DIR

logger = logging.getLogger("PYL.factor_engine")

class FactorEngine:
    def __init__(self):
        self.price_dir = DATA_DIR / "prices"
        self.fund_dir = DATA_DIR / "fundamentals"
        
    def run(self):
        """Main execution function"""
        # 1. Load data
        logger.info("Loading data and calculating momentum signals...")
        df_panel = self._load_and_merge_data()
        
        if df_panel is None or df_panel.empty:
            logger.error("Failed to load data for factor calculation.")
            return None

        logger.info(f"Data ready: {len(df_panel)} observations")

        # 2. Calculate daily returns
        df_panel['ret'] = df_panel.groupby('symbol')['close'].pct_change()
        
        # 3. Calculate daily SMB / HML / MOM factors
        logger.info("Calculating daily SMB / HML / MOM factors...")
        
        # 这一步比较耗时，请耐心等待
        factors = df_panel.groupby('date').apply(self._calculate_daily_factors)
        
        return factors

    def _load_and_merge_data(self):
        # --- A. Read price data ---
        price_files = list(self.price_dir.glob("*.csv"))
        if not price_files:
            logger.warning("No price data files found.")
            return None
            
        dfs = []
        for p in price_files:
            try:
                df = pd.read_csv(p, parse_dates=['date'])
                df['symbol'] = p.stem
                df = df[['date', 'symbol', 'close']].sort_values('date')
                
                # 🌟【新增】计算动量信号 (Momentum Signal)
                # 逻辑：过去12个月的累计收益，剔除最近1个月 (12-1 Month Momentum)
                # 假设一年 252 个交易日，一个月 21 个交易日
                # Shift(21) 是一个月前的价格，Shift(252) 是一年前的价格
                p_lag1 = df['close'].shift(21)
                p_lag12 = df['close'].shift(252)
                
                # MOM = (P_t-1 / P_t-12) - 1
                df['mom_signal'] = (p_lag1 / p_lag12) - 1
                
                dfs.append(df)
            except Exception:
                pass
        
        if not dfs: return None
        df_prices = pd.concat(dfs)
        
        # --- B. 读取基本面数据 ---
        fund_files = list(self.fund_dir.glob("*_fundamentals.csv"))
        dfs_fund = []
        for f in fund_files:
            try:
                df = pd.read_csv(f, parse_dates=['date'])
                symbol = f.name.split('_')[0] 
                df['symbol'] = symbol
                
                if 'shares' not in df.columns:
                    if 'marketCap' in df.columns and 'close' in df.columns:
                        df['shares'] = df['marketCap'] / df['close'] 
                    else:
                        continue
                
                cols = ['date', 'symbol', 'book_value', 'shares']
                df = df[[c for c in cols if c in df.columns]]
                dfs_fund.append(df)
            except Exception:
                pass
            
        if not dfs_fund: return None
        df_funds = pd.concat(dfs_fund)
        
        # --- C. 合并 ---
        df_prices = df_prices.sort_values('date')
        df_funds = df_funds.sort_values('date')
        
        df_merge = pd.merge_asof(
            df_prices,
            df_funds,
            on='date',
            by='symbol',
            direction='backward'
        )
        
        # --- D. 计算市值和估值 ---
        if 'shares' in df_merge.columns:
            df_merge['size'] = df_merge['close'] * df_merge['shares']
        else:
            return None

        df_merge['bm'] = df_merge['book_value'] / df_merge['size']
        
        # 清理无效值
        df_merge.replace([np.inf, -np.inf], np.nan, inplace=True)
        # 注意：不要因为 mom_signal 是 NaN 就删掉整行，否则前一年的数据全没了，SMB/HML 也算不了
        # 我们只在计算 MOM 时处理 NaN
        df_merge.dropna(subset=['size', 'bm', 'close'], inplace=True)
        
        # 过滤微小盘
        df_merge = df_merge[df_merge['size'] > 1e7]
        
        return df_merge

    def _calculate_daily_factors(self, daily_df):
        """每日截面计算"""
        if len(daily_df) < 5: 
            return pd.Series({'SMB': np.nan, 'HML': np.nan, 'MOM': np.nan})
            
        try:
            # --- 1. Size & Value (SMB, HML) ---
            median_size = daily_df['size'].median()
            small_cap = daily_df[daily_df['size'] <= median_size]
            big_cap = daily_df[daily_df['size'] > median_size]
            
            bm_30 = daily_df['bm'].quantile(0.3)
            bm_70 = daily_df['bm'].quantile(0.7)
            
            # 计算 6 个基础组合
            sl = small_cap[small_cap['bm'] <= bm_30]['ret'].mean()
            sm = small_cap[(small_cap['bm'] > bm_30) & (small_cap['bm'] < bm_70)]['ret'].mean()
            sh = small_cap[small_cap['bm'] >= bm_70]['ret'].mean()
            
            bl = big_cap[big_cap['bm'] <= bm_30]['ret'].mean()
            bm = big_cap[(big_cap['bm'] > bm_30) & (big_cap['bm'] < bm_70)]['ret'].mean()
            bh = big_cap[big_cap['bm'] >= bm_70]['ret'].mean()
            
            smb = np.nanmean([sl, sm, sh]) - np.nanmean([bl, bm, bh])
            hml = np.nanmean([sh, bh]) - np.nanmean([sl, bl])
            
            # --- 2. Momentum (MOM) ---
            # 🌟【新增】动量因子计算
            # 只有当动量信号存在时才计算 (前一年的数据这里会是 NaN)
            valid_mom = daily_df.dropna(subset=['mom_signal'])
            
            if len(valid_mom) > 5:
                # 按照动量信号排序
                mom_30 = valid_mom['mom_signal'].quantile(0.3) # Losers
                mom_70 = valid_mom['mom_signal'].quantile(0.7) # Winners
                
                # Winners (Top 30%)
                winners = valid_mom[valid_mom['mom_signal'] >= mom_70]['ret'].mean()
                # Losers (Bottom 30%)
                losers = valid_mom[valid_mom['mom_signal'] <= mom_30]['ret'].mean()
                
                mom = winners - losers
            else:
                mom = np.nan
            
            return pd.Series({'SMB': smb, 'HML': hml, 'MOM': mom})
            
        except Exception:
            return pd.Series({'SMB': np.nan, 'HML': np.nan, 'MOM': np.nan})