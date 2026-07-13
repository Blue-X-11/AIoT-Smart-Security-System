<template>
  <div class="dashboard">
    <header class="header">
      <h1>边缘 AIoT 目标检测控制大屏</h1>
      <div class="system-status">后端网关: 稳定连接 (Port: 54913) | 累计检测: {{ totalInferences }} 次</div>
    </header>

    <main class="main-content">
      <div class="top-layout">
        <section class="panel control-panel">
          <h2>📷 视频输入 / 图像抓拍</h2>
          <div class="upload-box">
            <input type="file" @change="handleFileChange" accept="image/*" id="file-input" />
            <label for="file-input" class="upload-label">
              <span>点击选择或拖拽监控抓拍图</span>
            </label>
          </div>
          <button @click="submitInference" :disabled="!selectedFile || isProcessing" class="btn-primary">
            {{ isProcessing ? 'AI 正在全力推理中...' : '开始 AI 目标检测' }}
          </button>
          <div v-if="taskStatus" class="status-alert">
            当前系统状态: <strong>{{ taskStatus }}</strong>
          </div>
        </section>

        <section class="panel result-panel">
          <h2 class="panel-header-flex">
            🖥️ 视觉分析画面 
            <!-- 💡 新增：一键切回实时监控的按钮 -->
            <button v-if="!isLiveMode" @click="enableLiveMode" class="btn-live">
              🔴 返回实时监控
            </button>
          </h2>
          
          <div class="visual-container">
            <!-- 💡 核心新增：实时视频流容器 -->
            <div v-show="isLiveMode" class="live-stream-wrapper">
              <img 
                :src="liveStreamUrl" 
                alt="等待 ESP32-CAM 摄像头接入..." 
                class="live-image"
                onerror="this.alt='❌ 视频流中断，请检查后端运行状态'"
              />
              <div class="live-badge">
                <span class="live-dot animate-ping"></span>
                <span class="live-dot absolute"></span>
                <span class="live-text">LIVE</span>
              </div>
            </div>

            <!-- 原有的静态图像画框 Canvas (隐藏/显示逻辑更新) -->
            <canvas ref="detectCanvas" class="result-canvas" v-show="!isLiveMode && resultImageUrl"></canvas>
            <div v-show="!isLiveMode && !resultImageUrl && !isProcessing" class="placeholder-box">等待接收边缘端监控画面...</div>
            <div v-show="!isLiveMode && isProcessing" class="placeholder-box">AI 视觉神经元解析中...</div>
          </div>

          <div class="data-dashboard">
            <div class="data-panel log-panel">
              <h3>📊 最新单次检测数据 (JSON)</h3>
              <pre v-if="predictions.length > 0">{{ JSON.stringify(predictions, null, 2) }}</pre>
              <div v-else class="no-data">暂无检测目标</div>
            </div>
            <div class="data-panel chart-panel">
              <h3>📈 全局目标态势感知 (Top 1000)</h3>
              <div ref="chartContainer" class="echarts-box"></div>
            </div>
          </div>
        </section>
      </div>

      <section class="panel history-panel">
        <h2>🎞️ 边缘节点历史抓拍档案 (点击回放)</h2>
        <div class="history-grid">
          <div 
            v-for="item in historyList" 
            :key="item.id" 
            class="history-card"
            @click="reviewHistory(item)"
          >
            <img :src="item.image_url ? item.image_url.replace('minio-server', 'localhost') : ''" alt="History" loading="lazy" />
            <div class="history-overlay">
              <span>ID: {{ item.id }}</span>
              <span>目标数: {{ item.prediction.length }}</span>
            </div>
          </div>
          <div v-if="historyList.length === 0" class="no-data">档案库为空</div>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'
import * as echarts from 'echarts'

const API_BASE = 'http://localhost:8000'

// 💡 新增：实时监控流地址 (换成你后端的真实 IP)
const liveStreamUrl = 'http://172.18.66.156:8000/video_feed'
const isLiveMode = ref(true) // 默认开启实时监控

