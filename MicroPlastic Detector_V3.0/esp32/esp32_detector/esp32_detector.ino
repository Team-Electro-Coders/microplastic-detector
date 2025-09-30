/*
 * ESP8266 Microplastic Detector - Main Firmware
 * Optimized for low power and reliable operation
 * Updated for standard 16-pin parallel LCD
 */

#include <ESP8266WiFi.h>
#include <ESPAsyncWebServer.h>
#include <ArduinoJson.h>
#include <LiquidCrystal.h>  // Standard parallel LCD library
#include <EEPROM.h>
#include <FS.h>

// Firmware information
#define FIRMWARE_VERSION "3.0"
#define BUILD_DATE __DATE__
#define BUILD_TIME __TIME__

// Serial communication
#define SERIAL_BAUD_RATE 115200

// LCD Configuration (16x2 standard parallel LCD)
#define LCD_COLUMNS 16
#define LCD_ROWS 2

// WiFi Configuration - Station Mode
#define WIFI_SSID ""           // Leave empty if not using WiFi connection
#define WIFI_PASSWORD ""

// WiFi Configuration - Access Point Mode
#define AP_SSID "MicroplasticDetector"
#define AP_PASSWORD "12345678"  // Minimum 8 characters

// Web Server Configuration
#define WEB_SERVER_PORT 80

// GPIO Pin Configuration
#define STATUS_LED_PIN D0      // GPIO16 - Status LED
#define HEARTBEAT_LED_PIN D1   // GPIO5 - Heartbeat LED

// Timing Configuration (in milliseconds)
#define DEFAULT_LCD_UPDATE_INTERVAL 2000    // 2 seconds
#define DEFAULT_HEARTBEAT_INTERVAL 5000     // 5 seconds
#define PC_CONNECTION_TIMEOUT 15000         // 15 seconds

// EEPROM Configuration
#define EEPROM_SIZE 512  // bytes

// LCD Pin definitions (based on your connection table)
#define LCD_RS  D2   // GPIO4 - Register Select
#define LCD_E   D3   // GPIO0 - Enable
#define LCD_D4  D4   // GPIO2 - Data Bit 4
#define LCD_D5  D5   // GPIO14 - Data Bit 5
#define LCD_D6  D6   // GPIO12 - Data Bit 6
#define LCD_D7  D7   // GPIO13 - Data Bit 7

// Hardware setup - Standard 16-pin LCD in 4-bit mode
LiquidCrystal lcd(LCD_RS, LCD_E, LCD_D4, LCD_D5, LCD_D6, LCD_D7);

AsyncWebServer server(WEB_SERVER_PORT);

// System state
struct SystemState {
  String mode = "standby";  // standby, detect, clean
  int particleCount = 0;
  float meanSize = 0.0;
  float concentration = 0.0;
  bool pcConnected = false;
  unsigned long lastUpdate = 0;
} state;

// Timing
unsigned long lcdUpdateInterval = DEFAULT_LCD_UPDATE_INTERVAL;
unsigned long lastLcdUpdate = 0;
unsigned long heartbeatInterval = DEFAULT_HEARTBEAT_INTERVAL;
unsigned long lastHeartbeat = 0;
unsigned long bootTime = 0;

// EEPROM memory addresses
#define EEPROM_LCD_INTERVAL_ADDR 0
#define EEPROM_HEARTBEAT_INTERVAL_ADDR 4
#define EEPROM_MAGIC_NUMBER_ADDR 8
#define EEPROM_MAGIC_VALUE 0x12345678

void setup() {
  Serial.begin(SERIAL_BAUD_RATE);
  Serial.println("\n\n========================================");
  Serial.println("ESP8266 Microplastic Detector");
  Serial.println("Version: " + String(FIRMWARE_VERSION));
  Serial.println("Build: " + String(BUILD_DATE) + " " + String(BUILD_TIME));
  Serial.println("========================================\n");
  
  bootTime = millis();
  
  // Initialize hardware
  initializeLCD();
  initializePins();
  initializeSPIFFS();
  initializeEEPROM();
  initializeWiFi();
  initializeWebServer();
  
  // Load configuration from EEPROM
  loadConfiguration();
  
  Serial.println("\n========================================");
  Serial.println("System Ready!");
  Serial.println("========================================\n");
  
  updateLCD();
}

