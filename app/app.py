import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from config.config import Config
from ai.kernel.fast_gtp import FastGTP
from monitor.file import DirectoryWatcher
import queue
import time
import logging

class App:
    def __init__(self, root:tk.Tk):
        self.root = root
        self.root.title("Code Review AI Assistant")
        self.root.geometry("1000x600")
        # self.root.iconbitmap("background.png")
        # 应用现代主题
        # 加载配置
        self.config = Config()
        self.config.load_from_yaml()
        
        # 创建FastGTP实例
        self.fast_gtp = FastGTP(self.config.fast_gtp_config)
        
        # 存储文件路径和对应的分析结果
        self.file_analysis = {}  # {file_path: {"content": str, "status": str, "answer": str}}
        
        # 并发控制设置 - 从配置获取最大并发数
        self.max_concurrent_analysis = self.config.max_concurrent_analysis
        self.analysis_queue = queue.Queue()  # 待分析任务队列
        self.active_analysis = {}  # 当前活跃的分析任务 {file_path: threading.Event}
        self.analysis_workers = []  # 分析工作线程列表
        self.running = True  # 控制工作线程的运行
        self.analysis_paused = False  # 新增：控制分析是否暂停
        
        # 启动分析工作线程
        self.start_analysis_workers()
        
        # 创建UI
        self.create_widgets()
        
        self.add_author_info()

        # 启动监控线程
        self.start_monitoring()
    
    def add_author_info(self):
        """在右下角添加作者信息"""
        author_label = ttk.Label(
            self.root, 
            text="Developed by Ployal",
            font=("Arial", 8, "italic"),
            foreground="#666666"
        )
        author_label.place(relx=0.02, rely=0.98, anchor=tk.SW)  # 修改为左下角

    def add_popup_author_info(self, window):
        """在弹出窗口右下角添加作者信息"""
        author_label = ttk.Label(
            window, 
            text="Developed by Ployal",
            font=("Arial", 8, "italic"),
            foreground="#666666"
        )
        author_label.place(relx=0.02, rely=0.98, anchor=tk.SW)  # 修改为左下角

    def create_widgets(self):
        # 创建左右分栏
        paned_window = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned_window.pack(fill=tk.BOTH, expand=True)
        # 左侧配置面板
        config_frame = ttk.LabelFrame(paned_window, text="配置设置")
        paned_window.add(config_frame, weight=1)
        
        # 右侧监控面板
        monitor_frame = ttk.Frame(paned_window)
        paned_window.add(monitor_frame, weight=2)
        
        # 填充配置面板
        self.create_config_ui(config_frame)
        
        # 填充监控面板
        self.create_monitor_ui(monitor_frame)
    
    def create_config_ui(self, parent):
        # 使用网格布局
        row = 0
        
        # 日志级别
        ttk.Label(parent, text="日志级别:").grid(row=row, column=0, padx=5, pady=5, sticky=tk.W)
        self.log_level = tk.StringVar(value=self.config.log_level)
        log_combo = ttk.Combobox(parent, textvariable=self.log_level, 
                               values=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        log_combo.grid(row=row, column=1, padx=5, pady=5, sticky=tk.EW)
        row += 1
        
        # FastGTP配置
        ttk.Label(parent, text="FastGTP 配置").grid(row=row, column=0, columnspan=2, pady=10)
        row += 1
        
        ttk.Label(parent, text="Secret Key:").grid(row=row, column=0, padx=5, pady=5, sticky=tk.W)
        self.secret_key = tk.StringVar(value=self.config.fast_gtp_config.secret_key)
        ttk.Entry(parent, textvariable=self.secret_key, show="*").grid(row=row, column=1, padx=5, pady=5, sticky=tk.EW)
        row += 1
        
        ttk.Label(parent, text="API URL:").grid(row=row, column=0, padx=5, pady=5, sticky=tk.W)
        self.api_url = tk.StringVar(value=self.config.fast_gtp_config.url)
        ttk.Entry(parent, textvariable=self.api_url).grid(row=row, column=1, padx=5, pady=5, sticky=tk.EW)
        row += 1
        
        ttk.Label(parent, text="GPT模型:").grid(row=row, column=0, padx=5, pady=5, sticky=tk.W)
        self.gpt_model = tk.StringVar(value=self.config.fast_gtp_config.gtp_model)
        ttk.Entry(parent, textvariable=self.gpt_model).grid(row=row, column=1, padx=5, pady=5, sticky=tk.EW)
        row += 1
        
        # 监控路径
        ttk.Label(parent, text="监控路径:").grid(row=row, column=0, padx=5, pady=5, sticky=tk.W)
        self.monitor_path = tk.StringVar(value=self.config.monitor_project_path)
        path_frame = ttk.Frame(parent)
        path_frame.grid(row=row, column=1, padx=5, pady=5, sticky=tk.EW)
        ttk.Entry(path_frame, textvariable=self.monitor_path).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(path_frame, text="浏览...", command=self.browse_path).pack(side=tk.RIGHT)
        row += 1
        
        # 文件类型配置
        ttk.Label(parent, text="监听文件类型:").grid(row=row, column=0, padx=5, pady=5, sticky=tk.W)
        file_types_str = ",".join(self.config.file_types) if self.config.file_types else ""
        self.file_types_var = tk.StringVar(value=file_types_str)
        ttk.Entry(parent, textvariable=self.file_types_var).grid(row=row, column=1, padx=5, pady=5, sticky=tk.EW)
        row += 1
        
        # 并发控制设置 - 修改为从配置获取
        ttk.Label(parent, text="并发分析数:").grid(row=row, column=0, padx=5, pady=5, sticky=tk.W)
        self.max_concurrent = tk.IntVar(value=self.config.max_concurrent_analysis)
        ttk.Spinbox(parent, from_=1, to=10, textvariable=self.max_concurrent).grid(row=row, column=1, padx=5, pady=5, sticky=tk.W)
        row += 1
        
        # 按钮区域
        button_frame = ttk.Frame(parent)
        button_frame.grid(row=row, column=0, columnspan=2, pady=10)
        
        ttk.Button(button_frame, text="保存配置", command=self.save_config).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="重启监控", command=self.restart_monitoring).pack(side=tk.LEFT, padx=5)
        
        # 设置列权重
        parent.columnconfigure(1, weight=1)
    
    def create_monitor_ui(self, parent):
        # 创建主框架
        main_frame = ttk.Frame(parent)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建Treeview显示文件列表
        columns = ("file", "status")
        self.tree = ttk.Treeview(main_frame, columns=columns, show="headings", selectmode="browse")
        
        # 设置列标题
        self.tree.heading("file", text="文件路径")
        self.tree.heading("status", text="状态")
        
        # 设置列宽
        self.tree.column("file", width=500, anchor=tk.W)
        self.tree.column("status", width=100, anchor=tk.CENTER)
        
        # 添加标签样式
        self.tree.tag_configure('urgent', background='#ffeeee', foreground='red')  # 浅红背景 + 红色文字
        self.tree.tag_configure('new', background="#ecec34")  # 浅黄背景
        self.tree.tag_configure('completed', background="#14e914")  # 浅绿背景
        

        # 添加滚动条
        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # 布局
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 添加操作按钮框架
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 添加查看和删除按钮
        ttk.Button(button_frame, text="查看分析", command=self.show_selected_analysis).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="删除记录", command=self.delete_selected_record).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="清除所有", command=self.clear_all_records).pack(side=tk.LEFT, padx=5)
        self.toggle_button = ttk.Button(button_frame, text="暂停分析", command=self.toggle_analysis)
        self.toggle_button.pack(side=tk.RIGHT, padx=5)
        
        # 状态标签 - 移除"等待更新"计数
        self.status_var = tk.StringVar(value="状态: 运行中 | 活跃任务: 0 | 队列: 0")
        ttk.Label(button_frame, textvariable=self.status_var).pack(side=tk.RIGHT, padx=10)
        
        # 绑定双击事件
        self.tree.bind("<Double-1>", self.show_analysis)
    
    def browse_path(self):
        from tkinter import filedialog
        path = filedialog.askdirectory()
        if path:
            self.monitor_path.set(path)
    
    def save_config(self):
        # 更新配置对象
        self.config.log_level = self.log_level.get()
        self.config.fast_gtp_config.secret_key = self.secret_key.get()
        self.config.fast_gtp_config.url = self.api_url.get()
        self.config.fast_gtp_config.gtp_model = self.gpt_model.get()
        self.config.monitor_project_path = self.monitor_path.get()
        self.config.max_concurrent_analysis = self.max_concurrent.get()  # 保存并发数配置
        
        # 处理文件类型配置
        file_types_str = self.file_types_var.get()
        self.config.file_types = [ext.strip() for ext in file_types_str.split(",") if ext.strip()]
        
        # 保存到YAML
        self.config.save_to_yaml()
        messagebox.showinfo("保存成功", "配置已保存到config.yaml")
        
        # 重启工作线程以应用新的并发数
        self.restart_workers()
    
    def restart_workers(self):
        """重启工作线程以应用新的并发数"""
        # 停止当前工作线程
        self.running = False
        for _ in range(len(self.analysis_workers)):
            self.analysis_queue.put(None)  # 发送停止信号
        
        # 等待工作线程结束
        for worker in self.analysis_workers:
            if worker.is_alive():
                worker.join(timeout=1)
        
        # 重置状态
        self.running = True
        self.analysis_workers = []
        self.active_analysis = {}
        self.analysis_paused = False
        
        # 更新最大并发数
        self.max_concurrent_analysis = self.config.max_concurrent_analysis
        logging.info(f"重启工作线程，新的最大并发数: {self.max_concurrent_analysis}")
        # 启动新的工作线程
        self.start_analysis_workers()
    
    def start_analysis_workers(self):
        """启动分析工作线程"""
        for i in range(self.max_concurrent_analysis):
            worker = threading.Thread(
                target=self.analysis_worker,
                daemon=True
            )
            worker.start()
            self.analysis_workers.append(worker)
    
    def analysis_worker(self):
        """分析工作线程函数"""
        while self.running:
            try:
                # 从队列获取任务
                file_path = self.analysis_queue.get(timeout=1)
                if file_path is None:  # 停止信号
                    break
                
                # 检查记录是否已被删除
                if file_path not in self.file_analysis:
                    self.analysis_queue.task_done()
                    continue
                
                # 创建停止事件
                stop_event = threading.Event()
                self.active_analysis[file_path] = stop_event
                self.update_status()
                
                try:
                    # 等待直到分析恢复
                    while self.analysis_paused and self.running:
                        time.sleep(0.1)
                    # 更新状态为分析中
                    self.root.after(0, self.update_analysis_status, file_path, "分析中")
                    
                    # 如果分析被中断，直接跳过
                    if stop_event.is_set() or not self.running:
                        continue
                    
                    # 获取文件内容
                    content = self.file_analysis[file_path]["content"]
                    
                    # 调用FastGTP分析内容（带中断检查）
                    question = """
                    请帮我review这段代码, 找出的明显代码缺陷(不用跨文件分析,只对当前代码进行分析)
                    重点:
                        1. 功能性缺陷（逻辑错误、边界条件未处理、计算错误）  
                        2. 可靠性缺陷（未处理异常、资源泄露、竞态条件）  
                        3. 安全性缺陷 (SQL 注入、命令注入、硬编码密钥等）  
                        4. 可维护性缺陷（拼写错误、魔法数字、重复代码）  
                        5. 性能缺陷（不必要的循环、未优化的数据结构）
                    要求:
                        - 仅分析当前代码，不考虑调用外部函数会产生的问题  
                        - 只针对真实且有显著影响的问题 
                        - 允许回答“没有明显问题”
                        - 不要编造或过度推测潜在风险
                        - 不要对函数的参数过渡判断, 尤其是项目内部的函数的出入参
                        - 不要对函数的返参(除err以外)未处理参数为nil的情况进行判断
                        - 不要考虑数字类型溢出的问题
                        - 代码内常量的使用如在文件内没提供可能是在同目录下的其他文件内，不要过渡推测

                    并严格按照下面的格式回答我：
                    代码中存在X个明显的安全问题:
                    然后按照顺序列出每个问题描述以及优化方案, 使用markdown格式。
                    代码如下:
                    ```
                    {}
                    ```
                    """.format(content)          
                    # 使用带中断检查的分析方法
                    answer = self.safe_analyze_content(question, stop_event)
                    
                    # 如果分析被中断，直接跳过
                    if stop_event.is_set():
                        continue
                    
                    problem_count = -1
                    # 更新分析结果
                    if file_path in self.file_analysis:  # 确保记录仍然存在
                        self.file_analysis[file_path]["answer"] = answer
                        self.file_analysis[file_path]["status"] = "分析完成"
                        # 解析答案中的问题数量
                        if "代码中存在" in answer:
                            try:
                                problem_count = int(answer.split("代码中存在")[1].split("个明显的")[0].strip())
                            except ValueError:
                                pass
                    # 更新UI状态
                    self.root.after(0, self.update_analysis_status, file_path, "分析完成", problem_count)
                except Exception as e:
                    if file_path in self.file_analysis and not stop_event.is_set():
                        error_msg = f"分析失败: {str(e)}"
                        self.file_analysis[file_path]["answer"] = error_msg
                        self.file_analysis[file_path]["status"] = "分析失败"
                        self.root.after(0, self.update_analysis_status, file_path, "分析失败")
                finally:
                    # 清理活跃任务
                    if file_path in self.active_analysis:
                        del self.active_analysis[file_path]
                    
                    # 更新状态
                    self.update_status()
                    
                    # 标记任务完成
                    self.analysis_queue.task_done()
            except queue.Empty:
                # 队列为空时继续等待
                continue
    
    def safe_analyze_content(self, question, stop_event):
        """带中断检查的分析方法"""
        # 在实际应用中，这里应该调用可中断的API
        # 为简化实现，我们使用普通调用
        # 在真实环境中，可以使用异步请求并定期检查stop_event
        if stop_event.is_set():
            return "分析已取消"
        
        # 实际调用分析API
        return self.fast_gtp.answer(question)
    
    def update_status(self):
        """更新状态栏信息"""
        active_count = len(self.active_analysis)
        queue_size = self.analysis_queue.qsize()
        status_text = "暂停" if self.analysis_paused else "运行中"
        status = f"状态: {status_text} | 活跃任务: {active_count} | 队列: {queue_size}"
        self.root.after(0, lambda: self.status_var.set(status))
    
    def toggle_analysis(self):
        """切换分析状态（运行/暂停）"""
        self.analysis_paused = not self.analysis_paused
        if self.analysis_paused:
            self.toggle_button.config(text="继续分析")
        else:
            self.toggle_button.config(text="暂停分析")
        self.update_status()
    
    def start_monitoring(self):
        # 确保监控路径有效
        path = self.config.monitor_project_path
        if not path or not os.path.isdir(path):
            logging.info(f"无效的监控路径: {path}")
            return
        
        # 处理文件类型配置
        file_types = self.config.file_types if self.config.file_types else None
        
        # 启动监控线程
        self.monitor_thread = threading.Thread(
            target=self.run_monitor, 
            args=(path, file_types),
            daemon=True
        )
        self.monitor_thread.start()
    
    def run_monitor(self, path, file_types):
        self.watcher = DirectoryWatcher(
            path=path,
            callback=self.file_modified_callback,
            recursive=True,
            file_types=file_types
        )
        self.watcher.start()
    
    def restart_monitoring(self):
        # 先停止现有监控
        if hasattr(self, 'watcher'):
            self.watcher.stop()
        
        # 更新配置
        self.config.monitor_project_path = self.monitor_path.get()
        self.config.save_to_yaml()
        
        # 重新启动监控
        self.start_monitoring()
        messagebox.showinfo("重启成功", "文件监控已重启")
    
    def file_modified_callback(self, file_path, content):
        # 在UI线程中更新文件列表
        self.root.after(0, self.update_file_list, file_path, content)
    
    def update_file_list(self, file_path, content):
        # 检查是否已有该文件记录
        if file_path in self.file_analysis:
            # 如果文件正在分析中或等待分析中，忽略新事件
            if (file_path in self.active_analysis or 
                self.file_analysis[file_path]["status"] in ["等待分析", "分析中"]):
                logging.info(f"文件 {file_path} 正在处理中，忽略新事件")
                return
            
            # 更新现有记录
            self.file_analysis[file_path]["content"] = content
            self.file_analysis[file_path]["status"] = "新变更"
            
            # 更新Treeview
            for item in self.tree.get_children():
                if self.tree.item(item, "values")[0] == file_path:
                    self.tree.item(item, values=(file_path, "● 新变更"))
                    break
            
            # 将任务添加到分析队列
            self.analysis_queue.put(file_path)
            self.update_status()
            
            # 更新状态为等待分析
            self.update_analysis_status(file_path, "等待分析")
        else:
            # 创建新记录
            self.file_analysis[file_path] = {
                "content": content,
                "status": "新变更",
                "answer": None
            }
            
            # 添加到Treeview，使用 'urgent' 标签
            item_id = self.tree.insert("", "end", values=(file_path, "● 新变更"), tags=('urgent',))
            
            # 将任务添加到分析队列
            self.analysis_queue.put(file_path)
            self.update_status()
            
            # 更新状态为等待分析
            self.update_analysis_status(file_path, "等待分析")
    
    def update_analysis_status(self, file_path, status, problem_count=-1):
        """更新文件分析状态"""
        # 如果文件记录已经被删除，则不更新
        if file_path not in self.file_analysis:
            return

        self.file_analysis[file_path]["status"] = status
        
        # 更新Treeview状态
        for item in self.tree.get_children():
            if self.tree.item(item, "values")[0] == file_path:
                display_text = status
                tags = ()
                
                if status == "新变更":
                    display_text = "● 新变更"
                    tags = ('new',)  # 红色感叹号 + 红色背景
                elif status == "等待分析":
                    display_text = "等待中...❗"  # 添加红色感叹号
                    tags = ('new',)
                elif status == "分析中":
                    display_text = "分析中...❗"  # 添加红色感叹号
                    tags = ('new',)
                elif status == "分析完成":
                    if problem_count > 0:
                        display_text = f"分析完成, 发现{problem_count}个潜在安全问题❗"
                        tags = ('urgent',)
                    elif problem_count == 0:
                        display_text = "分析完成, 代码很健全✅"
                        tags = ('completed',)  # 绿色背景表示已完成
                    else:
                        display_text = "分析完成❗"  # 添加红色感叹号
                        tags = ('urgent',)
                elif status == "分析失败":
                    display_text = "分析失败❗"  # 添加红色感叹号
                    tags = ('urgent',)
                elif status == "已查看":
                    display_text = "已查看"
                    tags = ('completed',)  # 绿色背景表示已完成
                
                # 更新Treeview项
                self.tree.item(item, values=(file_path, display_text), tags=tags)
                break
        
        self.update_status()
    
    def show_selected_analysis(self):
        """显示选中记录的分析结果"""
        selected = self.tree.selection()
        if selected:
            self.show_analysis(None)
    
    def show_analysis(self, event):
        """显示分析结果"""
        # 获取选中的文件路径
        selected = self.tree.selection()
        if not selected:
            return
            
        item = selected[0]
        file_path = self.tree.item(item, "values")[0]
        
        # 检查是否有分析结果
        if file_path not in self.file_analysis or not self.file_analysis[file_path]["answer"]:
            messagebox.showinfo("提示", "该文件尚未完成分析")
            return
        
        # 读取文件内容
        with open(file_path, 'r', encoding='utf-8') as f:
            file_content = f.read()

        # 从字典获取分析结果
        analysis = self.file_analysis[file_path]["answer"]
        
        # 创建弹出窗口
        popup = tk.Toplevel(self.root)
        popup.title(f"分析结果 - {os.path.basename(file_path)}")
        popup.geometry("800x500")
        
         # 添加作者信息到弹出窗口
        self.add_popup_author_info(popup)

        # 创建主框架
        main_frame = ttk.Frame(popup)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 创建分栏
        paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)
        
        # 左侧代码文本区域
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)

        # 添加查找功能框架
        search_frame = ttk.Frame(left_frame)
        search_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(search_frame, text="查找:").pack(side=tk.LEFT)
        search_entry = ttk.Entry(search_frame)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        search_entry.bind("<Return>", lambda e: self.find_in_text(text_source, search_entry.get()))
        
        ttk.Button(search_frame, text="查找", 
                command=lambda: self.find_in_text(text_source, search_entry.get())).pack(side=tk.LEFT)
        
        ttk.Label(left_frame, text="代码").pack(pady=5)
        text_source = scrolledtext.ScrolledText(left_frame, wrap=tk.WORD)
        text_source.pack(fill=tk.BOTH, expand=True)
        text_source.insert(tk.END, file_content)
        text_source.config(state=tk.DISABLED)
        
        text_source.bind("<Control-f>", lambda e: search_entry.focus())

        # 右侧Markdown预览区域
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=1)
        
        ttk.Label(right_frame, text="优化建议").pack(pady=5)
        text_preview = scrolledtext.ScrolledText(
            right_frame,
            wrap=tk.WORD,
            font=("Arial", 10),
            padx=10,
            pady=10
        )
        text_preview.pack(fill=tk.BOTH, expand=True)
        
        # 应用Markdown样式
        self.apply_markdown_styles(text_preview, analysis)
        text_preview.config(state=tk.DISABLED)
        
        # 添加关闭按钮
        ttk.Button(main_frame, text="关闭", command=popup.destroy).pack(pady=10)
        
        # 更新状态为已查看
        self.file_analysis[file_path]["status"] = "已查看"
        
        # 更新Treeview项为已完成样式
        for item in self.tree.get_children():
            if self.tree.item(item, "values")[0] == file_path:
                # 移除红色感叹号
                self.tree.item(item, values=(file_path, "已查看"), tags=('completed',))
                break

    def find_in_text(self, text_widget, search_str):
        """在文本组件中查找字符串"""
        if not search_str:
            return
        
        # 取消之前的高亮
        text_widget.tag_remove("found", "1.0", tk.END)
        
        # 如果为空字符串，直接返回
        if not search_str.strip():
            return
        
        # 从当前光标位置开始搜索
        start_pos = text_widget.index(tk.INSERT)
        idx = text_widget.search(search_str, start_pos, stopindex=tk.END)
        
        # 如果没找到，从头开始搜索
        if not idx:
            idx = text_widget.search(search_str, "1.0", stopindex=tk.END)
        
        # 如果找到，高亮显示并滚动到该位置
        if idx:
            end_pos = f"{idx}+{len(search_str)}c"
            text_widget.tag_add("found", idx, end_pos)
            text_widget.tag_config("found", background="yellow")
            text_widget.see(idx)
            text_widget.mark_set(tk.INSERT, end_pos)
            text_widget.focus()
        
    def apply_markdown_styles(self, text_widget, content):
        """应用Markdown样式到文本组件"""
        text_widget.config(state=tk.NORMAL)
        text_widget.delete(1.0, tk.END)
        
        # 添加内容并应用样式
        text_widget.insert(tk.END, content)
        
        # 标题样式
        for level in range(1, 6):
            start = 1.0
            while True:
                # 查找标题
                start = text_widget.search(f"{'#' * level} ", start, stopindex=tk.END)
                if not start:
                    break
                    
                end = text_widget.search("\n", start, stopindex=tk.END) or tk.END
                if not end:
                    break
                    
                # 应用样式
                size = 24 - (level * 2)
                text_widget.tag_add(f"h{level}", start, f"{end}-1c")
                text_widget.tag_config(f"h{level}", font=("Arial", size, "bold"))
                
                start = end
        
        # 加粗文本
        start = 1.0
        while True:
            start = text_widget.search("**", start, stopindex=tk.END)
            if not start:
                break
                
            end = text_widget.search("**", f"{start}+2c", stopindex=tk.END)
            if not end:
                break
                
            # 应用样式
            text_widget.tag_add("bold", f"{start}+2c", end)
            text_widget.tag_config("bold", font=("Arial", 10, "bold"))
            
            # 删除标记符号
            text_widget.delete(end, f"{end}+2c")
            text_widget.delete(start, f"{start}+2c")
            
            start = end
        
        # 斜体文本
        start = 1.0
        while True:
            start = text_widget.search("*", start, stopindex=tk.END)
            if not start:
                break
                
            end = text_widget.search("*", f"{start}+1c", stopindex=tk.END)
            if not end:
                break
                
            # 应用样式
            text_widget.tag_add("italic", f"{start}+1c", end)
            text_widget.tag_config("italic", font=("Arial", 10, "italic"))
            
            # 删除标记符号
            text_widget.delete(end, f"{end}+1c")
            text_widget.delete(start, f"{start}+1c")
            
            start = end
        
        # 代码块
        start = 1.0
        while True:
            start = text_widget.search("```", start, stopindex=tk.END)
            if not start:
                break
                
            end = text_widget.search("```", f"{start}+3c", stopindex=tk.END)
            if not end:
                break
                
            # 应用样式
            text_widget.tag_add("code", f"{start}+3c", end)
            text_widget.tag_config("code", 
                                font=("Courier New", 10),
                                background="#f0f0f0",
                                relief="solid",
                                borderwidth=1)
            
            # 删除标记符号
            text_widget.delete(end, f"{end}+3c")
            text_widget.delete(start, f"{start}+3c")
            
            start = end
        
        # 列表项
        start = 1.0
        while True:
            start = text_widget.search("- ", start, stopindex=tk.END)
            if not start:
                break
                
            end = text_widget.search("\n", start, stopindex=tk.END) or tk.END
            
            # 应用样式
            text_widget.tag_add("list", start, end)
            text_widget.tag_config("list", lmargin1=20, lmargin2=30)
            
            start = end
        
        # 引用
        start = 1.0
        while True:
            start = text_widget.search("> ", start, stopindex=tk.END)
            if not start:
                break
                
            end = text_widget.search("\n", start, stopindex=tk.END) or tk.END
            
            # 应用样式
            text_widget.tag_add("blockquote", start, end)
            text_widget.tag_config("blockquote", 
                                background="#f9f9f9",
                                lmargin1=20,
                                borderwidth=1,
                                relief="solid",
                                # padding=5,
                                )
            
            # 删除标记符号
            text_widget.delete(start, f"{start}+2c")
            
            start = end

    def delete_selected_record(self):
        """删除选中的记录"""
        selected = self.tree.selection()
        if not selected:
            return
            
        for item in selected:
            # 添加删除动画效果
            self.tree.item(item, tags=('urgent',))
            self.tree.item(item, values=(self.tree.item(item, "values")[0], "删除中..."))
            self.root.update()
            time.sleep(0.2)  # 短暂延迟，让用户看到删除效果
            file_path = self.tree.item(item, "values")[0]
            
            # 如果文件正在分析中，发送停止信号
            if file_path in self.active_analysis:
                self.active_analysis[file_path].set()
            
            # 从数据结构中删除
            if file_path in self.file_analysis:
                del self.file_analysis[file_path]
            
            # 从Treeview删除
            self.tree.delete(item)
        
        self.update_status()
    
    def clear_all_records(self):
        """清除所有记录"""
        if not messagebox.askyesno("确认", "确定要清除所有记录吗？"):
            return
            
        # 停止所有活跃的分析任务
        for stop_event in self.active_analysis.values():
            stop_event.set()
        
        # 添加清除动画效果
        for item in self.tree.get_children():
            self.tree.item(item, tags=('urgent',))
            self.tree.item(item, values=(self.tree.item(item, "values")[0], "清除中..."))
        
        self.root.update()
        time.sleep(0.3)  # 短暂延迟，让用户看到清除效果
        # 清空数据结构
        self.file_analysis.clear()
        
        # 清空Treeview
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        self.update_status()
    
    def on_closing(self):
        """窗口关闭时清理资源"""
        self.running = False
        
        # 停止所有活跃的分析任务
        for stop_event in self.active_analysis.values():
            stop_event.set()
        
        # 停止文件监控
        if hasattr(self, 'watcher'):
            self.watcher.stop()
        
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()