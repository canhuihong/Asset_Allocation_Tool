import os
import logging
import pandas as pd
import requests
from src.data_manager import DataManager

# ==========================================
# 1. 网络与代理设置
# ==========================================
PROXY_PORT = 7897 
os.environ["HTTP_PROXY"] = f"http://127.0.0.1:{PROXY_PORT}"
os.environ["HTTPS_PROXY"] = f"http://127.0.0.1:{PROXY_PORT}"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_tickers_from_wiki(url, limit, name):
    """
    通用爬虫：从维基百科表格中提取股票代码
    """
    print(f"🌐 正在抓取 [{name}]... 目标数量: {limit}")
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        r = requests.get(url, headers=headers, proxies={"http": os.environ["HTTP_PROXY"], "https": os.environ["HTTPS_PROXY"]})
        
        # 解析表格
        tables = pd.read_html(r.text)
        df = tables[0]
        
        # 寻找代码列 (Symbol 或 Ticker symbol)
        col_name = 'Symbol' if 'Symbol' in df.columns else 'Ticker symbol'
        
        # 清洗代码 (把 BF.B 变成 BF-B)
        tickers = df[col_name].str.replace('.', '-', regex=False).tolist()
        
        # 截取前 N 个
        selected = tickers[:limit]
        print(f"✅ [{name}] 抓取成功! 实际获取: {len(selected)} 只")
        return selected
        
    except Exception as e:
        print(f"⚠️ [{name}] 抓取失败: {e}")
        return []

def main():
    print("🚀 正在初始化数据库 (自定义数量版)...")
    db = DataManager()
    
    # ==========================================
    # 👇👇👇 在这里设定你要的数量 👇👇👇
    # ==========================================
    NUM_LARGE_CAP = 500   # 想要多少只大盘股 (S&P 500)
    NUM_SMALL_CAP = 600   # 想要多少只小盘股 (S&P 600)
    # ==========================================

    # 1. 抓取 S&P 500 (大盘)
    url_sp500 = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    large_caps = get_tickers_from_wiki(url_sp500, limit=NUM_LARGE_CAP, name="S&P 500")
    
    # 备用大盘股 (防爬虫失败)
    if not large_caps:
        print("🔄 使用内置备用大盘列表...")
        large_caps = ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'AMZN', 'META', 'TSLA', 'JPM', 'V', 'LLY']

    # 2. 抓取 S&P 600 (小盘)
    url_sp600 = "https://en.wikipedia.org/wiki/List_of_S%26P_600_companies"
    small_caps = get_tickers_from_wiki(url_sp600, limit=NUM_SMALL_CAP, name="S&P 600")

    # 3. 必须包含的核心 ETF 和 重点关注股
    # SPY=大盘基准, IWM=小盘基准, TLT=美债, GLD=黄金
    essential_tickers = [
        'SPY', 'QQQ', 'TLT', 'GLD', 'IWM', 
        'AAPL', 'MSFT', 'NVDA', 'JPM' # 确保 main.py 里的主角一定在
    ]
    
    # 4. 合并并去重
    final_tickers = list(set(large_caps + small_caps + essential_tickers))
    
    print("-" * 50)
    print(f"📦 最终清单统计:")
    print(f"   - 大盘股 (S&P 500): {len(large_caps)}")
    print(f"   - 小盘股 (S&P 600): {len(small_caps)}")
    print(f"   - 核心 ETF/个股:    {len(essential_tickers)}")
    print(f"   --------------------")
    print(f"   🔥 总共需下载:      {len(final_tickers)} 只股票")
    print("-" * 50)
    
    # 5. 执行下载
    db.update_stock_data(final_tickers)
    
    print("\n✅ 数据库更新完成！请运行 'python main.py' 查看新结果。")

if __name__ == "__main__":
    main()