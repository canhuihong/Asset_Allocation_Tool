import pandas as pd
import requests
import io
from src.config import SP500_TICKERS_FILE

class SP500Universe:
    """
    标普500成分股管理器
    负责获取、更新和读取成分股代码列表
    """
    
    def __init__(self):
        self.tickers = []

    def get_tickers(self, force_update=False):
        """
        获取成分股列表。
        :param force_update: 是否强制从网络重新下载
        :return: list of strings (e.g., ['AAPL', 'MSFT', ...])
        """
        if SP500_TICKERS_FILE.exists() and not force_update:
            print(f"📦 从本地缓存加载 SP500 列表: {SP500_TICKERS_FILE}")
            df = pd.read_csv(SP500_TICKERS_FILE)
            self.tickers = df['Symbol'].tolist()
        else:
            print("🌐 正在从 Wikipedia 下载最新的 SP500 列表...")
            self.tickers = self._download_from_wiki()
            self._save_to_csv()
            
        return self.tickers

    def _download_from_wiki(self):
        """内部方法：爬取维基百科 (带伪装头)"""
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        
        # --- 关键修正：伪装成浏览器 ---
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        try:
            # 1. 使用 requests 发送带 Header 的请求
            response = requests.get(url, headers=headers)
            response.raise_for_status() # 如果是 403/404，这里会抛出异常
            
            # 2. 将网页文本内容传给 pandas
            # pandas.read_html 在某些版本需要文件流对象，所以用 io.StringIO 包装一下
            file_obj = io.StringIO(response.text)
            tables = pd.read_html(file_obj)
            
            # 3. 提取表格
            df = tables[0]
            
            # 4. 数据清洗 (把 BRK.B 变成 BRK B)
            df['Symbol'] = df['Symbol'].str.replace('.', ' ', regex=False)
            
            return df['Symbol'].tolist()
            
        except Exception as e:
            print(f"❌ 下载维基百科数据失败: {e}")
            # 如果下载失败，返回一个空列表或抛出错误，避免程序崩溃
            return []

    def _save_to_csv(self):
        """内部方法：保存到 data 目录"""
        if not self.tickers:
            print("⚠️ 警告：没有获取到股票列表，跳过保存。")
            return
            
        df = pd.DataFrame(self.tickers, columns=['Symbol'])
        df.to_csv(SP500_TICKERS_FILE, index=False)
        print(f"✅ 列表已保存至: {SP500_TICKERS_FILE} (共 {len(self.tickers)} 只)")