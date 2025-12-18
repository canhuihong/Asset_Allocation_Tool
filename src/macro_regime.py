import logging
import pandas_datareader.data as web
import datetime

logger = logging.getLogger("PYL.macro_regime")

# ✅ 关键修复：类名必须叫 MacroRegime
class MacroRegime:
    def __init__(self):
        pass

    def determine_regime(self):
        try:
            # 简单快速的逻辑，防止卡死
            end = datetime.datetime.now()
            start = end - datetime.timedelta(days=365)
            df = web.DataReader(['DGS10', 'T5YIE'], 'fred', start, end)
            
            if df is None or df.empty: return "Neutral (No Data)"
            
            # 简单的均线逻辑
            rate_trend = df['DGS10'].iloc[-1] > df['DGS10'].mean()
            inf_trend = df['T5YIE'].iloc[-1] > df['T5YIE'].mean()
            
            if rate_trend and inf_trend: return "Reflation"
            if not rate_trend and inf_trend: return "Stagflation"
            if rate_trend and not inf_trend: return "Recovery"
            return "Deflation"
        except Exception as e:
            logger.warning(f"Macro regime failed: {e}")
            return "Neutral (Error)"