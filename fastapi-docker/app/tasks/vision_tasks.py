import os
import json
import time
from app.core.celery_app import celery_app
from app.services.inference import predict
from app.utils.minio_client import upload_image_to_minio
from app.db.database import SessionLocal
from app.db.models import PredictionRecord
from app.core.logger import logger
import logging
import paho.mqtt.client as mqtt
import face_recognition
import redis # 💡 新增：导入 redis 库
import cv2

logger = logging.getLogger(__name__)

# MQTT 路由配置
MQTT_BROKER = "YOUR_MQTT_BROKER_IP"
MQTT_PORT = 1883
MQTT_NAME = "YOUR_MQTT_USERNAME"
MQTT_PASSWORD = "YOUR_MQTT_PASSWORD"
TOPIC_CONTROL = "/iot/4861/bluemacair/2026/iot/control"
TOPIC_TRACK = "/iot/4861/bluemacair/2026/iot/track"

# 图像分辨率与死区
FRAME_WIDTH = 640
FRAME_HEIGHT = 480
CENTER_X = FRAME_WIDTH // 2  # 320
CENTER_Y = FRAME_HEIGHT // 2 # 240
DEADZONE = 40 

# MQTT 动态连接变量
_worker_mqtt_client = None

# =====================================================================
# 💡 门禁防抖控制变量：记录门锁应该保持开启到什么时间戳
DOOR_UNLOCK_EXPIRY = 0.0

# 💡 新增：初始化 Redis 客户端，用于极速存储实时画面
# 假设你的 docker-compose 里面 redis 的服务名就叫 redis-server
redis_client = redis.Redis(host='redis-server', port=6379, db=0)
# =====================================================================

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
MASTER_FACE_FILE = os.path.join(CURRENT_DIR, "my_face.JPG")
master_encoding = None

try:
    if os.path.exists(MASTER_FACE_FILE):
        logger.info(f"⏳ 正在加载主人面部密码本: {MASTER_FACE_FILE}...")
        master_image = face_recognition.load_image_file(MASTER_FACE_FILE)
        encodings = face_recognition.face_encodings(master_image)
        if len(encodings) > 0:
            master_encoding = encodings[0]
            logger.info("✅ 成功提取主人面部特征！系统已具备双重认证能力。")
        else:
            logger.warning(f"⚠️ 在 {MASTER_FACE_FILE} 中未能检测到清晰人脸！")
    else:
        logger.warning(f"⚠️ 找不到文件 {MASTER_FACE_FILE}，系统将无法开锁，默认对所有人报警。")
except Exception as e:
    logger.error(f"❌ 加载面部特征库严重出错: {e}")

def get_mqtt_client():
    global _worker_mqtt_client
    if _worker_mqtt_client is not None and _worker_mqtt_client.is_connected():
        return _worker_mqtt_client
        
    logger.info("⏳ 检测到当前 Worker 子进程未建立有效连接，正在初始化专属 MQTT 链路...")
    try:
        client = mqtt.Client()
        client.username_pw_set(MQTT_NAME, MQTT_PASSWORD)
        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        client.loop_start() 
        time.sleep(0.2)
        _worker_mqtt_client = client
        logger.info(f"✅ 专属 Worker 子进程成功连接到 MQTT Broker: {MQTT_BROKER}")
        return _worker_mqtt_client
    except Exception as e:
        logger.error(f"❌ Worker 子进程建立 MQTT 连接失败: {e}")
        _worker_mqtt_client = None
        return None

