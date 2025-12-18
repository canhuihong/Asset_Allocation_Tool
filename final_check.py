import sys
import os
import traceback

print("🔍 全系统自检开始...\n")

def check_step(name):
    print(f"👉 检查 {name}...", end=" ")

# 1. 检查库
try:
    check_step("第三方库")
    import jinja2
    import pandas_datareader
    import scipy
    print("✅ 通过")
except ImportError as e:
    print(f"❌ 失败! 缺库: {e.name}")
    print(f"   请运行: pip install {e.name}")
    sys.exit()

# 2. 检查数据库内容
try:
    check_step("数据库内容")
    from src.data_manager import DataManager
    db = DataManager()
    # 检查 main.py 需要的 4 只股票
    df = db.get_aligned_data(['AAPL', 'MSFT', 'JPM', 'NVDA'])
    if df is None or df.empty:
        print("❌ 失败! 数据库里没有 AAPL/MSFT/JPM/NVDA 的数据。")
        print("   请务必先运行 python init_data.py")
        sys.exit()
    print(f"✅ 通过 (发现 {len(df)} 行数据)")
except Exception as e:
    print(f"❌ 数据库读取出错: {e}")
    sys.exit()

# 3. 模拟 main.py 启动
print("\n🚀 环境完美！尝试启动主程序...\n")
try:
    import main
    main.main()
except Exception:
    print("\n💥 主程序崩溃！详细报错如下 (请把下面这段发给我):")
    print("="*40)
    traceback.print_exc()
    print("="*40)