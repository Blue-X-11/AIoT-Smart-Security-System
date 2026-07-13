#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ESP32Servo.h>

// Wi-Fi 配置
const char* ssid = "YOUR_WIFI_SSID";          // 改成这样
const char* password = "YOUR_WIFI_PASSWORD"; 

// MQTT Broker 配置
const char* mqtt_server = "YOUR_MQTT_BROKER_IP";
const int mqtt_port = 1883;
const char* mqtt_client_id="xjl-02";
const char* mqtt_name = "YOUR_MQTT_USERNAME";
const char* mqtt_password = "YOUR_MQTT_PASSWORD";

// MQTT 主题
const char* topic_track = "/iot/4861/bluemacair/2026/iot/track";

WiFiClient espClient;
PubSubClient client(espClient);

// 舵机配置
Servo panServo;  // 水平舵机
Servo tiltServo; // 垂直舵机

const int pinLED = 2;
const int pinBuzzer = 13;
const int panPin = 25;   // 接水平信号线
const int tiltPin = 26;  // 接垂直信号线

// 舵机角度范围
const int PAN_MIN = 0;
const int PAN_MAX = 180;
const int TILT_MIN = 45;
const int TILT_MAX = 135;

// 当前角度（初始归中）
int currentPan = 90;
int currentTilt = 90;

// 每次微调的步长（度数）- 与后端 stepSize=5 保持一致
const int stepSize = 5;

// 辅助函数：打印分隔线
void printSeparator() {
    for (int i = 0; i < 50; i++) {
        Serial.print("=");
    }
    Serial.println();
}

// 初始化硬件
void initHardware() {
    pinMode(pinLED, OUTPUT);
    pinMode(pinBuzzer, OUTPUT);
    digitalWrite(pinLED, LOW);
    digitalWrite(pinBuzzer, LOW);
    
    // 初始化舵机定时器
    ESP32PWM::allocateTimer(0);
    ESP32PWM::allocateTimer(1);
    
    panServo.setPeriodHertz(50);
    tiltServo.setPeriodHertz(50);
    panServo.attach(panPin, 500, 2400);
    tiltServo.attach(tiltPin, 500, 2400);
    
    // 初始归中
    panServo.write(currentPan);
    tiltServo.write(currentTilt);
    
    Serial.println("✅ 硬件初始化完成");
    Serial.printf("🦾 舵机初始位置: 水平=%d°, 垂直=%d°\n", currentPan, currentTilt);
}

// MQTT 回调函数 - 接收云台控制指令
void callback(char* topic, byte* payload, unsigned int length) {
    String message = "";
    for (int i = 0; i < length; i++) {
        message += (char)payload[i];
    }
    
    Serial.printf("📡 收到云台指令 [%s] -> %s\n", topic, message.c_str());
    
    String tStr = String(topic);
    
    // 处理云台追踪指令 (left, right, up, down, center)
    if (tStr == topic_track) {
        bool moved = false;
        int oldPan = currentPan;
        int oldTilt = currentTilt;
        
        if (message == "left") { 
            currentPan += stepSize; 
            if (currentPan > PAN_MAX) currentPan = PAN_MAX;
            moved = true;
            Serial.printf("⬅️ 水平左转 %d°\n", stepSize);
        }
        else if (message == "right") { 
            currentPan -= stepSize; 
            if (currentPan < PAN_MIN) currentPan = PAN_MIN;
            moved = true;
            Serial.printf("➡️ 水平右转 %d°\n", stepSize);
        }
        else if (message == "up") { 
            currentTilt -= stepSize; 
            if (currentTilt < TILT_MIN) currentTilt = TILT_MIN;
            moved = true;
            Serial.printf("⬆️ 垂直上仰 %d°\n", stepSize);
        }
        else if (message == "down") { 
            currentTilt += stepSize; 
            if (currentTilt > TILT_MAX) currentTilt = TILT_MAX;
            moved = true;
            Serial.printf("⬇️ 垂直下俯 %d°\n", stepSize);
        }
        else if (message == "center") { 
            currentPan = 90; 
            currentTilt = 90;
            moved = true;
            Serial.println("🎯 云台归中");
        }
        else {
            Serial.printf("⚠️ 未知指令: %s\n", message.c_str());
        }
        
        // 如果角度有变化，执行舵机转动
        if (moved) {
            panServo.write(currentPan);
            tiltServo.write(currentTilt);
            Serial.printf("🦾 云台状态: 水平=%d° (变化: %+d°), 垂直=%d° (变化: %+d°)\n", 
                         currentPan, currentPan - oldPan, 
                         currentTilt, currentTilt - oldTilt);
        }
    }
}

// MQTT 重连函数
void reconnect() {
    while (!client.connected()) {
        Serial.print("⏳ 正在连接 MQTT 服务器...");
        String clientId = "ESP32Client-" + String(random(0, 0xffff), HEX);
        digitalWrite(pinLED, HIGH);
        delay(50);
        digitalWrite(pinLED, LOW);
        
        if (client.connect(clientId.c_str(), mqtt_name, mqtt_password)) {
            Serial.println("✅ 连接成功！");
            // 订阅云台控制主题
            client.subscribe(topic_track);
            Serial.printf("📥 已订阅主题: %s\n", topic_track);
            Serial.println("🎯 云台控制系统就绪，等待指令...");
            
            for (int i = 0; i < 2; i++) {
                digitalWrite(pinBuzzer, HIGH);
                delay(100);
                digitalWrite(pinBuzzer, LOW);
                delay(100);
            }
        } else {
            Serial.printf("❌ 连接失败, rc=%d. 5秒后重试...\n", client.state());
            delay(5000);
        }
    }
}

void setup() {
    Serial.begin(115200);
    delay(1000);
    
    printSeparator();
    Serial.println("🚀 ESP32 云台追踪系统启动");
    printSeparator();
    
    // 初始化硬件
    initHardware();
    
    // 连接 Wi-Fi
    Serial.printf("📶 正在连接 Wi-Fi: %s...\n", ssid);
    WiFi.begin(ssid, password);
    
    while (WiFi.status() != WL_CONNECTED) {
        digitalWrite(pinLED, HIGH);
        delay(150);
        digitalWrite(pinLED, LOW);
        delay(150);
        Serial.print(".");
    }
    Serial.println("\n✅ Wi-Fi 连接成功！");
    Serial.printf("📡 IP 地址: %s\n", WiFi.localIP().toString().c_str());
    Serial.printf("🌐 网关: %s\n", WiFi.gatewayIP().toString().c_str());
    Serial.printf("🔗 MAC: %s\n", WiFi.macAddress().c_str());
    
    // 配置 MQTT
    client.setServer(mqtt_server, mqtt_port);
    client.setCallback(callback);
    
    printSeparator();
}

void loop() {
    // 保持 MQTT 连接
    if (!client.connected()) {
        reconnect();
    }
    client.loop();
    
    // 每 10 秒打印一次状态（可选，用于调试）
    static unsigned long lastStatusTime = 0;
    if (millis() - lastStatusTime > 10000) {
        lastStatusTime = millis();
        Serial.printf("💚 心跳 - 云台状态: 水平=%d°, 垂直=%d°\n", currentPan, currentTilt);
    }
}