import akshare as ak
import pandas as pd

def get_stock_returns(symbol="AAPL", start_date="20240101"):
    """
    获取美股数据并计算日收益率
    """
    print(f">> 正在获取 {symbol} 的数据...")
    
    # 1. 获取数据 (注意：AkShare 的 symbol 不需要加后缀，直接用代码)
    df = ak.stock_us_daily(symbol=symbol, adjust="qfq")
    
    # 2. 简单的清洗：确保按日期排序
    df.sort_values("date", inplace=True)
    df.set_index("date", inplace=True)
    
    # 3. 计算收益率：(今天收盘价 - 昨天收盘价) / 昨天收盘价
    df['ret'] = df['close'].pct_change()
    
    # 4. 删除第一行空值 (因为第一天没有前一天的数据)
    df.dropna(subset=['ret'], inplace=True)
    
    return df[['close', 'ret']]

if __name__ == "__main__":
    # 自我测试
    data = get_stock_returns()
    print(data.head())