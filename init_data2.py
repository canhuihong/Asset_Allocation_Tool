import os
import logging
from src.data_manager import DataManager
# 强制开启代理 (下载数据必须有网)
os.environ["HTTP_PROXY"] = "http://127.0.0.1:7897"
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7897"

logging.basicConfig(level=logging.INFO)

def main():
    print("🚀 正在初始化数据库...")
    db = DataManager()
    
    # 1. 这里的列表必须包含 main.py 里 my_portfolio 用到的所有股票！
    # 加上 SPY, QQQ, TLT, GLD 是为了给回测和优化做素材
    target_tickers = [
        'AAPL', 'MSFT', 'JPM', 'NVDA',  # main.py 里的主角
        'SPY', 'QQQ', 'TLT', 'GLD',     # 配角和基准
        'TSLA', 'GOOGL', 'AMZN'         # 备选
    ]
    
    print(f"📦 准备下载/更新以下股票: {target_tickers}")
    db.update_stock_data(target_tickers)
    
    print("\n✅ 数据库初始化完成！请运行 python main.py")

if __name__ == "__main__":
    main()