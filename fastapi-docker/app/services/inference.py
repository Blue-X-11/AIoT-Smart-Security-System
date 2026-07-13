from ultralytics import YOLO
import cv2

# 1. 初始化 YOLO 模型
# 首次运行会自动从 GitHub 下载 yolov8n.pt 权重文件 (约 6MB)
model = YOLO("yolov8n.pt")

def predict(image_path):
    """
    接收图片路径，执行目标检测推理
    """
    # 2. 执行推理
    # conf=0.25: 过滤掉置信度低于 25% 的杂讯目标
    # device="cpu": 明确指定使用 CPU 推理，避免寻找 CUDA 报错
    results = model(image_path, conf=0.25, device="cpu")
    
    detections = []
    
    # 3. 结构化解析结果
    # results 是一个列表 (YOLO 支持批量传图，我们每次传1张，所以取 result[0] 即为 r)
    for r in results:
        boxes = r.boxes  # 提取所有的边界框对象
        
        # 遍历图中的每一个被检测到的目标
        for box in boxes:
            # 取出类别索引并转换为具体的类别名称 (如 'person', 'car')
            class_id = int(box.cls[0])
            class_name = model.names[class_id]
            
            # 取出置信度并保留 4 位小数
            confidence = round(float(box.conf[0]), 4)
            
            # 取出坐标: xyxy 格式 (左上角 x, 左上角 y, 右下角 x, 右下角 y)
            coords = box.xyxy[0].tolist()
            coords = [round(c, 2) for c in coords]  # 坐标保留 2 位小数
            
            # 组装成企业标准的 JSON 数据结构
            detections.append({
                "class": class_name,
                "confidence": confidence,
                "bbox": coords
            })

    # 使用 YOLO 内置的方法在原图上画框
    #res_plotted = results[0].plot()  # plot() 会返回一个画好框的 BGR 图像矩阵

    # 用画好框的图，覆盖掉原来的 temp_path 原图
    #cv2.imwrite(image_path, res_plotted)
            
    return detections