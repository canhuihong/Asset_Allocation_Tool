import streamlit as st
import sys
import os
import matplotlib.pyplot as plt

# 🛠️ 关键修复：强行把当前脚本所在的目录加入 Python 搜索路径
# 这样 Streamlit 才能找到同级目录下的 src 文件夹
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

# 导入你的引擎
from src.backtest_engine import BacktestEngine
from src.optimizer import PortfolioOptimizer
from src.macro_regime import MacroRegime

# 设置页面配置
st.set_page_config(page_title="Quant Macro Lab", layout="wide")

st.title("🚀 量化策略指挥中心 (Quant Command)")

# ==========================================
# 侧边栏：控制面板
# ==========================================
st.sidebar.header("⚙️ 策略参数")

# 回测参数
mom_window = st.sidebar.slider("动量窗口 (Momentum Window)", 20, 252, 126, help="计算动量的天数，126天约等于半年。")
top_n = st.sidebar.slider("持仓数量 (Top N)", 1, 20, 5)
min_history = st.sidebar.number_input("最小上市天数", value=750, step=250)

st.sidebar.markdown("---")
st.sidebar.header("🌍 宏观控制")
run_macro = st.sidebar.checkbox("显示宏观周期状态", value=True)

# ==========================================
# 主界面：宏观状态
# ==========================================
if run_macro:
    st.subheader("1. Macro Regime Detection")
    try:
        mr = MacroRegime()
        regime = mr.determine_regime()
        
        # 用不同颜色显示状态
        if "Inflation" in regime:
            st.error(f"🔥 Current Regime: {regime}")
        elif "Deflation" in regime:
            st.info(f"❄️ Current Regime: {regime}")
        else:
            st.success(f"🌱 Current Regime: {regime}")
            
    except Exception as e:
        st.warning(f"宏观模块加载失败: {e}")

# ==========================================
# 主界面：策略回测
# ==========================================
st.subheader("2. Strategy Backtest (Interactive)")

col1, col2 = st.columns([1, 3])

with col1:
    st.markdown("""
    点击下方按钮运行回测。
    你可以实时调整左侧参数，
    观察策略表现变化。
    """)
    run_btn = st.button("▶️ 运行回测", type="primary")

with col2:
    if run_btn:
        with st.spinner("正在扫描全市场数据..."):
            try:
                be = BacktestEngine()
                # 调用回测引擎
                # 注意：BacktestEngine.run_backtest 默认返回 fig
                fig = be.run_backtest(
                    strategy_name=f"Mom_{mom_window}d_Top{top_n}",
                    top_n=top_n, 
                    min_history_days=min_history, 
                    mom_window=mom_window
                )
                
                if fig:
                    st.pyplot(fig)
                else:
                    st.warning("回测未生成图表，可能是数据不足或全部被过滤。")
                    
            except Exception as e:
                st.error(f"❌ 回测运行出错: {e}")
                # 打印详细报错方便调试
                import traceback
                st.code(traceback.format_exc())

# ==========================================
# 主界面：组合优化
# ==========================================
st.markdown("---")
st.subheader("3. Portfolio Optimization")

if st.button("✨ 运行有效前沿优化"):
    with st.spinner("正在进行蒙特卡洛模拟..."):
        try:
            opt = PortfolioOptimizer()
            # optimize 返回 (fig, portfolios)
            fig, portfolios = opt.optimize()
            
            if fig:
                st.pyplot(fig)
            
            if portfolios:
                st.success("优化完成！下载配置建议：")
                cols = st.columns(len(portfolios))
                for idx, (filename, df) in enumerate(portfolios.items()):
                    csv = df.to_csv(index=False).encode('utf-8')
                    cols[idx].download_button(
                        label=f"📥 下载 {filename}",
                        data=csv,
                        file_name=filename,
                        mime='text/csv',
                    )
        except Exception as e:
            st.error(f"❌ 优化运行出错: {e}")
            import traceback
            st.code(traceback.format_exc())