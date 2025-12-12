import pandas as pd
import requests
import io
from src.config import DATA_DIR

class StockUniverse:
    """
    股票池管理器：负责获取 S&P 500 (大盘) 和 S&P 600 (小盘)
    """
    
    def __init__(self):
        self.sp500_file = DATA_DIR / "sp500_tickers.csv"
        self.sp600_file = DATA_DIR / "sp600_tickers.csv"
        
        # 伪装头 (反爬虫)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    def get_sp500(self, force_update=False):
        """获取大盘股列表"""
        return self._get_tickers(
            "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
            self.sp500_file,
            force_update
        )

    def get_sp600(self, force_update=False):
        """获取小盘股列表 (S&P 600)"""
        return self._get_tickers(
            "https://en.wikipedia.org/wiki/List_of_S%26P_600_companies",
            self.sp600_file,
            force_update,
            table_index=0 # 维基百科页面通常第一个表格是成分股
        )

    def _get_tickers(self, url, cache_file, force_update, table_index=0):
        """通用的下载与缓存逻辑"""
        if cache_file.exists() and not force_update:
            print(f"📦 从本地加载: {cache_file.name}")
            df = pd.read_csv(cache_file)
            return df['Symbol'].tolist()
        
        print(f"🌐 正在下载列表: {url.split('/')[-1]} ...")
        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            # 解析表格
            file_obj = io.StringIO(response.text)
            tables = pd.read_html(file_obj)
            
            # 这里需要一点容错，不同页面的表格位置可能不同，通常是第一个
            df = tables[table_index]
            
            # 兼容性清洗: 维基百科列名可能是 'Symbol' 或 'Ticker symbol'
            col_name = 'Symbol' if 'Symbol' in df.columns else 'Ticker symbol'
            if col_name not in df.columns:
                # 最后的尝试：取第一列
                df.rename(columns={df.columns[0]: 'Symbol'}, inplace=True)
            else:
                df.rename(columns={col_name: 'Symbol'}, inplace=True)

            # 符号清洗 (BRK.B -> BRK B) - 适配 IBKR/Yahoo
            # 注意：Yahoo 需要 'BRK-B', IBKR 需要 'BRK B'
            # 我们这里统一存为最原始的，具体使用时再转
            df['Symbol'] = df['Symbol'].str.replace('.', ' ', regex=False)
            
            tickers = df['Symbol'].tolist()
            
            # 保存缓存
            pd.DataFrame(tickers, columns=['Symbol']).to_csv(cache_file, index=False)
            return tickers
            
        except Exception as e:
            print(f"❌ 下载列表失败: {e}")
            return []