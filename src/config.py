import os
from pathlib import Path

# ==========================================
# 🚀 强制开启代理 (解决 Yahoo/FMP 连不上的问题)
# 请根据你的实际情况修改端口号 (比如 7890 或 10809)
# ==========================================
PROXY_PORT = "7897"  # <--- 请确认这里的数字！
os.environ["HTTP_PROXY"] = f"http://127.0.0.1:{PROXY_PORT}"
os.environ["HTTPS_PROXY"] = f"http://127.0.0.1:{PROXY_PORT}"
print(f"🌍 已配置网络代理: 127.0.0.1:{PROXY_PORT}")

# ... (后面是你原有的 ROOT_DIR 等代码) ...
ROOT_DIR = Path(__file__).parent.parent
# ...

# 获取项目根目录的绝对路径
ROOT_DIR = Path(__file__).parent.parent
DATA_DIR = ROOT_DIR / "data"

# 确保 data 目录存在
os.makedirs(DATA_DIR, exist_ok=True)

# IBKR 连接配置
IB_HOST = "127.0.0.1"
IB_PORT = 4001        # 模拟盘 7497, 实盘 7496
IB_CLIENT_ID = 1

# 文件存储路径
SP500_TICKERS_FILE = DATA_DIR / "sp500_tickers.csv"

# FMP API 配置
FMP_API_KEY = "LCsyRfa75rhROP4mw3gJjv0oUM8yRDoV"
FMP_BASE_URL = "https://financialmodelingprep.com/api/v3"

# 基本面数据存储路径
FUNDAMENTAL_DIR = DATA_DIR / "fundamentals"
import os
os.makedirs(FUNDAMENTAL_DIR, exist_ok=True)