def trigger_physical_action(predictions, image_path):
    global DOOR_UNLOCK_EXPIRY
    
    client = get_mqtt_client()
    if client is None:
        return

    labels = [p["class"] for p in predictions]
    current_time = time.time()
    
    # ----------------------------------------
    # 模块 A：安防与身份认证门禁联动 (带防抖保护)
    # ----------------------------------------
    if "person" in labels:
        is_master = False
        
        if master_encoding is not None:
            logger.info("👀 第一道门卫(YOLO)发现人员！启动第二道门卫(FaceRecognition)深度比对...")
            try:
                unknown_image = face_recognition.load_image_file(image_path)
                unknown_encodings = face_recognition.face_encodings(unknown_image)
                
                if len(unknown_encodings) == 0:
                    logger.warning("⚠️ 第二道门卫报告：光线太暗或脸太小，没看清五官！")

                for unknown_encoding in unknown_encodings:
                    distances = face_recognition.face_distance([master_encoding], unknown_encoding)
                    logger.info(f"📏 AI 面部特征差异值 (Distance): {distances[0]:.4f} (越小越像)")
                    # 容错率放宽至 0.6 适配 ESP32-CAM
                    results = face_recognition.compare_faces([master_encoding], unknown_encoding, tolerance=0.6)
                    if results[0] == True:
                        is_master = True
                        break 
            except Exception as e:
                logger.error(f"❌ 人脸比对引擎运行异常: {e}")

        # 终极判决逻辑
        if is_master:
            logger.info("✅ 身份确认：是主人！触发继电器开锁 (门锁将保持开启 5 秒)...")
            # 💡 核心防抖：一旦认出是主人，把开门到期时间往后延 5 秒
            DOOR_UNLOCK_EXPIRY = current_time + 5.0
            client.publish(TOPIC_CONTROL, "relay:on")
            client.publish(TOPIC_CONTROL, "buzzer:off")
            client.publish(TOPIC_CONTROL, "led:off")
        else:
            # 💡 缓冲判断：如果是陌生人，或者没看清脸，先检查 5 秒的保护期过了没
            if current_time < DOOR_UNLOCK_EXPIRY:
                remain = DOOR_UNLOCK_EXPIRY - current_time
                logger.info(f"⏳ 门锁保护期开启中 (剩余 {remain:.1f} 秒)，忽略本次未识别/陌生人警告。")
            else:
                logger.warning("❌ 身份不明且保护期已过：确认陌生人入侵！触发声光警报！")
                client.publish(TOPIC_CONTROL, "buzzer:on")
                client.publish(TOPIC_CONTROL, "led:on")
                client.publish(TOPIC_CONTROL, "relay:off")
            
    elif "cat" in labels:
        logger.info("🐱 发现猫上桌！触发继电器喷雾...")
        client.publish(TOPIC_CONTROL, "relay:on")
    else:
        # 画面中没人，同样检查保护期
        if current_time < DOOR_UNLOCK_EXPIRY:
             remain = DOOR_UNLOCK_EXPIRY - current_time
             logger.info(f"⏳ 主人刚离开画面，门锁延时保持中 (剩余 {remain:.1f} 秒)...")
        else:
            logger.info("🔇 画面无人且保护期结束: 发送指令关闭所有物理外设")
            client.publish(TOPIC_CONTROL, "buzzer:off")
            client.publish(TOPIC_CONTROL, "led:off")
            client.publish(TOPIC_CONTROL, "relay:off")

    # ----------------------------------------
    # 模块 B：云台追踪联动
    # ----------------------------------------
    target = None
    for p in predictions:
        if p["class"] in ["person", "cat"]:
            target = p
            logger.info(f"📍 选择追踪目标: {p['class']} (置信度: {p.get('confidence', 'N/A')})")
            break
    
    if target:
        bbox = target["bbox"]
        cx = int((bbox[0] + bbox[2]) / 2)
        cy = int((bbox[1] + bbox[3]) / 2)
        
        # 水平方向判断
        if cx < (CENTER_X - DEADZONE):
            offset = CENTER_X - DEADZONE - cx
            logger.info(f"⬅️ 目标偏左 {offset} 像素，发送 'left' 指令")
            client.publish(TOPIC_TRACK, "left")
        elif cx > (CENTER_X + DEADZONE):
            offset = cx - (CENTER_X + DEADZONE)
            logger.info(f"➡️ 目标偏右 {offset} 像素，发送 'right' 指令")
            client.publish(TOPIC_TRACK, "right")
        else:
            logger.info("✅ 水平方向在死区范围内，无需调整")
            
        # 垂直方向判断
        if cy < (CENTER_Y - DEADZONE):
            offset = CENTER_Y - DEADZONE - cy
            logger.info(f"⬆️ 目标偏上 {offset} 像素，发送 'up' 指令")
            client.publish(TOPIC_TRACK, "up")
        elif cy > (CENTER_Y + DEADZONE):
            offset = cy - (CENTER_Y + DEADZONE)
            logger.info(f"⬇️ 目标偏下 {offset} 像素，发送 'down' 指令")
            client.publish(TOPIC_TRACK, "down")
        else:
            logger.info("✅ 垂直方向在死区范围内，无需调整")
    else:
        logger.info("ℹ️ 未检测到 person 或 cat 目标，云台保持当前位置")

# ========== Celery 任务 ==========
@celery_app.task(bind=True, name="process_image_task")
def process_image_task(self, temp_path: str, original_filename: str):
    start_time = time.time()
    db = SessionLocal()
    try:
        # 1. 获取推理结果
        result = predict(temp_path)
        trigger_physical_action(result, temp_path)
        
        # 2. 💡 核心修改：在图片上绘制 YOLO 检测框
        # 读取原始图片
        img = cv2.imread(temp_path)
        
        # 假设 predict() 函数返回的结果中包含边界框信息 (bbox)
        # 这里使用 OpenCV 绘制，或者如果你使用的是 Ultralytics YOLO，可以使用 results.plot()
        for p in result:
            bbox = p["bbox"] # [x1, y1, x2, y2]
            label = p["class"]
            # 绘制矩形框
            cv2.rectangle(img, (int(bbox[0]), int(bbox[1])), (int(bbox[2]), int(bbox[3])), (0, 255, 0), 2)
            # 绘制文字
            cv2.putText(img, label, (int(bbox[0]), int(bbox[1]) - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        # 将绘制好的图片编码为 JPEG
        _, buffer = cv2.imencode('.jpg', img)
        annotated_image_bytes = buffer.tobytes()

        # 3. 💡 存入 Redis，前端流媒体服务读取此数据即为带框画面
        try:
            redis_client.setex("latest_frame", 5, annotated_image_bytes)
        except Exception as redis_err:
            logger.error(f"❌ 存入 Redis 实时画面失败: {redis_err}")

        # 4. 上传原始图片到 MinIO (保持不变)
        image_url = upload_image_to_minio(temp_path, original_filename)
        
        # 5. 记录数据库 (保持不变)
        elapsed = time.time() - start_time
        record = PredictionRecord(
            filename=image_url if image_url else original_filename,
            prediction=json.dumps(result),
            source="celery background task",
            inference_time=elapsed
        )
        db.add(record)
        db.commit()
        return {"status": "success", "prediction": result, "image_url": image_url, "time": elapsed}
    except Exception as e:
        logger.error(f"[Celery] 任务 {self.request.id} 失败: {str(e)}")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()
        if os.path.exists(temp_path):
            os.remove(temp_path)