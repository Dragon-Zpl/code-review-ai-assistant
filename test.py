from ai.kernel.fast_gtp import FastGTP
from config.config import FastGTPConfig
import logging
if __name__ == "__main__":
    # 创建 FastGTPConfig 实例并设置参数
    fast_gtp_config = FastGTPConfig()
    fast_gtp_config.secret_key = "sk-PtxBvgDpcroxxDkmA66eBa18A99f45A0Ac8fB930B5D934F7"
    fast_gtp_config.url = "https://api.edgefn.net/v1/chat/completions"
    fast_gtp_config.gtp_model = "GLM-4.5-FLASH"

    # 创建 FastGTP 实例
    fast_gtp = FastGTP(fast_gtp_config)
    path = "D:\\PycharmProjects\\jinja2test\\main.py"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    question = """请帮我review这段代码, 找出潜在的安全问题，并以下面的格式回答我：
    代码中存在X个潜在的安全问题:
    然后按照顺序列出每个问题描述以及优化方案，使用markdown格式。
    代码如下:
    ```
    {}
    ```
    """.format(content)
    logging.info(fast_gtp.answer(question=question))