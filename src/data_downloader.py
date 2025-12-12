import os
import time
import pandas as pd
from ib_insync import *
from tqdm import tqdm # 进度条库
from src.config import DATA_DIR

class DataDownloader:
    def __init__(self, ib_conn):
        self.ib = ib_conn
        # 创建一个专门存放价格数据的文件夹
        self.price_dir = DATA_DIR / "prices"
        os.makedirs(self.price_dir, exist_ok=True)

    def download_history(self, contracts, duration='3 Y'):
        """
        批量下载历史数据
        :param contracts: 合约对象列表 (必须先 Qualify)
        :param duration: 下载多长时间的数据，默认 3 年
        """
        print(f"📉 准备下载 {len(contracts)} 只股票的日线数据...")
        print(f"📂 数据将保存在: {self.price_dir}")

        success_count = 0
        failure_list = []

        # 使用 tqdm 创建一个进度条
        for contract in tqdm(contracts, desc="下载进度", unit="股"):
            symbol = contract.symbol
            local_path = self.price_dir / f"{symbol}.csv"

            # 策略：如果本地已经有刚下载的文件，可以选择跳过 (这里为了演示，默认覆盖)
            # if local_path.exists(): continue 

            try:
                # 1. 请求数据
                # whatToShow='ADJUSTED_LAST' 包含除权除息调整，最适合做 Fama-French
                # 如果没有该权限，改回 'TRADES'
                bars = self.ib.reqHistoricalData(
                    contract,
                    endDateTime='',
                    durationStr=duration,
                    barSizeSetting='1 day',
                    whatToShow='ADJUSTED_LAST', 
                    useRTH=True,
                    formatDate=1,
                    keepUpToDate=False
                )

                if bars:
                    # 2. 转为 DataFrame
                    df = util.df(bars)
                    df.set_index('date', inplace=True)
                    
                    # 3. 保存 CSV
                    df.to_csv(local_path)
                    success_count += 1
                else:
                    failure_list.append(symbol)

            except Exception as e:
                # 捕获所有错误，不要让程序崩溃
                failure_list.append(f"{symbol} ({str(e)})")
            
            # --- 关键：防封号休眠 ---
            # IBKR 限制：每秒不能超过 ~50 个请求，但历史数据请求更消耗资源
            # 我们保守一点，每次请求完休息 0.5 到 1 秒
            self.ib.sleep(0.5) 

        # --- 总结报告 ---
        print("\n" + "="*30)
        print(f"✅ 下载完成报告")
        print(f"成功: {success_count} 只")
        print(f"失败: {len(failure_list)} 只")
        if failure_list:
            print("失败列表:", failure_list[:10]) # 只打印前10个
        print("="*30)