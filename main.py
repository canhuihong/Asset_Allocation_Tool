import pandas as pd
from ib_insync import IB, Stock
# 注意：这里我们导入的是新的 StockUniverse
from src.universe import StockUniverse 
from src.data_downloader import DataDownloader
# 注意：这里导入的是我们之前改好的 Yahoo 版数据管理器 (类名没变)
from src.fmp_data import FMPDataManager 
from src.factor_engine import FactorEngine
from src.config import IB_HOST, IB_PORT, IB_CLIENT_ID, DATA_DIR

def main():
    # ==========================================
    # 阶段 1: 构建混合股票池 (大盘 + 小盘)
    # ==========================================
    print("\n=== 阶段 1: 构建混合股票池 ===")
    universe_loader = StockUniverse()
    
    # 1. 获取大盘股 (S&P 500)
    print("正在获取 S&P 500 列表...")
    sp500 = universe_loader.get_sp500()
    
    # 2. 获取小盘股 (S&P 600)
    print("正在获取 S&P 600 列表...")
    sp600 = universe_loader.get_sp600()
    
    print(f"📚 统计: S&P500 共 {len(sp500)} 只, S&P600 共 {len(sp600)} 只")
    
    # --- 🎯 关键策略：构建 100 只股票的混合样本 ---
    # 取 S&P 500 的前 50 只 (代表 Big Cap)
    # 取 S&P 600 的前 50 只 (代表 Small Cap)
    target_tickers = sp500[:50] + sp600[:50]
    
    # 去重 (以防万一)
    target_tickers = list(set(target_tickers))
    
    print(f"🚀 本次任务目标: {len(target_tickers)} 只股票 (50 Big + 50 Small)")

    # ==========================================
    # 阶段 2: 下载价格数据 (IBKR)
    # ==========================================
    # 如果你不想每次都重新下载 IBKR 价格，可以把下面这段代码注释掉
    print("\n=== 阶段 2: 下载价格数据 (IBKR) ===")
    ib = IB()
    try:
        print(f"🔌 正在连接 IBKR (端口 {IB_PORT})...")
        ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID)

        # 创建合约对象
        # 注意：IBKR 对于 S&P 600 的小票通常也能用 SMART 路由
        contracts = []
        for symbol in target_tickers:
            contracts.append(Stock(symbol, 'SMART', 'USD'))
        
        print("🔍 正在验证合约有效性 (Qualifying)...")
        # 批量验证，IB 会自动填充 conId
        # 这一步可能会剔除掉一些 IBKR 不支持的冷门小票
        qualified_contracts = ib.qualifyContracts(*contracts)
        print(f"✅ 成功验证 {len(qualified_contracts)} 个合约")
        
        # 启动下载
        downloader = DataDownloader(ib)
        # 下载过去 2 年的数据
        downloader.download_history(qualified_contracts, duration='2 Y') 

    except Exception as e:
        print(f"❌ IBKR 连接或下载部分出错: {e}")
    finally:
        ib.disconnect()
        print("🔌 连接已断开")

    # ==========================================
    # 阶段 3: 下载基本面数据 (Yahoo Finance)
    # ==========================================
    print("\n=== 阶段 3: 下载基本面数据 (Yahoo) ===")
    fmp_manager = FMPDataManager() # 虽然名字叫 FMP，但其实我们已经换成了 Yahoo 内核
    
    success_count = 0
    print(f"正在处理 {len(target_tickers)} 只股票的基本面...")
    
    for symbol in target_tickers:
        # 这一步会去 Yahoo 下载历史股本和账面价值
        df_fund = fmp_manager.get_fama_french_fundamentals(symbol)
        
        if df_fund is not None and not df_fund.empty:
            success_count += 1
            # 简单打印进度，不刷屏
            # print(f"✅ {symbol} 获取成功")
        else:
            print(f"⚠️ {symbol} 基本面获取失败")
    
    print(f"✅ 基本面数据处理完成: {success_count}/{len(target_tickers)}")

    # ==========================================
    # 阶段 4: 计算 Fama-French 因子
    # ==========================================
    print("\n=== 阶段 4: 计算 Fama-French 因子 ===")
    engine = FactorEngine()
    
    # 运行引擎
    factors_df = engine.run()
    
    if factors_df is not None and not factors_df.dropna().empty:
        print("✅ 因子计算完成！预览如下:")
        print(factors_df.tail())
        
        # 保存结果
        output_file = DATA_DIR / "my_ff_factors.csv"
        factors_df.to_csv(output_file)
        print(f"📂 因子序列已保存至: {output_file}")
        
        # --- 可视化 ---
        import matplotlib.pyplot as plt
        
        # 计算累积收益率
        cum_factors = (1 + factors_df).cumprod()
        
        plt.figure(figsize=(10, 6))
        # 画 SMB (小盘因子)
        plt.plot(cum_factors.index, cum_factors['SMB'], label='SMB (Small Minus Big)', color='orange', linewidth=2)
        # 画 HML (价值因子)
        plt.plot(cum_factors.index, cum_factors['HML'], label='HML (High Minus Low)', color='purple', linewidth=2)
        
        plt.title('Custom Fama-French Factors (S&P 500 + S&P 600)', fontsize=14)
        plt.xlabel('Date')
        plt.ylabel('Cumulative Return')
        plt.legend()
        plt.grid(True, linestyle='--', alpha=0.5)
        plt.tight_layout()
        plt.show()
    else:
        print("❌ 因子计算结果为空，可能是数据不足或全部为 NaN。")

if __name__ == "__main__":
    main()