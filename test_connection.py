from ib_insync import *
import pandas as pd
import matplotlib.pyplot as plt

# --- 1. 连接设置 ---
ib = IB()
# ⚠️ 注意：如果你是模拟账户(Paper)，通常是 7497；实盘是 7496
PORT = 4001 
CLIENT_ID = 3  # 这里的 ID 随便写，别和正在运行的其他脚本重复就行

try:
    print("正在连接 TWS...")
    ib.connect('127.0.0.1', PORT, clientId=CLIENT_ID)
    print("✅ 连接成功！")

    # --- 2. 定义合约 (Contract) ---
    # 我们定义标普500指数。
    # 注意：指数的数据通常需要订阅权限。如果你没有订阅 SPX 数据，
    # 可以尝试把下面的 'SPX' 改为 'SPY' (ETF)，Exchange 改为 'SMART'。
    contract = Index('SPX', 'CBOE', 'USD')
    
    # 稍微“清洗”一下合约，确保 IB 能够识别
    ib.qualifyContracts(contract)
    print(f"正在获取合约数据: {contract.symbol} ...")

    # --- 3. 请求历史数据 ---
    # endDateTime='' 表示直到当前最新时间
    # durationStr='1 Y' 表示取过去 1 年的数据
    # barSizeSetting='1 day' 表示日线
    # whatToShow='TRADES' 表示取实际成交价 (对于指数，有时需用 'MIDPOINT')
    bars = ib.reqHistoricalData(
        contract,
        endDateTime='',
        durationStr='1 Y',
        barSizeSetting='1 day',
        whatToShow='TRADES',
        useRTH=True,        # 只看常规交易时间 (Regular Trading Hours)
        formatDate=1
    )

    if not bars:
        print("❌ 未获取到数据。可能是没有订阅该市场的数据权限。")
        print("建议尝试将代码中的 'SPX' 改为 'SPY' 再试一次。")
    else:
        # --- 4. 数据处理 (转为 DataFrame) ---
        df = util.df(bars)
        
        # 将 date 列设为索引，方便画图
        df.set_index('date', inplace=True)
        
        # 打印前几行看看数据长什么样
        print("\n数据预览 (前 5 行):")
        print(df.head())

        # --- 5. 使用 Matplotlib 画图 ---
        print("\n正在绘图...")
        
        # 设置画布大小和风格
        plt.style.use('seaborn-v0_8') # 设置一个好看的风格
        plt.figure(figsize=(12, 6))
        
        # 画收盘价曲线
        plt.plot(df.index, df['close'], label='SPX Close Price', color='navy', linewidth=1.5)
        
        # 添加图表细节
        plt.title('S&P 500 Historical Price (1 Year)', fontsize=16)
        plt.xlabel('Date', fontsize=12)
        plt.ylabel('Price (USD)', fontsize=12)
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.legend()
        
        # 显示图表
        plt.show()

except Exception as e:
    print(f"❌ 发生错误: {e}")

finally:
    ib.disconnect()
    print("连接已断开。")