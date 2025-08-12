
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
                    logging.info("配置已从 YAML 文件加载。")

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
            'max_concurrent_analysis': self.max_concurrent_analysis  # 保存并发数配置
        }
        logging.info("正在保存配置到 YAML 文件...")
        with open('config.yaml', 'w', encoding='utf-8') as file:
            yaml.dump(config_data, file, allow_unicode=True)



class FastGTPConfig:
    def __init__(self):
        self.secret_key = "" # API 密钥
        self.url = "" # API URL
        self.gtp_model = "" # 模型名称

    

