import time
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import logging

class DirectoryWatcher:
    def __init__(self, path, callback, recursive=True, file_types=None):
        """
        :param path: 要监听的目录路径
        :param callback: 回调函数，当文件修改时调用
        :param recursive: 是否递归监听子目录
        :param file_types: 要监听的文件类型列表，例如 ['.txt', '.log']，None 表示全部文件
        """
        self.path = path
        self.recursive = recursive
        self.file_types = file_types
        self.observer = Observer()
        self.callback = callback  # 新增回调函数
        logging.info(f"初始化监控器: 路径={path}, 递归={recursive}, 文件类型={file_types}")  # 调试信息

    class _Handler(FileSystemEventHandler):
        def __init__(self, file_types, callback):
            self.file_types = file_types
            self.callback = callback

        def _match_type(self, file_path):
            if not self.file_types:
                return True
            return any(file_path.lower().endswith(ext.lower()) for ext in self.file_types)

        def on_modified(self, event):
            if not event.is_directory and self._match_type(event.src_path):
                logging.info(f"文件被修改: {event.src_path}")
                try:
                    with open(event.src_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    # 调用回调函数，传递文件路径和内容
                    if self.callback:
                        self.callback(event.src_path, content)
                except Exception as e:
                    logging.info(f"读取文件失败: {e}")

    def start(self):
        handler = self._Handler(self.file_types, self.callback)
        self.observer.schedule(handler, self.path, recursive=self.recursive)
        self.observer.start()
        logging.info(f"开始监听目录: {self.path}（递归: {self.recursive}）")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        self.observer.stop()
        self.observer.join()
        logging.info("监听已停止")

if __name__ == "__main__":
    def callback(file_path, content):
        logging.info(f"回调函数被调用，文件: {file_path}")
        # logging.info("文件内容:", content)
    # 示例1：监听 D:/test 目录，递归所有子目录，监听全部文件
    watcher = DirectoryWatcher("D:\\go\\src\\pr2\\security_portal", callback, recursive=True,file_types=[".go"])
    watcher.start()