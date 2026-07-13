#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>

// Wi-Fi 配置
const char* ssid = "YOUR_WIFI_SSID";          // 改成这样
const char* password = "YOUR_WIFI_PASSWORD";

// MQTT Broker
const char* mqtt_server = "YOUR_MQTT_BROKER_IP";
const int mqtt_port = 1883;
const char* mqtt_client_id="xjl-02";
const char* mqtt_name = "YOUR_MQTT_USERNAME";
const char* mqtt_password = "YOUR_MQTT_PASSWORD";

// 独占加密主题定义
const char* topic_control = "/iot/4861/bluemacair/2026/iot/control";

WiFiClient espClient;
PubSubClient client(espClient);

// 硬件外设引脚
const int pinLED = 2;
const int pinLED1 = 4;
const int pinBuzzer = 13;
const int pinRelay = 14;

// 初始化硬件引脚
void initHardware() {
    pinMode(pinLED, OUTPUT);
    pinMode(pinLED1, OUTPUT);
    pinMode(pinBuzzer, OUTPUT);
    pinMode(pinRelay, OUTPUT);
    digitalWrite(pinLED, LOW);
    digitalWrite(pinLED1, LOW);
    digitalWrite(pinBuzzer, LOW);
    digitalWrite(pinRelay, LOW);
}

// 核心：收到 MQTT 云端消息的回调函数
void callback(char* topic, byte* payload, unsigned int length) {
    String message = "";
    for (int i = 0; i < length; i++) {
        message += (char)payload[i];
    }
    Serial.printf("📡 收到公网消息 [%s] -> %s\n", topic, message.c_str());

    String tStr = String(topic);

    // 处理开关量控制 (Format: device:status -> 例如 led:on, buzzer:off)
    if (tStr == topic_control) {
        int colonIdx = message.indexOf(':');
        if (colonIdx != -1) {
            String device = message.substring(0, colonIdx);
            String status = message.substring(colonIdx + 1);
            int targetPin = -1;
            
            if (device == "led") targetPin = pinLED1;
            else if (device == "buzzer") targetPin = pinBuzzer;
            else if (device == "relay") targetPin = pinRelay;

            if (targetPin != -1) {
                int level = (status == "on") ? HIGH : LOW;
                digitalWrite(targetPin, level);
                Serial.printf("🎯 GPIO %d 切换为 %s\n", targetPin, status.c_str());
            }
        }
    }
}

// 自动断线重连信箱
void reconnect() {
    while (!client.connected()) {
        Serial.print("⏳ 正在连接 MQTT 邮局...");
        // 随机生成一个客户端ID，防止冲突
        String clientId = "ESP32Client-" + String(random(0, 0xffff), HEX);
        // 尝试连接时，LED 闪烁一下提示正在拨号
        digitalWrite(pinLED, HIGH);
        delay(50);
        digitalWrite(pinLED, LOW);
        if (client.connect(clientId.c_str(), mqtt_name, mqtt_password)) {
            Serial.println("成功接入！");
            // 重新订阅我们专属的保险箱主题
            client.subscribe(topic_control);
            Serial.println("📥 主题订阅成功，监听云端中...");
            // 💡 物理反馈：MQTT 连接成功，蜂鸣器欢快地滴滴两声！
            for (int i = 0; i < 2; i++) {
                digitalWrite(pinBuzzer, HIGH);
                delay(100);
                digitalWrite(pinBuzzer, LOW);
                delay(100);
            }
        } else {
            Serial.printf("失败, rc=%d. 5秒后重试...\n", client.state());
            delay(5000);
        }
    }
}

void setup() {
    Serial.begin(115200);
    delay(1000);
    initHardware();

    WiFi.begin(ssid, password);

    // Wi-Fi 未连接时：LED 狂闪
    while (WiFi.status() != WL_CONNECTED) {
        digitalWrite(pinLED, HIGH);
        delay(150);
        digitalWrite(pinLED, LOW);
        delay(150);
        Serial.print(".");
    }

    Serial.println("\n📶 Wi-Fi已联网！");

    // 💡 物理反馈：Wi-Fi 连接成功，蜂鸣器长鸣 0.5 秒
    digitalWrite(pinBuzzer, HIGH);
    delay(500);
    digitalWrite(pinBuzzer, LOW);

    Serial.print("IP: "); 
    Serial.println(WiFi.localIP());
    Serial.print("网关: "); 
    Serial.println(WiFi.gatewayIP());
    Serial.print("DNS: "); 
    Serial.println(WiFi.dnsIP(0));

    client.setServer(mqtt_server, mqtt_port);
    client.setCallback(callback); // 绑定接收信箱的回调
}

void loop() {
    if (!client.connected()) {
        reconnect();
    }
    client.loop(); // 保持与公网代理的心跳
}