
import os
import logging
import yaml
class Config:
    def __init__(self):
        self.log_level = "DEBUG"  # 日志级别
        self.fast_gtp_config = FastGTPConfig()
        self.monitor_project_path = "" # 监控项目路径
        self.file_types = ['.py', '.go']  # 新增：默认监听的文件类型
        self.max_concurrent_analysis = 3  # 最大并发分析任务数
        self.name = "" # 用户名
        self.ignore_gitignore = False  # 新增：保存.gitignore配置
        self.check_type_list = [] # 检查类型列表

    def load_from_yaml(self):
        if os.path.exists('config.yaml'):
            with open('config.yaml', 'r', encoding='utf-8') as file:
                config_data = yaml.load(file, Loader=yaml.FullLoader)
                if config_data:
                    self.log_level = config_data.get('log_level', "ERROR")
                    self.fast_gtp_config.secret_key = config_data.get('fast_gtp_config', {}).get('secret_key', "")
                    self.fast_gtp_config.url = config_data.get('fast_gtp_config', {}).get('url', "")
                    self.fast_gtp_config.gtp_model = config_data.get('fast_gtp_config', {}).get('gtp_model', "gpt-3.5-turbo")
                    self.monitor_project_path = config_data.get('monitor_project_path', "")
                    self.file_types = config_data.get('file_types', ['.py', '.go'])
                    self.max_concurrent_analysis = config_data.get('max_concurrent_analysis', 3)  # 加载并发数配置
                    self.ignore_gitignore = config_data.get('ignore_gitignore', False)  # 加载.gitignore配置
                    self.check_type_list = config_data.get('check_type_list', [])
                    # 先从配置中加载用户名,  不存在的话或为空的话则生成一个随机的
                    self.name = config_data.get('name', "")
                    if not self.name:
                        self.generate_random_name()
                    logging.info("配置已从 YAML 文件加载。")
        else:
            logging.warning("配置文件 config.yaml 不存在，使用默认配置。")
            self.generate_random_name()

    # 使用uuid生成随机的用户名
    def generate_random_name(self):
        import uuid
        self.name = str(uuid.uuid4())[:8]

    def save_to_yaml(self):
        config_data = {
            'log_level': self.log_level,
            'fast_gtp_config': {
                'secret_key': self.fast_gtp_config.secret_key,
                'url': self.fast_gtp_config.url,
                'gtp_model': self.fast_gtp_config.gtp_model
            },
            'monitor_project_path': self.monitor_project_path,
            'file_types': self.file_types,
            'max_concurrent_analysis': self.max_concurrent_analysis,  # 保存并发数配置
            'name': self.name,
            'ignore_gitignore': self.ignore_gitignore,  # 保存.gitignore配置
            'check_type_list': self.check_type_list
        }
        logging.info("正在保存配置到 YAML 文件...")
        with open('config.yaml', 'w', encoding='utf-8') as file:
            yaml.dump(config_data, file, allow_unicode=True)



class FastGTPConfig:
    def __init__(self):
        self.secret_key = "" # API 密钥
        self.url = "" # API URL
        self.gtp_model = "" # 模型名称

    

