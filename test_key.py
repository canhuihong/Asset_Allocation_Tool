# test_key.py
import requests
from src.config import FMP_API_KEY

print(f"当前使用的 Key: {FMP_API_KEY}")

# 测试最简单的接口
url = f"https://financialmodelingprep.com/api/v3/profile/AAPL?apikey={FMP_API_KEY}"
resp = requests.get(url)

if resp.status_code == 200:
    print("✅ 成功！Key 是有效的，数据下载功能已恢复。")
elif resp.status_code == 401:
    print("❌ 失败：401 Unauthorized。Key 依然无效，请检查是否粘贴正确。")
else:
    print(f"⚠️ 其他错误: {resp.status_code}")