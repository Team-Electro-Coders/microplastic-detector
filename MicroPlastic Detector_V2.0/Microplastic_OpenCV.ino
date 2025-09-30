#include <LiquidCrystal.h>

// LCD pin connections: RS, E, D4, D5, D6, D7
LiquidCrystal lcd(12, 11, 5, 4, 3, 2);

// Update these to match classes.txt in your model
const char* classes[] = {"fiber", "fragment", "film", "bead", "other"};
const int NUM_CLASSES = 5;

// Enhanced settings
const unsigned long TIMEOUT_MS = 5000;  // 5 second timeout
const int MAX_MESSAGE_LENGTH = 32;
const int LED_PIN = 13;  // Built-in LED for status indication

// State variables
unsigned long lastMessageTime = 0;
bool systemActive = false;
int currentConc = -1;
int currentType = -1;
String lastValidMessage = "";

// Statistics
unsigned long totalMessages = 0;
unsigned long invalidMessages = 0;

void setup() {
  Serial.begin(9600);
  lcd.begin(16, 2);
  pinMode(LED_PIN, OUTPUT);
  
  // Enhanced startup sequence
  lcd.clear();
  lcd.print("Microplastic");
  lcd.setCursor(0, 1);
  lcd.print("Detector v2.0");
  
  // LED startup indication
  for (int i = 0; i < 3; i++) {
    digitalWrite(LED_PIN, HIGH);
    delay(200);
    digitalWrite(LED_PIN, LOW);
    delay(200);
  }
  
  delay(2000);
  displayWaitingStatus();
  
  Serial.println("Arduino Ready - Enhanced Microplastic Detector v2.0");
}

void loop() {
  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    
    if (line.length() > 0 && line.length() <= MAX_MESSAGE_LENGTH) {
      totalMessages++;
      
      if (parseAndDisplay(line)) {
        lastMessageTime = millis();
        systemActive = true;
        digitalWrite(LED_PIN, HIGH);  // LED on when receiving valid data
        lastValidMessage = line;
      } else {
        invalidMessages++;
        displayErrorMessage("Parse Error");
      }
    }
  }
  
  // Check for timeout
  if (systemActive && (millis() - lastMessageTime > TIMEOUT_MS)) {
    systemActive = false;
    digitalWrite(LED_PIN, LOW);
    displayTimeoutStatus();
  }
  
  // Blink LED when inactive
  if (!systemActive) {
    static unsigned long lastBlink = 0;
    if (millis() - lastBlink > 1000) {
      digitalWrite(LED_PIN, !digitalRead(LED_PIN));
      lastBlink = millis();
    }
  }
}

bool parseAndDisplay(String message) {
  int concCode = -1;
  int typeCode = -1;
  
  // Enhanced parsing with better error checking
  int cPos = message.indexOf('C');
  int semicolon = message.indexOf(';');
  int tPos = message.indexOf('T');
  
  // Validate message format
  if (cPos < 0 || semicolon < 0 || tPos < 0) {
    return false;
  }
  
  if (cPos >= semicolon || semicolon >= tPos) {
    return false;
  }
  
  // Extract concentration code
  String concStr = message.substring(cPos + 1, semicolon);
  if (concStr.length() == 0 || !isDigit(concStr.charAt(0))) {
    return false;
  }
  concCode = concStr.toInt();
  
  // Extract type code
  String typeStr = message.substring(tPos + 1);
  if (typeStr.length() == 0) {
    return false;
  }
  
  // Handle negative type codes (e.g., -1 for none)
  if (typeStr.charAt(0) == '-') {
    if (typeStr.length() < 2 || !isDigit(typeStr.charAt(1))) {
      return false;
    }
    typeCode = -typeStr.substring(1).toInt();
  } else if (isDigit(typeStr.charAt(0))) {
    typeCode = typeStr.toInt();
  } else {
    return false;
  }
  
  // Validate ranges
  if (concCode < 0 || concCode > 2) {
    return false;
  }
  
  // Update current state
  currentConc = concCode;
  currentType = typeCode;
  
  // Display the information
  displayResults(concCode, typeCode);
  
  return true;
}

void displayResults(int concCode, int typeCode) {
  lcd.clear();
  
  // Display concentration with enhanced formatting
  lcd.setCursor(0, 0);
  lcd.print("Conc: ");
  switch (concCode) {
    case 0:
      lcd.print("LOW");
      break;
    case 1:
      lcd.print("MEDIUM");
      break;
    case 2:
      lcd.print("HIGH");
      break;
    default:
      lcd.print("ERROR");
      break;
  }
  
  // Display type with enhanced formatting
  lcd.setCursor(0, 1);
  lcd.print("Type: ");
  
  if (typeCode >= 0 && typeCode < NUM_CLASSES) {
    lcd.print(classes[typeCode]);
  } else if (typeCode == -1) {
    lcd.print("none");
  } else {
    lcd.print("unknown");
  }
}

void displayWaitingStatus() {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Waiting for");
  lcd.setCursor(0, 1);
  lcd.print("data stream...");
}

void displayTimeoutStatus() {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Connection");
  lcd.setCursor(0, 1);
  lcd.print("timeout!");
  
  delay(2000);
  
  // Show last known values if available
  if (currentConc >= 0 && currentType >= -1) {
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Last: ");
    switch (currentConc) {
      case 0: lcd.print("L"); break;
      case 1: lcd.print("M"); break;
      case 2: lcd.print("H"); break;
    }
    
    lcd.setCursor(0, 1);
    if (currentType >= 0 && currentType < NUM_CLASSES) {
      lcd.print(classes[currentType]);
    } else {
      lcd.print("none");
    }
  } else {
    displayWaitingStatus();
  }
}

void displayErrorMessage(String error) {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Error:");
  lcd.setCursor(0, 1);
  lcd.print(error);
  
  delay(1000);
  
  // Return to previous display or waiting status
  if (systemActive && currentConc >= 0) {
    displayResults(currentConc, currentType);
  } else {
    displayWaitingStatus();
  }
}

// Function to display statistics (called via serial command)
void displayStatistics() {
  Serial.println("=== Arduino Statistics ===");
  Serial.print("Total messages: ");
  Serial.println(totalMessages);
  Serial.print("Invalid messages: ");
  Serial.println(invalidMessages);
  Serial.print("Success rate: ");
  if (totalMessages > 0) {
    Serial.print((totalMessages - invalidMessages) * 100 / totalMessages);
    Serial.println("%");
  } else {
    Serial.println("N/A");
  }
  Serial.print("System active: ");
  Serial.println(systemActive ? "Yes" : "No");
  Serial.print("Last valid message: ");
  Serial.println(lastValidMessage);
  Serial.println("=========================");
}