#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include "esp_camera.h"

// 硬件防坑：关闭断电检测，防止 ESP32-CAM 在开启摄像头瞬间因为电流过大而无限重启
#include "soc/soc.h"           
#include "soc/rtc_cntl_reg.h"  

// ================== 【必须修改的配置区】 ==================
const char* ssid = "YOUR_WIFI_SSID";          // 改成这样
const char* password = "YOUR_WIFI_PASSWORD"; // 换成你的 Wi-Fi 密码

// 换成你 Mac 电脑的局域网 IP 和 Nginx 网关端口
const String serverUrl = "http://172.18.66.156:8000/predict/"; 
// ==========================================================

// 💡 状态指示灯引脚：ESP32-CAM 背面的小红灯（注意：它是低电平点亮 LOW=亮, HIGH=灭）
const int indicatorLED = 33; 

// 安信可 ESP32-CAM (AI Thinker) 标准引脚映射
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

// 初始化摄像头
void initCamera() {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG; 
  
  if(psramFound()){
    config.frame_size = FRAMESIZE_SVGA; // 800x600 分辨率
    config.jpeg_quality = 12;           // 质量 12，适合 AI 推理
    config.fb_count = 1;
  } else {
    config.frame_size = FRAMESIZE_VGA;
    config.jpeg_quality = 12;
    config.fb_count = 1;
  }

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("摄像头初始化失败，错误码 0x%x", err);
    return;
  }
  Serial.println("摄像头初始化成功！");
}

// 核心业务：拍照并发送 HTTP Multipart 请求
void captureAndUpload() {
  camera_fb_t * fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("拍照失败！");
    return;
  }
  
  String boundary = "----ESP32CamFormBoundary";
  String head = "--" + boundary + "\r\n" +
                "Content-Disposition: form-data; name=\"file\"; filename=\"esp32cam.jpg\"\r\n" +
                "Content-Type: image/jpeg\r\n\r\n";
  String tail = "\r\n--" + boundary + "--\r\n";

  size_t totalLen = head.length() + fb->len + tail.length();

  uint8_t *post_data = (uint8_t *)ps_malloc(totalLen);
  if (!post_data) {
    Serial.println("PSRAM 内存分配失败！图片太大了！");
    esp_camera_fb_return(fb);
    return;
  }
  memcpy(post_data, head.c_str(), head.length());
  memcpy(post_data + head.length(), fb->buf, fb->len);
  memcpy(post_data + head.length() + fb->len, tail.c_str(), tail.length());

  HTTPClient http;
  http.begin(serverUrl);
  http.addHeader("Connection", "close");
  http.addHeader("Content-Type", "multipart/form-data; boundary=" + boundary);
  
  int httpResponseCode = http.POST(post_data, totalLen);

  if (httpResponseCode > 0) {
    // 上传成功，不打印长篇大论，保持控制台清爽
    Serial.printf("↑ 上传成功 [%d bytes] (状态码: %d)\n", totalLen, httpResponseCode);
  } else {
    Serial.printf("❌ 上传失败！错误代码: %d\n", httpResponseCode);
  }

  http.end();
  free(post_data);
  esp_camera_fb_return(fb);
}

void setup() {
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0); 
  Serial.begin(115200);
  delay(1000);

  // 💡 1. 初始化指示灯
  pinMode(indicatorLED, OUTPUT);
  digitalWrite(indicatorLED, HIGH); // 默认熄灭 (HIGH)

  // 2. 连接 Wi-Fi
  WiFi.begin(ssid, password);
  Serial.print("正在连接 Wi-Fi");
  
  // 💡 3. Wi-Fi 未连接时：小红灯快速闪烁提示正在寻找网络
  while (WiFi.status() != WL_CONNECTED) {
    digitalWrite(indicatorLED, LOW);  // 亮
    delay(100);
    digitalWrite(indicatorLED, HIGH); // 灭
    delay(100);
    Serial.print(".");
  }
  
  Serial.println("\nWi-Fi 连接成功！");
  Serial.print("ESP32 的 IP 地址是: ");
  Serial.println(WiFi.localIP());

  // 💡 4. Wi-Fi 连上后：小红灯长亮 2 秒钟，然后彻底熄灭潜伏
  digitalWrite(indicatorLED, LOW);
  delay(2000);
  digitalWrite(indicatorLED, HIGH);

  // 启动摄像头
  initCamera();
}

void loop() {
  // 📸 实时监控模式：拍完立马传，传完立马拍！
  captureAndUpload();
  
  // 仅保留 200 毫秒的微小延时，防止连续高频发包把路由器或者后端 Celery 撑爆
  // 这样你大约能获得 2~5 FPS 的流畅识别帧率，完全足够安防使用了。
  delay(200); 
}