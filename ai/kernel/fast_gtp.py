from ai.kernel import Kernel
import requests 
from config.config import FastGTPConfig
import logging
class FastGTP(Kernel):
    def __init__(self, config:FastGTPConfig):
        self.config = config

    def get_headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Authorization": "Bearer {}".format(self.config.secret_key)
        }      

    def answer(self, question:str, retry_count=0) -> str:
        # sleep 10秒
        # import time
        # logging.info("answer")
        # time.sleep(5)
        # return "测试"
        try:
            data = {
                "model": self.config.gtp_model,
                "messages": [
                    {
                        "role": "user",
                        "content": question
                    }
                ],
                "stream": False,
            }
            logging.info("开始分析")
            # proxies = {
            #     'http': 'socks5://xxxx:10080',
            #     'https': 'socks5://xxxx:10080',
            # }
            response = requests.post(self.config.url, 
                                    headers=self.get_headers(), 
                                    json=data, 
                                    #  proxies=proxies
                                    timeout=300,
                                    )
            logging.info("分析完成:{}".format(response.status_code))
            if response.status_code != 200:
                if retry_count < 3:
                    return self.answer(question, retry_count+1)
                return "当前网络拥挤，请稍后再试: {}".format(response.text)
            else:
                return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logging.info("请求异常:{}".format(e))
            return "当前网络拥挤，请稍后再试。"
    
    def is_valid(self, question:str) -> bool:
        return True
    
    def name(self) -> str:
        return "FastGTP"

