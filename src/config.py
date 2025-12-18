import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# ==========================================
# 1. 基础路径配置
# ==========================================
# 获取项目的根目录
ROOT_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = ROOT_DIR 

# 定义数据目录
DATA_DIR = ROOT_DIR / "data"

# 定义输出目录
OUTPUT_DIR = ROOT_DIR / "outputs"

# 自动创建目录
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ==========================================
# 2. 网络代理设置
# ==========================================
# 优先读取环境变量，如果没有则使用默认值 7897
PROXY_PORT = int(os.getenv("PROXY_PORT", 7897))

# 只有在确实需要代理时才设置环境变量（防止干扰本地服务）
# 如果你需要强制开启，可以取消下面两行的注释：
# os.environ["HTTP_PROXY"] = f"http://127.0.0.1:{PROXY_PORT}"
# os.environ["HTTPS_PROXY"] = f"http://127.0.0.1:{PROXY_PORT}"

# ==========================================
# 3. 业务配置 (统一黑名单) - ✅ 新增核心部分
# ==========================================
# A. 指数 ETF、大盘指数、债券 ETF 等非个股资产
ETF_BLOCKLIST = [
    'SPY', 'QQQ', 'TLT', 'GLD', 'IWM', 'USDOLLAR', '^GSPC', '^VIX', '^IXIC',
    'IVV', 'VOO', 'AGG', 'BND', 'LQD', 'HYG', 'EEM', 'EFA', 'SLV', 'USO',
    'SHY', 'IEF', 'TIP', 'VNQ', 'XLK', 'XLF', 'XLV', 'XLE', 'XLY', 'XLP'
]

# B. 宏观经济指标 (避免被误读为股票)
MACRO_BLOCKLIST = [
    'DGS10', 'T5YIE', 'T10Y2Y', 'BAMLC0A0CM', # 利率/信用
    'VIXCLS', 'DCOILWTICO', 'DTWEXBGS',       # VIX/油/美元
    'CPIAUCSL', 'M2SL', 'UNRATE', 'DGS3MO'    # 通胀/货币/其他
]

# C. 合并后的完整排除列表 (供 Optimizer 和 Backtest 使用)
FULL_BLOCKLIST = list(set(ETF_BLOCKLIST + MACRO_BLOCKLIST))

# ==========================================
# 4. 日志配置
# ==========================================
load_dotenv()

logger = logging.getLogger("PYL")
logger.setLevel(logging.INFO)

# Console handler
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# ==========================================
# 5. API 与旧变量保留区
# ==========================================
IB_HOST = os.getenv("IB_HOST", "127.0.0.1")
IB_PORT = int(os.getenv("IB_PORT", "4001"))
IB_CLIENT_ID = int(os.getenv("IB_CLIENT_ID", "1"))

FMP_API_KEY = os.getenv("FMP_API_KEY")
FMP_BASE_URL = "https://financialmodelingprep.com/api/v3"

SP500_TICKERS_FILE = DATA_DIR / "sp500_tickers.csv"
FUNDAMENTAL_DIR = DATA_DIR / "fundamentals"
os.makedirs(FUNDAMENTAL_DIR, exist_ok=True)

PORTFOLIO_FILE = DATA_DIR / "my_portfolio.csv"
IMAGES_DIR = OUTPUT_DIR 

if __name__ == "__main__":
    print(f"✅ Config Loaded.")
    print(f"📂 ROOT_DIR:   {ROOT_DIR}")
    print(f"🚫 Blocklist Size: {len(FULL_BLOCKLIST)}")