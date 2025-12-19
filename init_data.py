import os
import logging
import pandas as pd
import requests
import datetime
import pandas_datareader.data as web
from src.data_manager import DataManager
from src.config import DATA_DIR  # 确保引入配置路径

# ==========================================
# 1. 网络与代理设置 (根据您的实际情况调整端口)
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

def fetch_and_save_online_factors(db):
    """
    尝试在线下载 Fama-French 因子并保存
    """
    print("\n🌐 [方式1] 正在尝试在线下载 Fama-French 因子 (Kenneth French Library)...")
    start_date = "2000-01-01"
    end_date = datetime.datetime.now().strftime("%Y-%m-%d")

    try:
        # 1. 下载 Fama-French 3因子 (Mkt-RF, SMB, HML)
        ff3_data = web.DataReader("F-F_Research_Data_Factors_daily", "famafrench", start=start_date, end=end_date)
        df_ff3 = ff3_data[0]
        
        # 2. 下载 动量因子 (Momentum)
        mom_data = web.DataReader("F-F_Momentum_Factor_daily", "famafrench", start=start_date, end=end_date)
        df_mom = mom_data[0]
        
        # 3. 合并数据并除以100 (原始数据是百分比整数)
        df_merged = df_ff3.join(df_mom, how="inner") / 100.0
        
        # 4. 重命名列以匹配数据库 schema
        df_merged.rename(columns={
            'Mkt-RF': 'mkt',
            'SMB': 'smb',
            'HML': 'hml',
            'Mom   ': 'mom'
        }, inplace=True)
        
        # 清洗列名
        df_merged.columns = [c.strip().lower() for c in df_merged.columns]
        
        # 5. 存入数据库
        required_cols = ['mkt', 'smb', 'hml', 'mom']
        if all(col in df_merged.columns for col in required_cols):
            db.save_factors(df_merged[required_cols])
            print(f"✅ 在线因子更新成功! 时间范围: {df_merged.index[0].date()} -> {df_merged.index[-1].date()}")
            return True
        else:
            print("⚠️ 在线数据列名不匹配。")
            return False
            
    except Exception as e:
        print(f"❌ 在线下载失败: {e}")
        return False

def load_local_factors(db):
    """
    读取本地 CSV 因子文件作为备用
    """
    print("\n📂 [方式2] 正在尝试读取本地因子文件 (data/my_ff_factors.csv)...")
    factor_path = DATA_DIR / "my_ff_factors.csv"
    
    if not factor_path.exists():
        print(f"⚠️ 未找到本地因子文件: {factor_path}")
        return

    try:
        df = pd.read_csv(factor_path)
        # 清洗列名
        df.columns = [c.lower().strip() for c in df.columns]
        
        # 处理日期
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
        else:
            try: df.index = pd.to_datetime(df.index)
            except: 
                print("❌ 本地文件日期解析失败")
                return

        # 简单的列名映射兼容
        rename_map = {}
        for col in df.columns:
            if 'mkt' in col: rename_map[col] = 'mkt'
            elif 'smb' in col: rename_map[col] = 'smb'
            elif 'hml' in col: rename_map[col] = 'hml'
            elif 'mom' in col: rename_map[col] = 'mom'
        df.rename(columns=rename_map, inplace=True)
        
        valid_cols = [c for c in ['smb', 'hml', 'mom', 'mkt'] if c in df.columns]
        if valid_cols:
            db.save_factors(df[valid_cols])
            print(f"✅ 本地因子加载成功! 包含列: {valid_cols}")
        else:
            print("❌ 本地文件缺少必要的因子列。")
            
    except Exception as e:
        print(f"❌ 本地加载出错: {e}")

def main():
    print("🚀 正在初始化数据库...")
    db = DataManager()
    
    # ==========================================
    # 设定股票数量
    # ==========================================
    NUM_LARGE_CAP = 500
    NUM_SMALL_CAP = 600

    # 1. 抓取大盘股
    url_sp500 = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    large_caps = get_tickers_from_wiki(url_sp500, limit=NUM_LARGE_CAP, name="S&P 500")
    if not large_caps:
        large_caps = ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'AMZN', 'META', 'TSLA', 'JPM', 'V', 'LLY']

    # 2. 抓取小盘股
    url_sp600 = "https://en.wikipedia.org/wiki/List_of_S%26P_600_companies"
    small_caps = get_tickers_from_wiki(url_sp600, limit=NUM_SMALL_CAP, name="S&P 600")

    # 3. 核心标的
    essential_tickers = ['SPY', 'QQQ', 'TLT', 'GLD', 'IWM', 'AAPL', 'MSFT', 'NVDA', 'JPM']
    
    # 4. 合并去重
    final_tickers = list(set(large_caps + small_caps + essential_tickers))
    
    print("-" * 50)
    print(f"🔥 总共需下载: {len(final_tickers)} 只股票")
    print("-" * 50)
    
    # 5. 更新股价数据
    db.update_stock_data(final_tickers)
    
    # ==========================================
    # ✅ 6. 关键修复：更新因子数据 (优先在线，失败则本地)
    # ==========================================
    success = fetch_and_save_online_factors(db)
    if not success:
        load_local_factors(db)
    
    db.close()
    print("\n✅ 数据库初始化全部完成！请运行 'python main.py'。")

if __name__ == "__main__":
    main()