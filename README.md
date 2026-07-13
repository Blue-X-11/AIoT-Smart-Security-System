<div align="center">
  <h1>🛡️ AIoT 智能安防与追踪视觉网关 (AIoT-Smart-Security-System)</h1>
  <p>一个端到端的分布式 AI 视觉物联网系统，涵盖硬件感知、深度学习推理、异步队列处理到大屏监控的全栈实现。</p>
  
  <p>
    <img src="https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white" alt="Python">
    <img src="https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi&logoColor=white" alt="FastAPI">
    <img src="https://img.shields.io/badge/Vue.js-3.0-4FC08D?logo=vue.js&logoColor=white" alt="Vue">
    <img src="https://img.shields.io/badge/YOLO-v8-yellow" alt="YOLOv8">
    <img src="https://img.shields.io/badge/Hardware-ESP32%20%7C%20NodeMCU-black" alt="Hardware">
  </p>
</div>

## 📖 项目简介

本项目探索了“云-边-端”协同架构在物联网安防场景下的落地。前端由 **ESP32-CAM** 采集图像流，通过 **MQTT** 和 **HTTP** 协议传输至后端；后端基于 **FastAPI + Celery + Redis** 构建了高并发异步处理管线，利用 **YOLOv8** 模型进行目标检测，最后通过 MQTT 协议将物理控制信号下发至底层的 **NodeMCU** 节点，实现动态云台追踪与智能电磁门锁联动。

### 🌟 核心亮点

*   **⚡ 全栈闭环架构**：打通了从 `C++(MCU)` -> `Python(AI网关)` -> `JavaScript(Web大屏)` 的完整数据与控制链路。
*   **🧠 异步推理与极速缓存**：基于 Celery + Redis 隔离 AI 推理的阻塞耗时，利用 Redis 构建 5 秒短效帧缓存，实现 Web 端的低延迟 MJPEG 实况视频流注入（带检测框）。
*   **🔒 软硬物理隔离**：弱电(3.3V) NodeMCU 结合光耦继电器，驱动 12V 强电电磁锁，实现指令防抖与保护机制。
*   **🎯 动态云台追踪**：基于 YOLO 返回的 BBox 边界框相对位移，后端计算偏航角度并通过 MQTT 实时微调底座二维舵机。

---

## 🏗️ 系统架构图

> **TODO: 强烈建议在此处插入一张架构图（可以是 draw.io 或你手绘的截图）**
> 
> *图注示例：ESP32-CAM 采集端 -> FastAPI 中转 -> Redis 缓存判定 -> Celery 异步队列 -> YOLOv8 推理 -> MQTT Broker -> NodeMCU 继电器/云台执行端*

---

## 📂 项目结构 (Monorepo)

本仓库采用单体大仓库（Monorepo）结构管理完整的分布式系统：

```text
AIoT-Smart-Security-System/
├── backend/                  # AI 视觉处理网关核心 (Python)
│   ├── app/main.py           # FastAPI 主入口与视频流分发
│   ├── app/tasks/            # Celery 异步任务 (YOLO 推理与图像标注)
│   ├── app/core/             # MQTT 配置与系统中间件
│   └── docker-compose.yml    # Redis / MinIO 基础设施编排
├── frontend/                 # 态势感知大屏 (Vue3 + Tailwind)
│   └── src/components/       # UI 组件与实时视频流接收器
├── hardware-esp32cam/        # 【端点1】图像采集节点 (C++)
│   └── esp32_cam.ino         # 摄像头驱动与 HTTP 图像推流
├── hardware-yuntai/          # 【端点2】2D云台追踪节点 (C++)
│   └── yuntai_servo.ino      # 接收 MQTT 指令计算 PWM 驱动双舵机
└── hardware-mensuo/          # 【端点3】门禁控制节点 (C++)
    └── relay_lock.ino        # 接收 MQTT 认证指令，控制继电器与 12V 电磁锁
🚀 快速启动
1. 环境准备
安装 Docker 与 Docker Compose

Python 3.11+

Node.js 18+

配置好 Arduino IDE 且支持 ESP32 / ESP8266 开发板。

2. 部署后端 (Backend)
Bash
cd backend
# 1. 启动基础设施 (Redis)
docker-compose up -d

# 2. 安装依赖并启动 AI 网关
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 3. 启动 Celery 异步推理队列 (新开一个终端)
celery -A app.core.celery_app worker --loglevel=info
3. 启动前端监控大屏 (Frontend)
Bash
cd frontend
npm install
npm run dev
4. 硬件节点烧录
将 hardware-* 目录下的代码分别烧录到对应的 ESP32-CAM 和 NodeMCU 开发板中。

注意：烧录前请在 .ino 代码中填写你的 Wi-Fi 名称和 MQTT Broker 地址。

📷 系统运行截图
1. 态势感知大屏与实时带框视频流

TODO: 在此处插入一张你的 Vue 监控大屏的截图。一定要截一张能清晰看到绿色的 YOLO 识别框覆盖在真实物理世界物品上的图！

2. 硬件控制链路实测

TODO: 插入一张你在桌面上接线的 ESP32-CAM、NodeMCU 和 12V 电磁锁的实物照片，展现你的硬件动手能力。

⚙️ 核心技术细节 (For Interviewers)
视频流防卡死策略：传统做法是让浏览器频繁拉取检测接口，这会导致大量 HTTP 开销。本方案在 Celery 后端将 OpenCV imencode 后的 JPEG 字节流以 5秒过期时间 注入 Redis。FastAPI 通过 multipart/x-mixed-replace 持续读取 Redis 直接推送到前端 <img> 标签，实现了零前端逻辑的高帧率带框直播。

动作防抖设计：针对视频帧中目标闪烁导致继电器频繁启停的问题，在 MQTT 信号下发模块引入了 DOOR_UNLOCK_EXPIRY 时间戳滑动窗口。一旦识别受信任目标（如人脸验证通过），系统将继电器开启周期强制延长并顺延，极大延长了物理硬件寿命。

📄 许可证 (License)
基于 MIT License 开源。欢迎交流与 Star ⭐️！