void loop() {
  unsigned long currentTime = millis();
  
  // Update LCD periodically
  if (currentTime - lastLcdUpdate >= lcdUpdateInterval) {
    updateLCD();
    lastLcdUpdate = currentTime;
  }
  
  // Send heartbeat to check PC connection
  if (currentTime - lastHeartbeat >= heartbeatInterval) {
    checkPCConnection();
    lastHeartbeat = currentTime;
  }
  
  // Handle watchdog - reset if no updates for too long
  if (currentTime - state.lastUpdate > PC_CONNECTION_TIMEOUT) {
    if (state.pcConnected) {
      state.pcConnected = false;
      Serial.println("PC connection timeout");
    }
    if (state.mode == "detect") {
      state.mode = "standby";
      Serial.println("Auto-switching to standby mode");
    }
  }
  
  delay(100);
}

void initializeLCD() {
  Serial.print("Initializing LCD (16-pin parallel)...");
  
  // Initialize LCD with 16 columns and 2 rows
  lcd.begin(LCD_COLUMNS, LCD_ROWS);
  
  // Clear and display startup message
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Microplastic");
  lcd.setCursor(0, 1);
  lcd.print("Detector v" + String(FIRMWARE_VERSION));
  
  Serial.println(" Done");
  delay(2000);
}

void initializePins() {
  Serial.print("Initializing pins...");
  pinMode(STATUS_LED_PIN, OUTPUT);
  pinMode(HEARTBEAT_LED_PIN, OUTPUT);
  digitalWrite(STATUS_LED_PIN, LOW);
  digitalWrite(HEARTBEAT_LED_PIN, LOW);
  Serial.println(" Done");
}

void initializeSPIFFS() {
  Serial.print("Initializing SPIFFS...");
  if (!SPIFFS.begin()) {
    Serial.println(" Failed!");
    Serial.println("SPIFFS mount failed - web files will not be available");
  } else {
    Serial.println(" Done");
    FSInfo fs_info;
    SPIFFS.info(fs_info);
    Serial.print("SPIFFS Total: ");
    Serial.print(fs_info.totalBytes);
    Serial.print(" bytes, Used: ");
    Serial.print(fs_info.usedBytes);
    Serial.println(" bytes");
  }
}

void initializeEEPROM() {
  Serial.print("Initializing EEPROM...");
  EEPROM.begin(EEPROM_SIZE);
  
  // Check if EEPROM has been initialized
  uint32_t magic;
  EEPROM.get(EEPROM_MAGIC_NUMBER_ADDR, magic);
  
  if (magic != EEPROM_MAGIC_VALUE) {
    Serial.println(" First boot - initializing defaults");
    EEPROM.put(EEPROM_LCD_INTERVAL_ADDR, DEFAULT_LCD_UPDATE_INTERVAL);
    EEPROM.put(EEPROM_HEARTBEAT_INTERVAL_ADDR, DEFAULT_HEARTBEAT_INTERVAL);
    EEPROM.put(EEPROM_MAGIC_NUMBER_ADDR, EEPROM_MAGIC_VALUE);
    EEPROM.commit();
  } else {
    Serial.println(" Done");
  }
}

void initializeWiFi() {
  Serial.println("\nInitializing WiFi...");
  WiFi.mode(WIFI_AP_STA);
  
  // Try to connect to existing WiFi first
  if (strlen(WIFI_SSID) > 0) {
    Serial.print("Connecting to WiFi: ");
    Serial.print(WIFI_SSID);
    Serial.print(" ");
    
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 20) {
      delay(500);
      Serial.print(".");
      attempts++;
    }
    
    if (WiFi.status() == WL_CONNECTED) {
      Serial.println(" Connected!");
      Serial.print("IP Address: ");
      Serial.println(WiFi.localIP());
      Serial.print("Signal Strength: ");
      Serial.print(WiFi.RSSI());
      Serial.println(" dBm");
    } else {
      Serial.println(" Failed!");
    }
  }
  
  // Always start AP for fallback
  Serial.print("\nStarting Access Point: ");
  Serial.print(AP_SSID);
  Serial.print(" ");
  
  WiFi.softAP(AP_SSID, AP_PASSWORD);
  delay(100);
  
  Serial.println(" Done");
  Serial.print("AP IP Address: ");
  Serial.println(WiFi.softAPIP());
  Serial.print("AP MAC: ");
  Serial.println(WiFi.softAPmacAddress());
}

