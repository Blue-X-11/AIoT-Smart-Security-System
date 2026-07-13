import os
from celery import Celery

# 1. 初始化 Celery 应用，取名叫 'ai_tasks'
# 我们复用现有的 Redis 作为流水线 (broker) 和结果存储 (backend)
redis_url = f"redis://{os.getenv('REDIS_HOST', 'redis-server')}:{os.getenv('REDIS_PORT', '6379')}/0"

celery_app = Celery(
    "ai_tasks",
    broker=redis_url,
    backend=redis_url
)

# 2. Celery 基础配置
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    # 告诉 Celery 去哪个文件里找厨师（任务）
    imports=["app.tasks.vision_tasks"] 
)