const selectedFile = ref(null)
const isProcessing = ref(false)
const taskStatus = ref('系统已就绪，实时监控中')
const resultImageUrl = ref('')
const predictions = ref([])
const detectCanvas = ref(null)

const chartContainer = ref(null)
const totalInferences = ref(0)
let myChart = null

const historyList = ref([])
const lastSeenId = ref(null) 

const fetchAndRenderStats = async () => {
  try {
    const res = await axios.get(`${API_BASE}/stats/`)
    if (res.data.status === 'success') {
      totalInferences.value = res.data.total_inferences
      if (!myChart && chartContainer.value) {
        myChart = echarts.init(chartContainer.value, 'dark')
      }
      const option = {
        backgroundColor: 'transparent',
        tooltip: { trigger: 'item' },
        series: [
          {
            name: '检测目标', type: 'pie', radius: ['40%', '70%'],
            avoidLabelOverlap: false,
            itemStyle: { borderRadius: 5, borderColor: '#1e293b', borderWidth: 2 },
            label: { show: true, color: '#94a3b8' },
            data: res.data.chart_data
          }
        ]
      }
      if (myChart) myChart.setOption(option)
    }
  } catch (error) {
    console.error("获取统计数据失败", error)
  }
}

const fetchHistory = async () => {
  try {
    const res = await axios.get(`${API_BASE}/history/`)
    if (res.data.status === 'success') {
      historyList.value = res.data.data
      
      if (historyList.value.length > 0) {
        const latestItem = historyList.value[0] 
        
        if (lastSeenId.value !== latestItem.id) {
          lastSeenId.value = latestItem.id 
          
          // 💡 修改：如果处于实时监控模式，后台默默更新历史墙就行，不抢占大屏
          if (!isProcessing.value && !isLiveMode.value) {
            taskStatus.value = `🟢 接收到边缘节点最新画面 (ID: ${latestItem.id})`
            reviewHistory(latestItem) 
          }
          fetchAndRenderStats() 
        }
      }
    }
  } catch (error) {
    console.error("获取历史记录失败", error)
  }
}

// 💡 辅助函数：一键切回实时监控
const enableLiveMode = () => {
  isLiveMode.value = true
  taskStatus.value = '已恢复实时监控模式'
}

const reviewHistory = (item) => {
  if (!item.image_url) return
  
  // 💡 修改：一旦用户点击历史记录，立刻关闭实时视频流，进入 Canvas 静态回放模式
  isLiveMode.value = false
  taskStatus.value = `正在回放历史影像 (档案 ID: ${item.id})`
  
  const safeUrl = item.image_url.replace('minio-server', 'localhost')
  resultImageUrl.value = safeUrl
  predictions.value = item.prediction
  
  drawResultOnCanvas(safeUrl, item.prediction)
}

onMounted(() => {
  fetchAndRenderStats()
  fetchHistory() 
  window.addEventListener('resize', () => { if (myChart) myChart.resize() })

  setInterval(() => {
    if (!isProcessing.value) {
      fetchHistory()
    }
  }, 3000)
})

const handleFileChange = (event) => {
  const file = event.target.files[0]
  if (file) {
    // 💡 修改：一旦选择本地文件，立刻退出实时监控模式
    isLiveMode.value = false
    
    selectedFile.value = file
    resultImageUrl.value = ''
    predictions.value = ''
    taskStatus.value = '文件已就绪'
    if (detectCanvas.value) {
      const ctx = detectCanvas.value.getContext('2d')
      ctx.clearRect(0, 0, detectCanvas.value.width, detectCanvas.value.height)
    }
  }
}

