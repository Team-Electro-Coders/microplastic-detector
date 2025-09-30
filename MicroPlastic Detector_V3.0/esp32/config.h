/*
 * ESP32 Microplastic Detector Configuration
 * Modify these values according to your hardware setup
 */

#ifndef CONFIG_H
#define CONFIG_H

// WiFi Configuration
#define WIFI_SSID "YourHomeWiFi"        // Replace with your WiFi network name
#define WIFI_PASSWORD "YourPassword"     // Replace with your WiFi password

// Access Point Configuration (fallback)
#define AP_SSID "ESP32_Detector"
#define AP_PASSWORD "microplastic123"

// Hardware Pin Definitions
#define LCD_ADDRESS 0x27                // I2C address for LCD (common: 0x27, 0x3F)
#define LCD_SDA_PIN 21                  // ESP32 default SDA pin
#define LCD_SCL_PIN 22                  // ESP32 default SCL pin
#define STATUS_LED_PIN 2                // Built-in LED for status indication
#define HEARTBEAT_LED_PIN 4             // Optional external LED for heartbeat

// System Configuration
#define SERIAL_BAUD_RATE 115200
#define EEPROM_SIZE 512

// Timing Configuration (milliseconds)
#define DEFAULT_LCD_UPDATE_INTERVAL 1000
#define DEFAULT_HEARTBEAT_INTERVAL 30000
#define PC_CONNECTION_TIMEOUT 60000

// Web Server Configuration
#define WEB_SERVER_PORT 80
#define MAX_JSON_SIZE 1024

// Display Configuration
#define LCD_COLUMNS 16
#define LCD_ROWS 2

// System Limits
#define MAX_PARTICLE_COUNT 9999
#define MAX_SIZE_DISPLAY 99.99

// Version Information
#define FIRMWARE_VERSION "2.0.0"
#define BUILD_DATE __DATE__
#define BUILD_TIME __TIME__

#endif // CONFIG_H