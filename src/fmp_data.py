import pandas as pd
import logging
import time
import random
import yfinance as yf
from src.config import FUNDAMENTAL_DIR

logger = logging.getLogger("PYL.fmp_data")

class FMPDataManager:
    """
    Yahoo Finance Downloader (Robust Version).
    Designed to be slow but safe to avoid Rate Limits.
    """
    
    def __init__(self):
        # 不需要 API Key
        pass

    def get_fama_french_fundamentals(self, symbol, force_update=False):
        """
        Download Balance Sheet data via yfinance.
        """
        local_path = FUNDAMENTAL_DIR / f"{symbol}_fundamentals.csv"
        
        # 1. 优先读取本地缓存
        if local_path.exists() and not force_update:
            try:
                df = pd.read_csv(local_path, parse_dates=['date'])
                if not df.empty and 'book_value' in df.columns:
                    return df
            except Exception:
                pass 

        # 2. 从 Yahoo 下载 (慢速模式)
        return self._download_yahoo_safe(symbol, local_path)

    def _download_yahoo_safe(self, symbol, save_path):
        logger.info(f"Downloading fundamentals for {symbol} (Yahoo)...")
        
        # 随机延时
        sleep_time = random.uniform(3, 6)
        time.sleep(sleep_time)

        max_retries = 2
        for attempt in range(max_retries):
            # ==========================================
            # 🔴 你的报错就在这里：try 后面必须跟 except
            # ==========================================
            try:
                # 修复 ticker 格式
                yf_sym = symbol.replace(' ', '-')
                ticker = yf.Ticker(yf_sym)
                
                # 获取资产负债表
                bs = ticker.balance_sheet.T
                
                if bs.empty:
                    if attempt < max_retries - 1:
                        logger.warning(f"{symbol} data empty, waiting 10s to retry...")
                        time.sleep(10)
                        continue
                    else:
                        logger.warning(f"No balance sheet found for {symbol}")
                        return None

                # 查找“股东权益”
                target_col = None
                candidates = ['Stockholders Equity', 'Total Stockholder Equity', 'Total Equity Gross Minority Interest', 'Total Equity', 'Common Stock Equity']
                
                for col in bs.columns:
                    col_str = str(col)
                    if any(c in col_str for c in candidates):
                        target_col = col
                        break
                
                if not target_col:
                    logger.warning(f"Could not find 'Equity' column for {symbol}")
                    return None
                
                # 获取股本
                shares = ticker.info.get('sharesOutstanding', 0)
                if not shares: shares = 1
                
                # 组装数据
                df = pd.DataFrame()
                df['date'] = bs.index
                df['book_value'] = bs[target_col].values
                df['shares'] = shares 
                df['symbol'] = symbol
                
                df['date'] = pd.to_datetime(df['date'])
                df = df.sort_values('date').dropna()
                
                if not df.empty:
                    df.to_csv(save_path, index=False)
                    logger.info(f"Saved {symbol} fundamentals.")
                    return df
                
            except Exception as e:
                # 🔴 这就是你缺失的部分
                if "Too Many Requests" in str(e):
                    logger.warning("Yahoo Rate Limit hit! Sleeping 30s...")
                    time.sleep(30)
                else:
                    logger.warning(f"Error downloading {symbol}: {e}")
                
        return None