void initializeWebServer() {
  Serial.println("\nInitializing web server...");
  
  // CORS headers
  DefaultHeaders::Instance().addHeader("Access-Control-Allow-Origin", "*");
  DefaultHeaders::Instance().addHeader("Access-Control-Allow-Methods", "GET, POST, PUT");
  DefaultHeaders::Instance().addHeader("Access-Control-Allow-Headers", "Content-Type");
  
  // Status endpoint
  server.on("/status", HTTP_GET, [](AsyncWebServerRequest *request) {
    DynamicJsonDocument doc(512);
    doc["mode"] = state.mode;
    doc["particle_count"] = state.particleCount;
    doc["mean_size_mm"] = serialized(String(state.meanSize, 3));
    doc["concentration_per_ml"] = serialized(String(state.concentration, 1));
    doc["pc_connected"] = state.pcConnected;
    doc["uptime"] = (millis() - bootTime) / 1000;
    doc["free_heap"] = ESP.getFreeHeap();
    doc["wifi_connected"] = WiFi.status() == WL_CONNECTED;
    doc["ap_clients"] = WiFi.softAPgetStationNum();
    doc["firmware_version"] = FIRMWARE_VERSION;
    
    String response;
    serializeJson(doc, response);
    request->send(200, "application/json", response);
  });
  
  // Mode control endpoints
  server.on("/mode/detect", HTTP_POST, [](AsyncWebServerRequest *request) {
    state.mode = "detect";
    digitalWrite(STATUS_LED_PIN, HIGH);
    Serial.println("Mode: DETECT");
    request->send(200, "text/plain", "Mode set to DETECT");
  });
  
  server.on("/mode/clean", HTTP_POST, [](AsyncWebServerRequest *request) {
    state.mode = "clean";
    digitalWrite(STATUS_LED_PIN, LOW);
    Serial.println("Mode: CLEAN");
    request->send(200, "text/plain", "Mode set to CLEAN");
  });
  
  server.on("/mode/standby", HTTP_POST, [](AsyncWebServerRequest *request) {
    state.mode = "standby";
    digitalWrite(STATUS_LED_PIN, LOW);
    Serial.println("Mode: STANDBY");
    request->send(200, "text/plain", "Mode set to STANDBY");
  });
  
  // Stats update endpoint
  server.on("/stats", HTTP_POST, [](AsyncWebServerRequest *request) {
  }, NULL, [](AsyncWebServerRequest *request, uint8_t *data, size_t len, size_t index, size_t total) {
    DynamicJsonDocument doc(512);
    DeserializationError error = deserializeJson(doc, (char*)data);
    
    if (error) {
      Serial.print("JSON parse error: ");
      Serial.println(error.c_str());
      request->send(400, "text/plain", "Invalid JSON");
      return;
    }
    
    state.particleCount = doc["count"] | 0;
    state.meanSize = doc["mean_size_mm"] | 0.0;
    state.concentration = doc["concentration_per_ml"] | 0.0;
    state.pcConnected = true;
    state.lastUpdate = millis();
    
    request->send(200, "text/plain", "Stats updated");
  });
  
  // Configuration endpoints
  server.on("/config", HTTP_GET, [](AsyncWebServerRequest *request) {
    DynamicJsonDocument doc(1024);
    doc["lcd_update_interval"] = lcdUpdateInterval;
    doc["heartbeat_interval"] = heartbeatInterval;
    doc["wifi_ssid"] = WIFI_SSID;
    doc["ap_ssid"] = AP_SSID;
    doc["firmware_version"] = FIRMWARE_VERSION;
    doc["free_heap"] = ESP.getFreeHeap();
    
    String response;
    serializeJson(doc, response);
    request->send(200, "application/json", response);
  });
  
  server.on("/config", HTTP_POST, [](AsyncWebServerRequest *request) {
  }, NULL, [](AsyncWebServerRequest *request, uint8_t *data, size_t len, size_t index, size_t total) {
    DynamicJsonDocument doc(1024);
    if (deserializeJson(doc, (char*)data) == DeserializationError::Ok) {
      if (doc.containsKey("lcd_update_interval")) {
        unsigned long newInterval = doc["lcd_update_interval"];
        if (newInterval >= 500 && newInterval <= 60000) {
          lcdUpdateInterval = newInterval;
        }
      }
      if (doc.containsKey("heartbeat_interval")) {
        unsigned long newInterval = doc["heartbeat_interval"];
        if (newInterval >= 1000 && newInterval <= 300000) {
          heartbeatInterval = newInterval;
        }
      }
      saveConfiguration();
      request->send(200, "text/plain", "Configuration updated");
    } else {
      request->send(400, "text/plain", "Invalid JSON");
    }
  });
  
  // Restart endpoint
  server.on("/restart", HTTP_POST, [](AsyncWebServerRequest *request) {
    request->send(200, "text/plain", "Restarting ESP8266...");
    delay(1000);
    ESP.restart();
  });
  
  // Health check
  server.on("/health", HTTP_GET, [](AsyncWebServerRequest *request) {
    request->send(200, "text/plain", "OK");
  });
  
  // Serve static files from SPIFFS
  server.serveStatic("/", SPIFFS, "/").setDefaultFile("index.html");
  
  // 404 handler
  server.onNotFound([](AsyncWebServerRequest *request) {
    Serial.print("404: ");
    Serial.println(request->url());
    request->send(404, "text/plain", "Not found");
  });
  
  server.begin();
  Serial.println("Web server started on port " + String(WEB_SERVER_PORT));
}

