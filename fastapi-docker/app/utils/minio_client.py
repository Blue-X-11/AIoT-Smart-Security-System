from minio import Minio
import os
import uuid
from datetime import datetime
from app.core.logger import logger

# 1. 初始化 MinIO 客户端
minio_client = Minio(
    endpoint=os.getenv("MINIO_ENDPOINT", "minio:9000"),
    access_key=os.getenv("MINIO_ROOT_USER", "admin"),
    secret_key=os.getenv("MINIO_ROOT_PASSWORD", "password123"),
    secure=False  # 因为我们在本地/内网环境，没有配置 HTTPS，所以设为 False
)

BUCKET_NAME = "images"

def upload_image_to_minio(file_path: str, original_filename: str) -> str:
    """
    将本地临时图片上传到 MinIO，并返回可访问的 URL
    """
    try:
        # 2. 生成全局唯一的安全文件名 (例如: 20260531_a1b2c3d4.jpg)
        ext = original_filename.split('.')[-1]
        unique_name = f"{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:8]}.{ext}"
        
        # 3. 执行上传
        minio_client.fput_object(
            bucket_name=BUCKET_NAME,
            object_name=unique_name,
            file_path=file_path,
            content_type=f"image/{ext}"
        )
        
        # 4. 拼接图片的访问 URL (这里假设前端通过 localhost 访问)
        # 生产环境中，这个 IP 通常是你的 Nginx 域名
        image_url = f"http://localhost:9000/{BUCKET_NAME}/{unique_name}"
        
        logger.info(f"Successfully uploaded image to MinIO: {image_url}")
        return image_url

    except Exception as e:
        logger.error(f"MinIO upload failed: {str(e)}")
        # 如果上传失败，返回空字符串或抛出异常，这里为了容错返回空
        return ""