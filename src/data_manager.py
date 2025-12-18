import sqlite3
import pandas as pd
import logging
import yfinance as yf
import time
from pathlib import Path
from src.config import DATA_DIR

logger = logging.getLogger("PYL.data_manager")

class DataManager:
    def __init__(self, db_name="quant_lab.db"):
        self.db_path = DATA_DIR / db_name
        self.conn = None
        self._initialize_db()

    def _get_conn(self):
        if self.conn is None:
            # check_same_thread=False 允许在不同线程中使用连接
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        return self.conn

    def _initialize_db(self):
        """初始化完整的数据库表结构"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # 股票价格表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_prices (
            date TEXT,
            ticker TEXT,
            close REAL,
            PRIMARY KEY (date, ticker)
        )
        ''')

        # 因子表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS factors (
            date TEXT PRIMARY KEY,
            smb REAL,
            hml REAL,
            mom REAL,
            mkt REAL
        )
        ''')
        conn.commit()

    def get_all_tickers_in_db(self):
        """
        ✅ 新增接口：获取数据库中所有存在的 Ticker 列表 (原始列表)
        上层模块不再需要自己写 SQL SELECT DISTINCT...
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT ticker FROM stock_prices")
            tickers = [row[0] for row in cursor.fetchall()]
            return tickers
        except Exception as e:
            logger.error(f"Failed to fetch tickers from DB: {e}")
            return []

    def update_stock_data(self, tickers):
        """下载股票数据 (全历史)"""
        conn = self._get_conn()
        logger.info(f"Updating database for {len(tickers)} tickers (Full History)...")
        
        for t in tickers:
            try:
                time.sleep(0.1) # 简单防封
                hist = yf.Ticker(t).history(period="max")
                
                if hist is None or hist.empty:
                    logger.warning(f"⚠️ No data for {t}")
                    continue
                
                # 移除时区信息
                if hist.index.tz is not None:
                    hist.index = hist.index.tz_localize(None)
                
                records = []
                for date, row in hist.iterrows():
                    date_str = date.strftime('%Y-%m-%d')
                    close_price = row.get('Close', 0)
                    records.append((date_str, t, close_price))
                
                if records:
                    conn.executemany(
                        'INSERT OR REPLACE INTO stock_prices (date, ticker, close) VALUES (?, ?, ?)',
                        records
                    )
            except Exception as e:
                logger.error(f"❌ Error updating {t}: {e}")
        
        conn.commit()
        logger.info("✅ Database update complete.")

    def save_factors(self, factor_df):
        """保存因子数据"""
        if factor_df is None or factor_df.empty:
            return
        
        conn = self._get_conn()
        records = []
        
        # 标准化列名
        cols = [c.upper() for c in factor_df.columns]
        factor_df.columns = cols
        
        for date, row in factor_df.iterrows():
            date_str = date if isinstance(date, str) else date.strftime('%Y-%m-%d')
            records.append((
                date_str, 
                row.get('SMB'), row.get('HML'), row.get('MOM'), row.get('MKT')
            ))
            
        conn.executemany(
            '''INSERT OR REPLACE INTO factors (date, smb, hml, mom, mkt) 
               VALUES (?, ?, ?, ?, ?)''',
            records
        )
        conn.commit()
        logger.info(f"✅ Factors saved to DB. Rows: {len(records)}")

    def get_aligned_data(self, tickers):
        """获取对齐后的宽表数据 (Close + Factors)"""
        conn = self._get_conn()
        
        # 1. 批量读取价格
        placeholders = ','.join(['?'] * len(tickers))
        query = f"SELECT date, ticker, close FROM stock_prices WHERE ticker IN ({placeholders})"
        
        try:
            df_prices = pd.read_sql_query(query, conn, params=tickers)
        except Exception as e:
            logger.error(f"SQL Error: {e}")
            return None
        
        if df_prices.empty:
            return None
            
        # 2. 转宽表
        df_pivot = df_prices.pivot(index='date', columns='ticker', values='close')
        df_pivot.index = pd.to_datetime(df_pivot.index)
        
        # 3. 读取并合并因子
        try:
            df_factors = pd.read_sql_query("SELECT * FROM factors", conn)
            df_factors['date'] = pd.to_datetime(df_factors['date'])
            df_factors.set_index('date', inplace=True)
        except:
            df_factors = pd.DataFrame()
        
        if not df_factors.empty:
            full_df = df_pivot.join(df_factors, how='left')
            cols_to_fill = [c for c in ['smb', 'hml', 'mom', 'mkt'] if c in full_df.columns]
            full_df[cols_to_fill] = full_df[cols_to_fill].fillna(0.0)
        else:
            full_df = df_pivot
        
        # 4. 排序返回
        return full_df.sort_index()

    def close(self):
        if self.conn:
            self.conn.close()