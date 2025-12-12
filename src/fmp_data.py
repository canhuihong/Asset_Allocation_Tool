import time
import yfinance as yf
import pandas as pd
from src.config import FUNDAMENTAL_DIR

class FMPDataManager:
    """
    (注：类名保留没改，方便兼容 main.py，实际底层已换成 Yahoo Finance)
    负责获取个股的财务数据：
    1. 账面价值 (Book Value) -> 来自资产负债表
    2. 流通股本 (Shares Outstanding) -> 用于计算市值
    """
    
    def __init__(self):
        # yfinance 不需要 API Key
        pass
        
    def get_fama_french_fundamentals(self, symbol, force_update=False):
        """
        获取构建 FF 因子所需的关键数据。
        Yahoo Finance 免费版通常能提供最近 4-5 年的年报。
        """
        # 针对 yfinance 的 ticker 格式修正 (比如 BRK B -> BRK-B)
        yf_symbol = symbol.replace(' ', '-')
        local_path = FUNDAMENTAL_DIR / f"{symbol}_fundamentals.csv"
        
        # 1. 缓存检查
        if local_path.exists() and not force_update:
            # print(f"📦 加载本地缓存: {symbol}")
            return pd.read_csv(local_path, parse_dates=['date'])
            
        print(f"🌐 (Yahoo) 正在下载基本面数据: {symbol} ...")
        
        try:
            # 2. 调用 yfinance
            stock = yf.Ticker(yf_symbol)
            
            # 获取资产负债表 (Balance Sheet) - 年频
            # yfinance 返回的表格：列是日期，行是科目
            bs = stock.balance_sheet.T # 转置一下，变成 日期 x 科目
            
            if bs.empty:
                print(f"⚠️ {symbol} 暂无财务数据 (Yahoo源)")
                return None
            
            # 3. 提取 股东权益 (Total Stockholder Equity)
            # Yahoo 的字段名通常叫 "Stockholders Equity" 或 "Total Stockholder Equity"
            target_col = None
            possible_names = ['Stockholders Equity', 'Total Stockholder Equity', 'Total Equity Gross Minority Interest']
            
            for name in possible_names:
                if name in bs.columns:
                    target_col = name
                    break
            
            if not target_col:
                print(f"❌ {symbol} 找不到股东权益字段")
                return None
                
            # 4. 提取 流通股本 (Shares Outstanding)
            # yfinance 的 shares 只有当前的，历史 shares 很难找。
            # 替代方案：用 "Ordinary Shares Number" 字段 (如果有)
            # 如果没有，我们暂时用当前的 shares 倒推 (这是免费数据的妥协)
            shares_col = 'Ordinary Shares Number'
            if shares_col not in bs.columns:
                # 如果财报里没写股本，就用当前股本填充 (虽然不严谨，但为了跑通项目先这样)
                current_shares = stock.info.get('sharesOutstanding', 0)
                bs['shares'] = current_shares
            else:
                bs['shares'] = bs[shares_col]

            # 5. 数据清洗
            df = pd.DataFrame()
            df['date'] = bs.index
            df['book_value'] = bs[target_col].values
            df['shares'] = bs['shares'].values
            df['symbol'] = symbol
            
            # 这里的市值 Market Cap 我们需要自己算：Price * Shares
            # 但由于这里是“年报日”，我们可以简单存储 shares，留给 factor_engine 去结合每日股价算市值
            # 为了兼容之前的逻辑，我们这里暂不存 marketCap，或者存一个占位符
            # 在 factor_engine 里，我们会用 (Close Price * Shares) 来计算每日动态市值
            
            # 保存
            df.sort_values('date', inplace=True)
            df.to_csv(local_path, index=False)
            
            # 礼貌性休眠
            time.sleep(0.5)
            
            return df

        except Exception as e:
            print(f"❌ 处理 {symbol} 失败: {e}")
            return None