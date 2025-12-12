import time
import requests
import pandas as pd
from pathlib import Path
from src.config import FMP_API_KEY, FMP_BASE_URL, FUNDAMENTAL_DIR

class FMPDataManager:
    def __init__(self):
        self.api_key = FMP_API_KEY
        self.base_url = FMP_BASE_URL
        
    def get_fama_french_fundamentals(self, symbol, force_update=False):
        """
        获取构建 FF 因子所需的关键数据：
        1. Total Stockholders Equity (用于计算 Book Value)
        2. Market Capitalization (用于计算 Size 和 B/M)
        
        返回: DataFrame (Date, Symbol, BookValue, MarketCap)
        """
        local_path = FUNDAMENTAL_DIR / f"{symbol}_fundamentals.csv"
        
        # 1. 缓存检查：如果本地有且不强制更新，直接读取
        if local_path.exists() and not force_update:
            # print(f"📦 加载本地基本面缓存: {symbol}") # 减少日志噪音
            return pd.read_csv(local_path, parse_dates=['date'])
            
        print(f"🌐 正在下载 FMP 基本面数据: {symbol} ...")
        
        try:
            # 2. 获取资产负债表 (Balance Sheet) - 年频
            # Fama-French 通常使用年度财报数据
            bs_data = self._fetch_api(f"balance-sheet-statement/{symbol}", params={'limit': 20})
            
            # 3. 获取历史市值 (Historical Market Cap) - 日频但我们只需要每年的
            # 注意：这里我们取足够长的数据来覆盖财报日期
            cap_data = self._fetch_api(f"historical-market-capitalization/{symbol}", params={'limit': 5000}) 
            
            if not bs_data or not cap_data:
                print(f"⚠️ {symbol} 数据缺失")
                return None

            # 4. 数据清洗与合并 (Data Engineering 核心)
            df_bs = pd.DataFrame(bs_data)
            df_cap = pd.DataFrame(cap_data)
            
            # 统一日期格式
            df_bs['date'] = pd.to_datetime(df_bs['date'])
            df_cap['date'] = pd.to_datetime(df_cap['date'])
            
            # 提取关键字段：股东权益 (Total Stockholders Equity)
            # 有些公司可能字段名不同，这里做个简单容错
            if 'totalStockholdersEquity' in df_bs.columns:
                df_bs = df_bs[['date', 'totalStockholdersEquity', 'symbol']].copy()
                df_bs.rename(columns={'totalStockholdersEquity': 'book_value'}, inplace=True)
            else:
                print(f"❌ {symbol} 找不到股东权益字段")
                return None

            # 处理市值：我们需要财报发布当且日或年末的市值
            # 为了简化，我们这里通过 merge_asof (近似匹配) 来找到财报日期的市值
            df_cap = df_cap[['date', 'marketCap']].sort_values('date')
            df_bs = df_bs.sort_values('date')
            
            # merge_asof: 在财报日期，找最近的一个市值数据 (向后找或向前找)
            # direction='nearest' 表示找离财报日期最近的那个交易日的市值
            df_merged = pd.merge_asof(
                df_bs, 
                df_cap, 
                on='date', 
                direction='nearest', 
                tolerance=pd.Timedelta(days=7) # 容忍前后7天内的误差
            )
            
            # 5. 保存到本地 (CSV)
            df_merged.to_csv(local_path, index=False)
            
            # 6. 礼貌性休眠 (防封号)
            time.sleep(0.2)
            
            return df_merged

        except Exception as e:
            print(f"❌ 处理 {symbol} 基本面数据时出错: {e}")
            return None

    def _fetch_api(self, endpoint, params=None):
        """内部方法：封装 Requests 请求，处理异常"""
        if params is None:
            params = {}
        params['apikey'] = self.api_key
        
        url = f"{self.base_url}/{endpoint}"
        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 403:
                print("❌ API Key 无效或额度用尽")
                return []
            else:
                print(f"⚠️ API 请求失败: {response.status_code}")
                return []
        except Exception as e:
            print(f"❌ 网络请求异常: {e}")
            return []