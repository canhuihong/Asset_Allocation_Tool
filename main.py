from ib_insync import IB
from src.config import IB_HOST, IB_PORT, IB_CLIENT_ID
from src.universe import SP500Universe
from src.data_downloader import DataDownloader
from src.fmp_data import FMPDataManager # 导入新模块

def main():
    # --- 阶段 1: 确定股票池 ---
    print("=== 阶段 1: 构建股票池 ===")
    universe_loader = SP500Universe()
    tickers = universe_loader.get_tickers()
    
    # ⚠️ 此时建议只测试前 5 只，跑通了再放开
    target_tickers = tickers[:5] 
    print(f"🎯 目标股票: {target_tickers}")

    # --- 阶段 2: 下载价格数据 (IBKR) ---
    # (如果你之前已经下载过，可以注释掉这部分以节省时间)
    """
    print("\n=== 阶段 2: 下载价格数据 (IBKR) ===")
    ib = IB()
    try:
        ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID)
        contracts = [Stock(s, 'SMART', 'USD') for s in target_tickers]
        ib.qualifyContracts(*contracts)
        
        downloader = DataDownloader(ib)
        downloader.download_history(contracts)
    except Exception as e:
        print(f"IBKR 连接错误: {e}")
    finally:
        ib.disconnect()
    """

    # --- 阶段 3: 下载基本面数据 (FMP) ---
    print("\n=== 阶段 3: 下载基本面数据 (FMP) ===")
    fmp_manager = FMPDataManager()
    
    success_count = 0
    for symbol in target_tickers:
        df_fund = fmp_manager.get_fama_french_fundamentals(symbol)
        
        if df_fund is not None and not df_fund.empty:
            success_count += 1
            # 打印最新一年的数据验证一下
            latest = df_fund.iloc[-1]
            print(f"   📊 {symbol} | 日期: {latest['date'].date()} | "
                  f"账面价值: {latest['book_value']/1e9:.2f}B | "
                  f"市值: {latest['marketCap']/1e9:.2f}B")
    
    print(f"\n✅ 基本面数据处理完成: {success_count}/{len(target_tickers)}")

if __name__ == "__main__":
    main()