const drawResultOnCanvas = (imageUrl, preds) => {
  const canvas = detectCanvas.value
  if (!canvas) return
  
  const ctx = canvas.getContext('2d')
  const img = new Image()
  
  img.crossOrigin = 'Anonymous' 
  img.src = imageUrl
  
  img.onload = () => {
    canvas.width = img.width
    canvas.height = img.height
    ctx.drawImage(img, 0, 0, img.width, img.height)
    
    preds.forEach(p => {
      const [x1, y1, x2, y2] = p.bbox
      const rectWidth = x2 - x1
      const rectHeight = y2 - y1
      
      const strokeWidth = Math.max(img.width * 0.005, 3)
      const fontSize = Math.max(img.width * 0.02, 16)
      const textHeight = fontSize + 10 
      
      ctx.strokeStyle = '#10b981' 
      ctx.lineWidth = strokeWidth
      ctx.strokeRect(x1, y1, rectWidth, rectHeight)
      
      const text = `${p.class} ${(p.confidence * 100).toFixed(1)}%`
      ctx.font = `bold ${fontSize}px Arial`
      const textWidth = ctx.measureText(text).width
      
      if (y1 - textHeight < 0) {
        ctx.fillStyle = '#10b981'
        ctx.fillRect(x1, y1, textWidth + 10, textHeight)
        ctx.fillStyle = '#ffffff'
        ctx.fillText(text, x1 + 5, y1 + fontSize + 4)
      } else {
        ctx.fillStyle = '#10b981'
        ctx.fillRect(x1, y1 - textHeight, textWidth + 10, textHeight)
        ctx.fillStyle = '#ffffff'
        ctx.fillText(text, x1 + 5, y1 - 8)
      }
    })
  }
}

const submitInference = async () => {
  if (!selectedFile.value) return
  isProcessing.value = true
  isLiveMode.value = false // 确保处于静态模式
  taskStatus.value = '排队入队中 (Celery Task Created)...'
  const formData = new FormData()
  formData.append('file', selectedFile.value)

  try {
    const response = await axios.post(`${API_BASE}/predict/`, formData, { headers: { 'Content-Type': 'multipart/form-data' } })
    if (response.data.source === 'redis cache') {
      taskStatus.value = '命中 Redis 缓存，直接返回！'
      predictions.value = response.data.prediction
      const finalImageUrl = response.data.image_url ? response.data.image_url.replace('minio-server', 'localhost') : ''
      resultImageUrl.value = finalImageUrl
      drawResultOnCanvas(finalImageUrl, response.data.prediction)
      isProcessing.value = false
      return
    }
    const taskId = response.data.task_id
    taskStatus.value = `任务已分发至后厨，ID: ${taskId.substring(0, 8)}...`
    startPolling(taskId)
  } catch (error) {
    taskStatus.value = '提交失败，请检查网络或后端容器'
    isProcessing.value = false
  }
}

const startPolling = (taskId) => {
  const timer = setInterval(async () => {
    try {
      const res = await axios.get(`${API_BASE}/tasks/${taskId}`)
      if (res.data.status === 'success') {
        clearInterval(timer)
        taskStatus.value = `推理完成！后台耗时 ${res.data.time.toFixed(2)} 秒`
        predictions.value = res.data.prediction
        const finalImageUrl = res.data.image_url ? res.data.image_url.replace('9000', '54913') : ''
        resultImageUrl.value = finalImageUrl
        drawResultOnCanvas(finalImageUrl, res.data.prediction)
        isProcessing.value = false
        
        fetchAndRenderStats() 
        fetchHistory() 
        
      } else if (res.data.status === 'failed') {
        clearInterval(timer)
        taskStatus.value = 'AI 推理任务失败'
        isProcessing.value = false
      }
    } catch (err) {
      clearInterval(timer)
      taskStatus.value = '轮询过程中断'
      isProcessing.value = false
    }
  }, 500)
}
</script>

