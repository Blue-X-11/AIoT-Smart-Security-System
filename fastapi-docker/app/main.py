from fastapi import FastAPI, File, UploadFile, Depends, Response
from fastapi.responses import StreamingResponse
import redis
import hashlib
import json
import os
import time
from dotenv import load_dotenv
from app.core.logger import logger
from sqlalchemy.orm import Session
from app.db.deps import get_db
from app.api.routes.auth import router as auth_router
from app.db.models import PredictionRecord
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware
import requests

# 1. [新增] 引入 Celery 任务和查询结果的类
from app.tasks.vision_tasks import process_image_task
from celery.result import AsyncResult
from app.core.celery_app import celery_app

NODEMCU_IP = "172.20.10.4"

app = FastAPI(root_path="/api")

# ================= 核心新增：CORS 跨域放行配置 =================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有域名跨域（开发环境无脑填 "*" 即可）
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有 HTTP 方法 (GET, POST, OPTIONS 等)
    allow_headers=["*"],  # 允许所有请求头
)
# ==============================================================

load_dotenv()
app.include_router(auth_router)

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis-server"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    decode_responses=True
)

# 专门用于读取二进制图像的 Redis 客户端，关闭自动解码
redis_binary_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis-server"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    decode_responses=False 
)

def trigger_physical_action(predictions):
    """提取预测结果中的标签，指挥 NodeMCU"""
    # 比如 predictions 的格式是: [{"class": "cat", "confidence": 0.9}, ...]
    labels = [p["class"] for p in predictions]
    try:
        if "person" in labels:
            requests.get(f"http://{NODEMCU_IP}/control?device=buzzer&status=on", timeout=1)
            requests.get(f"http://{NODEMCU_IP}/control?device=led&status=on", timeout=1)
        elif "cat" in labels:
            requests.get(f"http://{NODEMCU_IP}/control?device=relay&status=on", timeout=1)
        else:
            # 安全情况下，关闭所有报警和继电器
            requests.get(f"http://{NODEMCU_IP}/control?device=buzzer&status=off", timeout=1)
            requests.get(f"http://{NODEMCU_IP}/control?device=led&status=off", timeout=1)
            requests.get(f"http://{NODEMCU_IP}/control?device=relay&status=off", timeout=1)
    except Exception as e:
        print(f"NodeMCU 通信失败: {e}")

def generate_frames():
    """
    生成器函数：从 Redis 不断拉取最新画面并生成 MJPEG 视频流
    """
    while True:
        # 获取 Celery 刚刚存入的最新带框图片
        frame = redis_binary_client.get("latest_frame")
        
        if frame and isinstance(frame, bytes):
            # 必须严格遵守 HTTP MJPEG multipart/x-mixed-replace 格式规范
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        else:
            # 如果 Redis 里没画面，稍微休息一下，防止 CPU 空转飙升到 100%
            time.sleep(0.1)
            
        # 强制微小延迟，将输出帧率控制在约 20-30 FPS 以内，保护网络带宽
        time.sleep(0.04)

@app.get("/video_feed")
def video_feed():
    """
    流媒体直播接口，前端直接用 img 标签的 src 属性对准这里即可！
    """
    return StreamingResponse(
        generate_frames(), 
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@app.get("/")
def read_root():
    return {"message": "Hello AIoT"}

@app.post("/predict/")
async def predict_endpoint(file: UploadFile = File(...)):
    """
    异步接口：只负责接收图片，把任务扔给队列，瞬间返回 Task ID
    """
    contents = await file.read()
    image_hash = hashlib.md5(contents).hexdigest()

    # 1. 缓存拦截（收银员发现这个饭以前做过，直接从冰柜拿给客户）
    cached_data = redis_client.get(image_hash)
    if cached_data:
        logger.info("Cache hit in API layer")
        cached_result = json.loads(cached_data)
        # 既然命中了缓存，前台直接提取结果，命令 NodeMCU 动作！
        trigger_physical_action(cached_result)
        return {
            "status": "success",
            "prediction": cached_result,
            "source": "redis cache"
        }

    # 2. 如果没缓存，就把原图存在共享目录 /app 下，供后厨读取
    logger.info("Cache miss, sending to celery worker...")
    temp_path = f"temp_{image_hash}_{file.filename}"
    
    with open(temp_path, "wb") as buffer:
        buffer.write(contents)

    # 3. [核心代码] .delay() 就是把订单扔给后厨流水线！
    # 注意：我们这里不需要等待，代码执行完这行会瞬间往下走
    task = process_image_task.delay(temp_path, file.filename)

    # 4. 瞬间返回取餐码 (Task ID)
    return {
        "status": "processing",
        "task_id": task.id,
        "message": "任务已提交后台处理，请使用 task_id 查询进度"
    }

# ================= 新增查询接口 =================
@app.get("/tasks/{task_id}")
def get_task_status(task_id: str):
    """
    大屏幕接口：前端拿着 Task ID 来轮询任务进度
    """
    # 去 Redis 里查这个任务的状态
    task_result = AsyncResult(task_id, app=celery_app)
    
    if task_result.state == 'PENDING':
        # 任务还在排队
        return {"status": "pending", "message": "任务排队中或不存在"}
        
    elif task_result.state == 'SUCCESS':
        # 任务完成，返回结果！
        return task_result.result
        
    elif task_result.state == 'FAILURE':
        # 任务报错
        return {"status": "failed", "message": str(task_result.info)}
        
    else:
        # 其他状态（比如 STARTED 正在处理中）
        return {"status": task_result.state}
    
# ====== 新增：态势感知数据统计接口 ======
@app.get("/stats/")
def get_system_stats(db: Session = Depends(get_db)):
    """
    大屏数据看板接口：统计历史检测出的各类目标数量
    """
    # 1. 获取总检测次数
    total_inferences = db.query(PredictionRecord).count()
    
    # 2. 为了速度，我们抓取最近 1000 条记录进行分类统计
    recent_records = db.query(PredictionRecord).order_by(PredictionRecord.id.desc()).limit(1000).all()
    
    class_counts = {}
    
    for record in recent_records:
        try:
            # 将存入数据库的 JSON 字符串还原为 Python 字典列表
            predictions = json.loads(record.prediction)
            for p in predictions:
                obj_class = p.get("class")
                if obj_class:
                    # 如果字典里已经有这个类别，数量 +1；否则初始化为 1
                    class_counts[obj_class] = class_counts.get(obj_class, 0) + 1
        except Exception:
            continue
            
    # 3. 将字典转换为 ECharts 饼图所需要的格式: [{"name": "person", "value": 15}, ...]
    chart_data = [{"name": k, "value": v} for k, v in class_counts.items()]
    
    return {
        "status": "success",
        "total_inferences": total_inferences,
        "chart_data": chart_data
    }

# ====== 新增：历史影像档案查询接口 ======
@app.get("/history/")
def get_history(limit: int = 12, db: Session = Depends(get_db)):
    """
    大屏画廊接口：获取最近的 N 条历史检测记录（默认 12 条）
    """
    # 按照 ID 倒序排列，拿出最新的 12 条记录
    recent_records = db.query(PredictionRecord).order_by(PredictionRecord.id.desc()).limit(limit).all()
    
    history_data = []
    for record in recent_records:
        try:
            prediction_json = json.loads(record.prediction)
        except Exception:
            prediction_json = []
            
        history_data.append({
            "id": record.id,
            "image_url": record.filename,  # 这里存的是 MinIO 的 URL
            "prediction": prediction_json,
            "source": record.source
        })
        
    return {
        "status": "success",
        "data": history_data
    }