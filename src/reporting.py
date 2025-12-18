import os
import datetime
import logging
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
# 这里的 import try-except 是为了兼容性，不要动
try:
    from src.config import OUTPUT_DIR
except ImportError:
    OUTPUT_DIR = Path("outputs")

logger = logging.getLogger("PYL.reporting")

class ReportManager:
    def __init__(self, output_dir=None):
        """
        初始化报告管理器
        :param output_dir: 指定输出目录，如果为None则自动根据时间戳创建
        """
        if output_dir:
            self.report_dir = Path(output_dir)
        else:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            self.report_dir = OUTPUT_DIR / timestamp
        
        # 定义子目录结构
        self.images_dir = self.report_dir / "images"
        self.data_dir = self.report_dir / "data"
        
        # 确保目录存在 (parents=True 意味着如果父目录不存在也会一并创建)
        try:
            self.images_dir.mkdir(parents=True, exist_ok=True)
            self.data_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"📝 Report initialized. Output Path: {self.report_dir}")
        except Exception as e:
            logger.error(f"❌ Failed to create report directories: {e}")
        
        # 初始化 HTML 内容缓冲
        self.html_content = []
        self._init_html()

    def _init_html(self):
        """写入 HTML 头部信息"""
        header = f"""
        <html>
        <head>
            <title>Quant Research Report</title>
            <style>
                body {{ font-family: sans-serif; max-width: 1000px; margin: 0 auto; padding: 20px; }}
                h1 {{ border-bottom: 2px solid #333; padding-bottom: 10px; }}
                img {{ max-width: 100%; height: auto; margin: 20px 0; border: 1px solid #ddd; }}
                .timestamp {{ color: #666; font-size: 0.9em; }}
            </style>
        </head>
        <body>
            <h1>📊 Quant Macro Research Report</h1>
            <p class="timestamp">Generated at: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
            <hr>
        """
        self.html_content.append(header)

    def add_text(self, text):
        """添加普通文本段落"""
        if text:
            self.html_content.append(f"<p>{text}</p>")

    def add_heading(self, text, level=2):
        """添加标题"""
        if text:
            self.html_content.append(f"<h{level}>{text}</h{level}>")

    def add_figure(self, fig, filename_tag):
        """
        保存 Matplotlib 图片并添加到 HTML
        :param fig: Figure 对象
        :param filename_tag: 文件名前缀 (不带后缀)
        """
        if fig is None:
            logger.warning(f"⚠️ add_figure called with None for tag: {filename_tag}")
            return
        
        filename = f"{filename_tag}.png"
        filepath = self.images_dir / filename
        
        try:
            fig.savefig(filepath, bbox_inches='tight', dpi=100)
            plt.close(fig) # 释放内存
            
            # HTML 中使用相对路径
            rel_path = f"images/{filename}"
            self.html_content.append(f"<h3>{filename_tag}</h3>")
            self.html_content.append(f"<img src='{rel_path}' alt='{filename_tag}'>")
            logger.info(f"🖼️  Image saved: {filename}")
        except Exception as e:
            logger.error(f"❌ Failed to save image {filename}: {e}")

    def save_data(self, df, filename):
        """
        保存 DataFrame 到 data 目录 (CSV格式)
        这是最关键的方法，用于保存优化权重。
        """
        if df is None:
            logger.warning(f"⚠️ Attempted to save None DataFrame: {filename}")
            return
            
        if df.empty:
            logger.warning(f"⚠️ Attempted to save Empty DataFrame: {filename}")
            return
        
        # 确保文件名以 .csv 结尾
        if not filename.endswith('.csv'):
            filename += '.csv'
            
        filepath = self.data_dir / filename
        
        try:
            df.to_csv(filepath, index=False)
            logger.info(f"💾 Data saved: {filepath} (Rows: {len(df)})")
        except Exception as e:
            logger.error(f"❌ Failed to save data {filename}: {e}")

    def generate_html(self):
        """生成最终 HTML 文件"""
        self.html_content.append("</body></html>")
        
        report_path = self.report_dir / "report.html"
        try:
            with open(report_path, "w", encoding="utf-8") as f:
                f.write("\n".join(self.html_content))
            return report_path
        except Exception as e:
            logger.error(f"❌ Failed to write HTML report: {e}")
            return None