<style scoped>
/* 保持原有布局样式 */
.dashboard { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; min-height: 100vh; padding: 20px; }
.header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #334155; padding-bottom: 15px; margin-bottom: 20px; }
.header h1 { margin: 0; font-size: 24px; color: #38bdf8; }
.system-status { background: #065f46; color: #34d399; padding: 6px 12px; border-radius: 20px; font-size: 14px; font-weight: bold; }
.main-content { display: flex; flex-direction: column; gap: 20px; }
.top-layout { display: flex; flex-direction: column; gap: 20px; }

@media (min-width: 1024px) {
  .top-layout { flex-direction: row; }
  .control-panel { flex: 0 0 350px; }
  .result-panel { flex: 1; min-width: 0; }
}

.panel { background: #1e293b; border-radius: 12px; padding: 20px; border: 1px solid #334155; }
.panel h2 { margin-top: 0; font-size: 18px; border-left: 4px solid #38bdf8; padding-left: 10px; margin-bottom: 20px; }
.upload-box { border: 2px dashed #475569; border-radius: 8px; padding: 30px; text-align: center; margin-bottom: 15px; cursor: pointer; transition: 0.3s; }
.upload-box:hover { border-color: #38bdf8; }
#file-input { display: none; }
.upload-label { cursor: pointer; color: #94a3b8; }
.btn-primary { width: 100%; background: #0284c7; color: white; border: none; padding: 12px; border-radius: 6px; font-weight: bold; cursor: pointer; transition: 0.2s; }
.btn-primary:hover { background: #0369a1; }
.btn-primary:disabled { background: #475569; cursor: not-allowed; }
.status-alert { margin-top: 15px; background: #334155; padding: 10px; border-radius: 6px; font-size: 14px; color: #e2e8f0; }

/* 💡 新增：标题栏 Flex 布局，让按钮靠右 */
.panel-header-flex { display: flex; justify-content: space-between; align-items: center; }
.btn-live { background: #ef4444; color: white; border: none; padding: 6px 12px; border-radius: 6px; font-size: 12px; cursor: pointer; transition: 0.2s; font-weight: bold; }
.btn-live:hover { background: #dc2626; }

/* 💡 新增：实时流视频区域样式 */
.live-stream-wrapper { width: 100%; height: 100%; position: relative; display: flex; align-items: center; justify-content: center; }
.live-image { max-width: 100%; max-height: 500px; object-fit: contain; border-radius: 6px; }
.live-badge { position: absolute; top: 15px; left: 15px; display: flex; align-items:center; gap: 8px; background: rgba(0,0,0,0.6); padding: 4px 10px; border-radius: 20px; border: 1px solid #4b5563; }
.live-dot { display: inline-block; width: 10px; height: 10px; background-color: #ef4444; border-radius: 50%; }
.live-text { color: #ef4444; font-size: 12px; font-weight: bold; letter-spacing: 1px; font-family: monospace; margin-left: 12px; }

.visual-container { background: #0f172a; border-radius: 8px; min-height: 400px; display: flex; align-items: center; justify-content: center; overflow: hidden; margin-bottom: 20px; border: 1px solid #334155; position: relative; }
.result-canvas { max-width: 100%; max-height: 500px; object-fit: contain; }
.placeholder-box { color: #64748b; }

.data-dashboard { display: flex; flex-wrap: wrap; gap: 20px; }
.data-panel { background: #0f172a; padding: 15px; border-radius: 8px; border: 1px solid #334155; flex: 1; min-width: 250px;}
.data-panel h3 { margin-top: 0; font-size: 14px; color: #94a3b8; }
.log-panel pre { margin: 0; background: #000; padding: 10px; border-radius: 4px; color: #4ade80; font-family: monospace; overflow-x: auto; font-size: 13px; height: 200px; overflow-y: auto;}
.no-data { color: #475569; font-size: 14px; }
.echarts-box { width: 100%; height: 220px; } 

.history-panel { margin-top: 10px; }
.history-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 15px; }
.history-card { position: relative; border-radius: 8px; overflow: hidden; border: 2px solid #334155; cursor: pointer; transition: transform 0.2s, border-color 0.2s; background: #0f172a; aspect-ratio: 4/3; }
.history-card:hover { transform: translateY(-3px); border-color: #38bdf8; }
.history-card img { width: 100%; height: 100%; object-fit: cover; }
.history-overlay { position: absolute; bottom: 0; left: 0; right: 0; background: rgba(0,0,0,0.7); color: #fff; font-size: 12px; padding: 6px; display: flex; justify-content: space-between; align-items: center; }
</style>