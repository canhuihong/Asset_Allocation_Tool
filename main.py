import sys
import os
import logging
import datetime
import pandas as pd  # 记得确保导入 pandas
from pathlib import Path

# 引入各个模块
from src.config import DATA_DIR, OUTPUT_DIR
from src.data_manager import DataManager 
from src.macro_regime import MacroRegime
from src.portfolio_analyzer import PortfolioAnalyzer
from src.macro_engine import MacroEngine
from src.backtest_engine import BacktestEngine
from src.optimizer import PortfolioOptimizer
from src.reporting import ReportManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("PYL.Main")

def load_portfolio_from_csv(file_path):
    """
    从 CSV 文件读取持仓配置
    格式要求: 两列，表头为 Ticker, Weight
    """
    if not os.path.exists(file_path):
        logger.warning(f"⚠️ Portfolio file not found: {file_path}")
        logger.warning("-> Falling back to default Hardcoded Portfolio.")
        return None

    try:
        df = pd.read_csv(file_path)
        # 简单清洗：去空格，大写
        df['Ticker'] = df['Ticker'].astype(str).str.strip().str.upper()
        
        # 转换成字典 {Ticker: Weight}
        portfolio = dict(zip(df['Ticker'], df['Weight']))
        
        # 检查权重之和
        total_weight = sum(portfolio.values())
        if abs(total_weight - 1.0) > 0.05:
            logger.warning(f"⚠️ Warning: Portfolio weights sum to {total_weight:.2f}, not 1.0")
            
        logger.info(f"✅ Loaded portfolio from {file_path} ({len(portfolio)} assets)")
        return portfolio
        
    except Exception as e:
        logger.error(f"❌ Failed to read portfolio CSV: {e}")
        return None

def main():
    logger.info("==========================================")
    logger.info("🚀 Starting Quant Macro Lab (Engineering Mode)")
    logger.info("==========================================")
    
    # 0. 准备输出目录
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_dir = OUTPUT_DIR / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)
    
    reporter = ReportManager(run_dir)
    logger.info(f"📂 Output Directory: {run_dir}")
    
    # ==========================================
    # Phase 0: 宏观周期
    # ==========================================
    logger.info("\n--- Phase 0: Macro Regime Detection ---")
    try:
        mr = MacroRegime()
        regime = mr.determine_regime()
        logger.info(f"✅ Current Regime Detected: [{regime}]")
        reporter.add_text(f"Current Macro Regime: {regime}")
    except Exception as e:
        logger.error(f"❌ Phase 0 Failed: {e}")
        reporter.add_text("Macro Regime: Detection Failed")

    # ==========================================
    # Phase 1: 数据库检查
    # ==========================================
    logger.info("\n--- Phase 1: Data Check ---")
    db_path = DATA_DIR / "quant_lab.db"
    if not db_path.exists():
        logger.critical(f"⛔ Database not found at {db_path}!")
        return

    # ==========================================
    # Phase 2：读取外部配置文件
    # ==========================================
    logger.info("\n--- Phase 2: Getting Portfolio ---")
    try:
        csv_path = DATA_DIR / "my_portfolio.csv"  # 你的文件名
        my_portfolio = load_portfolio_from_csv(csv_path)
    except Exception as e:
        logger.error(f"❌ Phase 2 Portfolio Reading Failed: {e}")
        reporter.add_text("Porfolio Reading: No files")

    # ==========================================
    # Phase 3: 微观归因
    # ==========================================
    logger.info("\n--- Phase 3: Micro Attribution ---")
    try:
        pa = PortfolioAnalyzer()
        fig = pa.rolling_analyze(my_portfolio)
        if fig: reporter.add_figure(fig, "micro_attribution")
    except Exception as e: logger.error(f"Phase 4 Error: {e}")

    # ==========================================
    # Phase 4: 宏观敏感度
    # ==========================================
    logger.info("\n--- Phase 4: Macro Sensitivity ---")
    try:
        me = MacroEngine()
        fig = me.run_analysis(my_portfolio)
        if fig: reporter.add_figure(fig, "macro_sensitivity")
    except Exception as e: logger.error(f"Phase 5 Error: {e}")

    # ==========================================
    # Phase 5: 回测
    # ==========================================
    logger.info("\n--- Phase 5: Full-Market Backtest ---")
    try:
        be = BacktestEngine()
        fig = be.run_backtest("Trend_Following_Plus", top_n=2, min_history_days=750, mom_window=126)
        if fig: reporter.add_figure(fig, "backtest")
    except Exception as e: logger.error(f"Phase 6 Error: {e}")

    # ==========================================
    # Phase 6: 优化
    # ==========================================
    logger.info("\n--- Phase 6: Portfolio Optimization ---")
    try:
        opt = PortfolioOptimizer()
        fig, portfolios = opt.optimize()
        
        if fig: reporter.add_figure(fig, "frontier")
            
        if portfolios:
            logger.info(f"💾 Saving {len(portfolios)} optimized portfolios...")
            for filename, df in portfolios.items():
                reporter.save_data(df, filename)
    except Exception as e: 
        logger.error(f"Phase 7 Error: {e}")

    # ==========================================
    # 结束
    # ==========================================
    path = reporter.generate_html()
    logger.info(f"🎉 Report generated: {path}")
    if os.name == 'nt': 
        try: os.startfile(path)
        except: pass

if __name__ == "__main__":
    main()