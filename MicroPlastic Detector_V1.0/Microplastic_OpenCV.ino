#include <LiquidCrystal.h>

// Initialize the library with the numbers of the interface pins
// LiquidCrystal(rs, enable, d4, d5, d6, d7)
LiquidCrystal lcd(12, 11, 5, 4, 3, 2);

void setup() {
  // Start serial communication at a baud rate of 9600
  Serial.begin(9600);

  // Set up the LCD's number of columns and rows
  lcd.begin(16, 2);
  
  // Print a startup message to the LCD.
  lcd.print("Detector Ready");
}

void loop() {
  // Check if there is any data coming from the laptop
  if (Serial.available() > 0) {
    // Read the incoming character
    char signal = Serial.read();

    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Status:");
    lcd.setCursor(0, 1);

    // Update the display based on the signal
    if (signal == '1') {
      lcd.print("Detected! :)");
    } else if (signal == '0') {
      lcd.print("Clean      :)");
    }
  }
}