void updateLCD() {
  lcd.clear();
  
  // Line 1: Mode and connection status
  lcd.setCursor(0, 0);
  
  if (state.mode == "detect") {
    lcd.print("DETECT");
  } else if (state.mode == "clean") {
    lcd.print("CLEAN");
  } else {
    lcd.print("STANDBY");
  }
  
  if (state.pcConnected) {
    lcd.print(" *PC");
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    lcd.print(" WiFi");
  }
  
  // Line 2: Stats or status
  lcd.setCursor(0, 1);
  
  if (state.mode == "detect" && state.particleCount > 0) {
    lcd.print("P:");
    lcd.print(state.particleCount);
    lcd.print(" ");
    
    if (state.particleCount < 100) {
      lcd.print("S:");
      lcd.print(state.meanSize, 2);
    }
  } else if (state.mode == "clean") {
    lcd.print("Cleaning...");
  } else {
    if (WiFi.status() == WL_CONNECTED) {
      lcd.print(WiFi.localIP().toString().substring(0, 16));
    } else {
      lcd.print("Clients:");
      lcd.print(WiFi.softAPgetStationNum());
    }
  }
  
  // Heartbeat LED
  digitalWrite(HEARTBEAT_LED_PIN, !digitalRead(HEARTBEAT_LED_PIN));
}

void checkPCConnection() {
  unsigned long timeSinceUpdate = millis() - state.lastUpdate;
  
  if (timeSinceUpdate > heartbeatInterval * 2) {
    if (state.pcConnected) {
      Serial.println("PC connection lost");
    }
    state.pcConnected = false;
  }
  
  Serial.print("[");
  Serial.print((millis() - bootTime) / 1000);
  Serial.print("s] Mode: ");
  Serial.print(state.mode);
  Serial.print(" | Particles: ");
  Serial.print(state.particleCount);
  Serial.print(" | PC: ");
  Serial.print(state.pcConnected ? "Connected" : "Disconnected");
  Serial.print(" | Free Heap: ");
  Serial.print(ESP.getFreeHeap());
  Serial.println(" bytes");
}

void loadConfiguration() {
  Serial.print("Loading configuration from EEPROM...");
  
  uint32_t magic;
  EEPROM.get(EEPROM_MAGIC_NUMBER_ADDR, magic);
  
  if (magic == EEPROM_MAGIC_VALUE) {
    unsigned long storedLcdInterval;
    EEPROM.get(EEPROM_LCD_INTERVAL_ADDR, storedLcdInterval);
    if (storedLcdInterval >= 500 && storedLcdInterval <= 60000) {
      lcdUpdateInterval = storedLcdInterval;
    }
    
    unsigned long storedHeartbeatInterval;
    EEPROM.get(EEPROM_HEARTBEAT_INTERVAL_ADDR, storedHeartbeatInterval);
    if (storedHeartbeatInterval >= 1000 && storedHeartbeatInterval <= 300000) {
      heartbeatInterval = storedHeartbeatInterval;
    }
    
    Serial.println(" Done");
    Serial.print("  LCD Interval: ");
    Serial.print(lcdUpdateInterval);
    Serial.println(" ms");
    Serial.print("  Heartbeat Interval: ");
    Serial.print(heartbeatInterval);
    Serial.println(" ms");
  } else {
    Serial.println(" Using defaults");
  }
}

void saveConfiguration() {
  Serial.print("Saving configuration to EEPROM...");
  
  EEPROM.put(EEPROM_LCD_INTERVAL_ADDR, lcdUpdateInterval);
  EEPROM.put(EEPROM_HEARTBEAT_INTERVAL_ADDR, heartbeatInterval);
  EEPROM.put(EEPROM_MAGIC_NUMBER_ADDR, EEPROM_MAGIC_VALUE);
  
  if (EEPROM.commit()) {
    Serial.println(" Done");
  } else {
    Serial.println(" Failed!");
  }
}