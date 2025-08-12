import os
import sys
import logging
from config.config import Config
from app.app import App
import tkinter as tk

def setup_logging(log_level):
    """设置日志记录"""
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
    """主函数"""
    # 加载配置
    config = Config()
    config.load_from_yaml()
    
    # 设置日志
    setup_logging(config.log_level)
    
    # 创建并运行GUI应用
    root = tk.Tk()
    app = App(root)
    root.mainloop()
    
# pyinstaller -F --collect-data=ntwork main.py
if __name__ == "__main__":
    main()