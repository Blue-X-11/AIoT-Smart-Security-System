import logging
import os

# 创建 logs 目录
os.makedirs("logs", exist_ok=True)

# 创建 logger
logger = logging.getLogger("ai-api")

# 设置日志等级
logger.setLevel(logging.INFO)

# 日志格式
formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(message)s"
)

# 文件输出
file_handler = logging.FileHandler("logs/app.log")

file_handler.setFormatter(formatter)

# 控制台输出
stream_handler = logging.StreamHandler()

stream_handler.setFormatter(formatter)

# 添加 handler
logger.addHandler(file_handler)
logger.addHandler(stream_handler)
