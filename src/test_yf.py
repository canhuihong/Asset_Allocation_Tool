import yfinance as yf
import os

# ==========================================
# 🔴 核心步骤：设置代理
# 请根据你的软件修改端口号：Clash=7890, v2ray=10809
# ==========================================
PROXY_PORT = 7897 

os.environ["HTTP_PROXY"] = f"http://127.0.0.1:{PROXY_PORT}"
os.environ["HTTPS_PROXY"] = f"http://127.0.0.1:{PROXY_PORT}"

print(f"🔌 Proxy set to 127.0.0.1:{PROXY_PORT}")
print("Testing download for AMD (with proxy)...")

try:
    ticker = yf.Ticker("AMD")
    # 尝试获取资产负债表
    bs = ticker.balance_sheet
    
    if not bs.empty:
        print("\n✅ Success! Data retrieved:")
        print(bs.iloc[:, :2].head())
    else:
        print("\n❌ Failed: Data is still empty. Try changing the proxy node (US Mode).")
        
except Exception as e:
    print(f"\n❌ Error: {e}")