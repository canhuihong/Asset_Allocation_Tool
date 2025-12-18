import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# ==========================================
# 1. 基础路径配置 (核心修正)
# ==========================================
# 获取项目的根目录
# 兼容写法：ROOT_DIR 是老代码用的，PROJECT_ROOT 是新代码用的
ROOT_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = ROOT_DIR 

# 定义数据目录
DATA_DIR = ROOT_DIR / "data"

# 🌟 新增：定义输出目录 (这是 main.py 报错缺失的那个)
OUTPUT_DIR = ROOT_DIR / "outputs"

# 自动创建目录
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ==========================================
# 2. 网络代理设置 (全局强制生效)
# ==========================================
# 填入你的 Clash/v2ray 端口
PROXY_PORT = 7897

os.environ["HTTP_PROXY"] = f"http://127.0.0.1:{PROXY_PORT}"
os.environ["HTTPS_PROXY"] = f"http://127.0.0.1:{PROXY_PORT}"

# ==========================================
# 3. 日志配置 (保留你原来的设置)
# ==========================================
# Load environment variables
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
# 4. 旧变量保留区 (防止 ImportError)
# ==========================================
# 这些是你原来 config.py 里的变量，其他没改的模块可能在用，绝对不能删！

IB_HOST = os.getenv("IB_HOST", "127.0.0.1")
IB_PORT = int(os.getenv("IB_PORT", "4001"))
IB_CLIENT_ID = int(os.getenv("IB_CLIENT_ID", "1"))

FMP_API_KEY = os.getenv("FMP_API_KEY")
if not FMP_API_KEY:
    raise ValueError("⚠️ 请在 .env 文件中配置 FMP_API_KEY")
FMP_BASE_URL = "https://financialmodelingprep.com/api/v3"

SP500_TICKERS_FILE = DATA_DIR / "sp500_tickers.csv"
FUNDAMENTAL_DIR = DATA_DIR / "fundamentals"
os.makedirs(FUNDAMENTAL_DIR, exist_ok=True)

PORTFOLIO_FILE = DATA_DIR / "my_portfolio.csv"
IMAGES_DIR = OUTPUT_DIR # 防止 reporting.py 找 IMAGES_DIR

if __name__ == "__main__":
    print(f"✅ Config Loaded.")
    print(f"📂 ROOT_DIR:   {ROOT_DIR}")
    print(f"📂 OUTPUT_DIR: {OUTPUT_DIR}")
    print(f"🔑 FMP Key:    {FMP_API_KEY}")