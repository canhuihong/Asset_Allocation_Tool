import pandas as pd
import requests
from io import StringIO
import logging

logger = logging.getLogger("PYL.universe")

class StockUniverse:
    def __init__(self):
        pass
            
        # 2. 定义请求头 (伪装成 Chrome 浏览器)
        # (解决 Wikipedia 的 HTTP 403 Forbidden 反爬虫拦截)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    def get_sp500(self):
        """
        获取 S&P 500 成分股
        Returns: (tickers_list, name_map_dict)
        """
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        try:
            # 发送带 Header 的请求
            r = requests.get(url, headers=self.headers)
            r.raise_for_status() # 检查 404/403 等错误
            
            # 使用 io.StringIO 包装文本，供 pandas 读取
            df = pd.read_html(StringIO(r.text))[0]
            
            # 这里的逻辑不能少：清洗数据
            if 'Symbol' in df.columns:
                # 1. 替换点号 (BRK.B -> BRK-B) 以适配 Yahoo/IB
                df['Symbol'] = df['Symbol'].str.replace('.', '-', regex=False)
                tickers = df['Symbol'].tolist()
                
                # 2. 提取公司名称 (S&P 500 表格中列名叫 'Security')
                # 有时候维基百科会微调列名，这里做一个简单的兼容判断
                name_col = 'Security' if 'Security' in df.columns else df.columns[1]
                name_map = dict(zip(df['Symbol'], df[name_col]))
                
                return tickers, name_map
            
            return [], {}
            
        except requests.RequestException as e:
            logger.warning(f"Failed to fetch S&P 500 list: {e}")
            return [], {}
        except Exception as e:
            logger.error(f"Unexpected error fetching S&P 500: {e}", exc_info=True)
            return [], {}

    def get_sp600(self):
        """
        获取 S&P 600 (小盘股) 成分股
        Returns: (tickers_list, name_map_dict)
        """
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_600_companies"
        try:
            r = requests.get(url, headers=self.headers)
            r.raise_for_status()
            df = pd.read_html(StringIO(r.text))[0]
            
            if 'Symbol' in df.columns:
                # 1. 替换点号
                df['Symbol'] = df['Symbol'].str.replace('.', '-', regex=False)
                tickers = df['Symbol'].tolist()
                
                # 2. 提取公司名称 (S&P 600 表格中列名叫 'Company')
                name_col = 'Company' if 'Company' in df.columns else df.columns[1]
                name_map = dict(zip(df['Symbol'], df[name_col]))
                
                return tickers, name_map
                
            return [], {}
            
        except requests.RequestException as e:
            logger.warning(f"Failed to fetch S&P 600 list: {e}")
            return [], {}
        except Exception as e:
            logger.error(f"Unexpected error fetching S&P 600: {e}", exc_info=True)
            return [], {}