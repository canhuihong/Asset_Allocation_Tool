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
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        return self.conn

    def _initialize_db(self):
        """初始化完整的数据库表结构，绝不简化"""
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

        # 因子表 (Fama-French 等) - 这个绝对不能删！
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

    def update_stock_data(self, tickers):
        """
        下载股票数据。
        升级点：强制使用 period="max" 下载全历史，解决回测过短问题。
        """
        conn = self._get_conn()
        logger.info(f"Updating database for {len(tickers)} tickers (Full History)...")
        
        for t in tickers:
            try:
                # 稍微休眠，防止请求过快被 Yahoo 封锁
                time.sleep(0.2)
                
                # ✅ 关键修正：获取所有历史数据，而不是最近 5 年
                hist = yf.Ticker(t).history(period="max")
                
                if hist is None or hist.empty:
                    logger.warning(f"⚠️ No data for {t}")
                    continue
                
                # 移除时区信息，避免数据库存入乱码
                if hist.index.tz is not None:
                    hist.index = hist.index.tz_localize(None)
                
                records = []
                for date, row in hist.iterrows():
                    date_str = date.strftime('%Y-%m-%d')
                    # 优先使用 Adjusted Close，如果没有则用 Close
                    close_price = row.get('Close', 0)
                    records.append((date_str, t, close_price))
                
                if records:
                    conn.executemany(
                        'INSERT OR REPLACE INTO stock_prices (date, ticker, close) VALUES (?, ?, ?)',
                        records
                    )
                    logger.info(f"  -> {t}: Saved {len(records)} days")
                
            except Exception as e:
                logger.error(f"❌ Error updating {t}: {e}")
        
        conn.commit()
        logger.info("✅ Database update complete (Full History).")

    def save_factors(self, factor_df):
        """
        保存因子数据到数据库。
        这是 Phase 4 (FactorEngine) 必须的功能，绝对不能删。
        """
        if factor_df is None or factor_df.empty:
            return
        
        conn = self._get_conn()
        records = []
        
        # 确保列名大写，防止大小写敏感问题
        cols = [c.upper() for c in factor_df.columns]
        factor_df.columns = cols
        
        for date, row in factor_df.iterrows():
            if isinstance(date, str):
                date_str = date
            else:
                date_str = date.strftime('%Y-%m-%d')
            
            # 使用 get 防止某些列不存在报错
            smb = row.get('SMB', None)
            hml = row.get('HML', None)
            mom = row.get('MOM', None)
            mkt = row.get('MKT', None)
            
            records.append((date_str, smb, hml, mom, mkt))
            
        conn.executemany(
            '''INSERT OR REPLACE INTO factors (date, smb, hml, mom, mkt) 
               VALUES (?, ?, ?, ?, ?)''',
            records
        )
        conn.commit()
        logger.info(f"✅ Factors saved to DB. Rows: {len(records)}")

    def get_aligned_data(self, tickers):
        """
        获取对齐后的数据 (价格 + 因子)。
        """
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
            
        # 2. 转宽表 (Pivot)
        df_pivot = df_prices.pivot(index='date', columns='ticker', values='close')
        df_pivot.index = pd.to_datetime(df_pivot.index)
        
        # 3. 读取因子 (尝试 Join)
        try:
            df_factors = pd.read_sql_query("SELECT * FROM factors", conn)
            df_factors['date'] = pd.to_datetime(df_factors['date'])
            df_factors.set_index('date', inplace=True)
        except:
            df_factors = pd.DataFrame()
        
        # 4. 合并 (Left Join 以价格表为主)
        if not df_factors.empty:
            full_df = df_pivot.join(df_factors, how='left')
            # 填充因子空值 (周末或假期可能缺失)
            cols_to_fill = [c for c in ['smb', 'hml', 'mom', 'mkt'] if c in full_df.columns]
            full_df[cols_to_fill] = full_df[cols_to_fill].fillna(0.0)
        else:
            full_df = df_pivot
        
        # 5. 筛选有效列
        available_tickers = [t for t in tickers if t in full_df.columns]
        if not available_tickers:
            return None
            
        # 返回排序后的宽表，不做激进的 dropna，交给 backtest_engine 去清洗
        return full_df.sort_index()

    def close(self):
        if self.conn:
            self.conn.close()