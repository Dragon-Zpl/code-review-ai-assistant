import os
import sys
import logging
from config.config import Config
from app.app import App
import tkinter as tk

def setup_logging(log_level):
    """设置日志记录"""
    valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
    if log_level.upper() not in valid_levels:
        log_level = 'INFO'  # 设置默认值
    log_level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stderr)
        ]
    )
    logging.info("日志系统已初始化，日志级别: %s", logging.getLevelName(log_level))

def main():
    try:
        config = Config()
        config.load_from_yaml()
        setup_logging(config.log_level)
        
        # 创建并运行GUI应用
        root = tk.Tk()
        app = App(root)
        root.mainloop()
    except Exception as e:
        # 使用基本日志记录（避免动态内容泄露）
        logging.error("应用初始化失败: %s", str(e).replace('%', '%%'))  # 防止日志注入
        sys.exit(1)  # 安全退出
    finally:
        if 'root' in locals():  # 仅检查变量是否存在，不检查对象状态
            logging.info("应用已关闭")
    
# pyinstaller -w -F -n "Code Review AI Assistant" -i icon.ico --collect-data=ntwork main.py
if __name__ == "__main__":
    main()