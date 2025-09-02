import time
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import logging
import subprocess
import threading
from monitor.gitignore import GitIgnoreChecker
from config.config import Config

class DirectoryWatcher:
    def __init__(self, config:Config, path, callback, recursive=True, file_types=None):
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
        self.git_lock = threading.Lock()
        self.git_ignore_checker = GitIgnoreChecker(base_path=path)
        self.config = config
        logging.info(f"初始化监控器: 路径={path}, 递归={recursive}, 文件类型={file_types}")  # 调试信息

    class _Handler(FileSystemEventHandler):
        def __init__(self, git_ignore_checker:GitIgnoreChecker, config:Config, path, file_types, callback, git_lock: threading.Lock = None):
            self.file_types = file_types
            self.callback = callback
            self.path = path
            self.git_changes = []  # 用于存储 git 变更文件列表
            self.last_get_git_changes_time = 0  # 上次获取 git 变更的时间戳
            self.get_git_changes_interval = 2  # 获取 git 变更的时间间隔（秒）
            self.is_git_repo = True  # 是否是 git 仓库
            self.git_lock = git_lock # 用于保护 git 状态的锁
            self.config = config
            self.git_ignore_checker = git_ignore_checker

        def _match_type(self, file_path):
            if not self.file_types:
                return True
            return any(file_path.lower().endswith(ext.lower()) for ext in self.file_types)

        def on_modified(self, event):
            if not event.is_directory and self._match_type(event.src_path):
                git_changes, is_git = self._get_git_changes()
                file_name = os.path.basename(event.src_path)
                # 如果是 git 仓库且文件不在变更列表中，则忽略
                if is_git and file_name not in git_changes:
                    return
                if self.config.ignore_gitignore and self.git_ignore_checker.is_ignored(event.src_path):
                    return
                try:
                    with open(event.src_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    # 调用回调函数，传递文件路径和内容
                    if self.callback:
                        self.callback(event.src_path, content)
                except Exception as e:
                    logging.info(f"读取文件失败: {e}")

        # 返还变更文件,以及是否是git目录            
        def _get_git_changes(self):
            """
            获取当前 git 变更的文件列表
            :return: (changes, is_git_repo)
                    changes: list[str] 变更文件路径列表
                    is_git_repo: bool 是否是 git 仓库
            """
            # 先检查是否在时间间隔内，避免不必要的锁竞争
            current_time = time.time()
            if (self.is_git_repo and 
                current_time - self.last_get_git_changes_time < self.get_git_changes_interval):
                return self.git_changes, True
            
            # 获取锁
            with self.git_lock:
                # 再次检查，因为可能在等待锁的时候已经有其他线程更新了
                current_time = time.time()
                if (self.is_git_repo and 
                    current_time - self.last_get_git_changes_time < self.get_git_changes_interval):
                    return self.git_changes, True
                    
                if not self.is_git_repo:
                    return [], False
                
                try:
                    # 检查是否是 git 仓库
                    result = subprocess.run(
                        ["git", "rev-parse", "--is-inside-work-tree"],
                        cwd=self.path,
                        capture_output=True,
                        text=True,
                        creationflags=subprocess.CREATE_NO_WINDOW,  # Windows: 不创建窗口
                    )
                    if result.returncode != 0 or result.stdout.strip() != "true":
                        self.is_git_repo = False
                        return [], False  # 不是 git 仓库
                        
                    # 获取变更文件
                    status_result = subprocess.run(
                        ["git", "status", "--porcelain"],
                        cwd=self.path,
                        capture_output=True,
                        text=True,
                        creationflags=subprocess.CREATE_NO_WINDOW,  # Windows: 不创建窗口
                    )
                    output = status_result.stdout.strip()
                    if not output:
                        self.git_changes = []
                        self.last_get_git_changes_time = current_time
                        return [], True  # 是 git 仓库，但没有变更
                        
                    ll = output.split("\n")
                    changes = []
                    for line in ll:
                        change_path = line.strip()[2:]
                        if change_path:
                            # 解析到文件名
                            changes.append(os.path.basename(change_path))
                    self.git_changes = changes
                    self.last_get_git_changes_time = current_time
                    return changes, True
                except Exception as e:
                    logging.error(f"获取 Git 状态失败: {e}")
                    return [], False

        def get_gitignore_ignored_files(self):
            """
            获取 .gitignore 忽略的文件列表, 从根目录下的 .gitignore 文件读取
            :return: list[str] 忽略的文件路径列表
            """
            gitignore_path = os.path.join(self.path, ".gitignore")
            if not os.path.exists(gitignore_path):
                return []
            try:
                with open(gitignore_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                ignored_files = [line.strip() for line in lines if line.strip() and not line.startswith("#")]
                return ignored_files
            except Exception as e:
                logging.error(f"读取 .gitignore 失败: {e}")
                return []

    def start(self):
        handler = self._Handler(self.git_ignore_checker, self.config, self.path, self.file_types, self.callback, self.git_lock)
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