import os
import re
import threading
import time
from pathlib import Path
from typing import List, Set, Optional, Tuple
from fnmatch import fnmatch

class GitIgnoreChecker:
    def __init__(self, base_path: str = None):
        """
        初始化 GitIgnoreChecker
        
        Args:
            base_path: 项目根目录路径，如果为None则使用当前工作目录
        """
        self.base_path = os.path.abspath(base_path) if base_path else os.getcwd()
        self.gitignore_path = os.path.join(self.base_path, '.gitignore')
        
        # 缓存相关变量
        self._cache_lock = threading.RLock()  # 可重入锁，支持同一线程多次获取
        self._cached_patterns: Optional[List[str]] = None
        self._cached_gitignore_mtime: Optional[float] = None
        self._cache_expiry_time: float = 0  # 缓存过期时间戳
        self._cache_ttl: int = 300  # 缓存有效期5分钟（300秒）
    
    def is_ignored(self, file_path: str) -> bool:
        """
        检查文件路径是否被.gitignore规则忽略
        
        Args:
            file_path: 要检查的文件路径（可以是绝对路径或相对于base_path的相对路径）
        
        Returns:
            bool: 如果文件被忽略返回True，否则返回False
        """
        # 获取绝对路径
        abs_file_path = self._get_absolute_path(file_path)
        
        # 获取相对于base_path的路径
        rel_file_path = os.path.relpath(abs_file_path, self.base_path)
        if rel_file_path.startswith('..'):
            # 文件不在项目目录内，不被忽略
            return False
        
        # 获取忽略模式
        ignore_patterns = self._get_ignore_patterns()
        
        # 检查文件是否匹配任何忽略模式
        for pattern in ignore_patterns:
            if self._matches_pattern(rel_file_path, pattern):
                return True
        
        return False
    
    def _get_ignore_patterns(self) -> List[str]:
        """
        获取.gitignore中的忽略模式，支持缓存和线程安全
        
        Returns:
            List[str]: 处理后的模式列表
        """
        # 检查.gitignore文件是否存在
        if not os.path.exists(self.gitignore_path):
            return []
        
        current_time = time.time()
        
        # 首先检查缓存是否有效（无锁读取，性能优化）
        if (self._cached_patterns is not None and 
            current_time < self._cache_expiry_time):
            # 检查文件是否已修改
            try:
                current_mtime = os.path.getmtime(self.gitignore_path)
                if current_mtime == self._cached_gitignore_mtime:
                    return self._cached_patterns
            except (OSError, FileNotFoundError):
                # 文件可能被删除，继续重新读取
                pass
        
        # 获取锁并重新检查（双重检查锁定模式）
        with self._cache_lock:
            # 再次检查，避免多个线程同时等待锁时重复读取
            current_time = time.time()
            if (self._cached_patterns is not None and 
                current_time < self._cache_expiry_time):
                try:
                    current_mtime = os.path.getmtime(self.gitignore_path)
                    if current_mtime == self._cached_gitignore_mtime:
                        return self._cached_patterns
                except (OSError, FileNotFoundError):
                    pass
            
            # 需要重新读取文件
            patterns, mtime = self._read_and_process_gitignore()
            
            # 更新缓存
            self._cached_patterns = patterns
            self._cached_gitignore_mtime = mtime
            self._cache_expiry_time = current_time + self._cache_ttl
            
            return patterns
    
    def _read_and_process_gitignore(self) -> Tuple[List[str], float]:
        """
        读取并处理.gitignore文件（线程安全，在锁内调用）
        
        Returns:
            Tuple[List[str], float]: (模式列表, 文件修改时间)
        """
        try:
            # 获取文件修改时间
            mtime = os.path.getmtime(self.gitignore_path)
            
            # 读取文件内容（使用二进制读取避免编码问题）
            with open(self.gitignore_path, 'rb') as f:
                content = f.read()
            
            # 尝试解码（优先使用UTF-8，失败时使用系统默认编码）
            try:
                content_str = content.decode('utf-8')
            except UnicodeDecodeError:
                content_str = content.decode('latin-1')  # 回退到latin-1
            
            gitignore_rules = content_str.splitlines()
            
            # 处理.gitignore规则
            patterns = self._process_gitignore_rules(gitignore_rules)
            
            return patterns, mtime
            
        except (OSError, FileNotFoundError) as e:
            # 文件不存在或无法读取
            print(f"警告: 无法读取.gitignore文件: {e}")
            return [], 0
    
    def _process_gitignore_rules(self, rules: List[str]) -> List[str]:
        """
        处理.gitignore规则，转换为标准化的模式
        
        Args:
            rules: .gitignore文件中的规则行
        
        Returns:
            List[str]: 处理后的模式列表
        """
        patterns = []
        
        for line in rules:
            # 移除行尾的换行符和空格
            line = line.strip()
            
            # 跳过空行和注释
            if not line or line.startswith('#'):
                continue
            
            # 处理否定模式（以!开头的模式）
            if line.startswith('!'):
                # 这里我们只处理忽略模式，否定模式需要更复杂的逻辑
                # 为了简化，我们暂时跳过否定模式
                continue
            
            # 移除前导和尾随的斜杠（如果有）
            if line.startswith('/'):
                line = line[1:]
            if line.endswith('/'):
                line = line[:-1]
            
            patterns.append(line)
        
        return patterns
    
    def _get_absolute_path(self, file_path: str) -> str:
        """
        获取文件的绝对路径
        
        Args:
            file_path: 文件路径（绝对或相对）
        
        Returns:
            str: 绝对路径
        """
        if os.path.isabs(file_path):
            return os.path.normpath(file_path)
        else:
            return os.path.normpath(os.path.join(self.base_path, file_path))
    
    def _matches_pattern(self, file_path: str, pattern: str) -> bool:
        """
        检查文件路径是否匹配给定的gitignore模式
        
        Args:
            file_path: 相对文件路径
            pattern: gitignore模式
        
        Returns:
            bool: 如果匹配返回True，否则返回False
        """
        # 处理目录匹配
        if pattern.endswith('/'):
            pattern = pattern[:-1]
        
        # 如果模式包含路径分隔符，需要精确匹配路径
        if '/' in pattern:
            # 完整路径匹配
            if fnmatch(file_path, pattern):
                return True
            
            # 目录内容匹配：如果模式是目录，匹配该目录下的所有内容
            if fnmatch(file_path, pattern + '/*') or fnmatch(file_path, pattern + '/**'):
                return True
        else:
            # 单级模式，匹配任何级别的该名称
            if fnmatch(os.path.basename(file_path), pattern):
                return True
            
            # 对于目录，匹配任何级别的该目录名
            path_parts = file_path.split(os.sep)
            for part in path_parts:
                if fnmatch(part, pattern):
                    return True
        
        return False
    
    def get_ignore_patterns(self) -> List[str]:
        """
        获取当前所有忽略模式（用于调试）
        
        Returns:
            List[str]: 所有忽略模式
        """
        return self._get_ignore_patterns()
    
    def refresh(self):
        """
        强制刷新.gitignore规则缓存
        """
        with self._cache_lock:
            self._cached_patterns = None
            self._cached_gitignore_mtime = None
            self._cache_expiry_time = 0
    
    def set_cache_ttl(self, ttl_seconds: int):
        """
        设置缓存TTL（秒）
        
        Args:
            ttl_seconds: 缓存有效期（秒）
        """
        with self._cache_lock:
            self._cache_ttl = ttl_seconds
            # 立即使当前缓存过期
            self._cache_expiry_time = 0
    
    def get_cache_info(self) -> dict:
        """
        获取缓存信息（用于监控和调试）
        
        Returns:
            dict: 缓存状态信息
        """
        with self._cache_lock:
            return {
                'has_cache': self._cached_patterns is not None,
                'cache_size': len(self._cached_patterns) if self._cached_patterns else 0,
                'cache_expiry': self._cache_expiry_time,
                'time_until_expiry': max(0, self._cache_expiry_time - time.time()),
                'ttl_seconds': self._cache_ttl
            }
        
# 示例用法
if __name__ == "__main__":
    # 创建检查器实例
    checker = GitIgnoreChecker("D:\\go\\src\\pr2\\security_portal")
    
    # 检查文件是否被忽略
    test_files = [
        "app/security_api/cmd/api/__debug.txt",
        "app/security_api/security_api",
        "app/security_api/security_job11",
        "vendor/ccc/a.txt"
    ]
    
    for file_path in test_files:
        is_ignored = checker.is_ignored(file_path)
        print(f"文件 {file_path} 是否被忽略: {is_ignored}")
    
    # 获取所有忽略模式（用于调试）
    print("\n所有忽略模式:", checker.get_ignore_patterns())