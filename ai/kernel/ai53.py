from ai.kernel import Kernel
import requests 
import logging

class AI53(Kernel):
    def __init__(self, config:dict):
        self.url = config["url"]
        self.bot_id = config["bot_id"]
        self.secret_key = config["secret_key"]
        self.headers = {
            "Authorization": "Bearer {}".format(self.secret_key),
            "Bot-Id": self.bot_id
        }
    def answer(self, question:str, retry_count=0) -> str:
        data = {
            "conversation_id": "",
            "query": question,
            "user": "liuzimu",
            "response_mode": "blocking",
            "inputs": {},
        }
        """
        {
    "event": "message",
    "task_id": "788334c3-c596-484c-9233-9d3e62fdeb70",
    "id": "1a3a14e9-3c38-41d0-bbab-8b4b432dd74b",
    "message_id": "1a3a14e9-3c38-41d0-bbab-8b4b432dd74b",
    "conversation_id": "983721ad-7278-437a-9449-6cb1d78a9872",
    "mode": "chat",
    "answer": "哎呀，小蜜不知道53AI的官网地址呢，不过你可以试试网上搜索一下，应该能找到的哦~",
    "metadata": {
        "usage": {
            "prompt_tokens": 177,
            "prompt_unit_price": "0.01",
            "prompt_price_unit": "0.001",
            "prompt_price": "0.0017700",
            "completion_tokens": 43,
            "completion_unit_price": "0.03",
            "completion_price_unit": "0.001",
            "completion_price": "0.0012900",
            "total_tokens": 220,
            "total_price": "0.0030600",
            "currency": "USD",
            "latency": 1.999626561999321
        }
    },
    "created_at": 1724752607
}
        """
        response = requests.post(self.url, 
                                 headers=self.headers, 
                                 json=data, 
                                #  proxies=proxies
                                 )
        logging.info("请求返回:{}".format(response.text))
        if response.status_code != 200:
            if retry_count < 3:
                return self.answer(question, retry_count+1)
            return "当前网络拥挤，请稍后再试。"
        else:
            return response.json()["answer"]


    def is_valid(self, question:str) -> bool:
        return True

    def name(self) -> str:
        return "53ai"
