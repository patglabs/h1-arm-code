#include <TMCStepper.h>
#include <AccelStepper.h>

// --- CONFIGURATION ---
// At 1/16 microstepping, 3200 steps = 1 full revolution
const int TARGET_STEPS = 800;  
const int MAX_SPEED    = 2000; 
const int ACCEL_RATE   = 1000;
const int RMS_CURRENT  = 1000; // 1000mA for high torque

// --- PINS ---
const int STEP_PIN = 1;
const int DIR_PIN  = 3; 
const int EN_PIN   = 2;
const int UART_PIN = 4; 

#define DRIVER_ADDRESS 0b00 
#define R_SENSE 0.11f       

// Use Hardware Serial1 for the ESP32-S3
TMC2209Stepper driver(&Serial1, R_SENSE, DRIVER_ADDRESS);
AccelStepper stepper(AccelStepper::DRIVER, STEP_PIN, DIR_PIN);

void setup() {
  Serial.begin(115200); 

  // 1. Initialize Pins
  pinMode(EN_PIN, OUTPUT);
  digitalWrite(EN_PIN, LOW); 

  // 2. Start Hardware UART (Pin 4 for both RX/TX)
  Serial1.begin(115200, SERIAL_8N1, UART_PIN, UART_PIN); 
  driver.begin();             

  // 3. Beast Mode & Microstepping
  driver.toff(4);                 // Enable driver logic
  driver.rms_current(RMS_CURRENT); // Set power via code
  driver.microsteps(16);          // FORCE 1/16 microstepping
  driver.en_spreadCycle(true);    // Enable high-torque mode (The Squeak)
  driver.pwm_autoscale(false);    // Assist SpreadCycle stability

  // UART Diagnostic Check
  uint32_t drv_status = driver.DRV_STATUS();
  if (drv_status == 0xFFFFFFFF || drv_status == 0) {
    Serial.println("--- UART ERROR: TX is likely working, but RX is blocked. ---");
    Serial.println("--- Continuing anyway because we heard the squeak! ---");
  } else {
    Serial.print("--- UART SUCCESS! Driver Version: ");
    Serial.println(driver.version());
  }

  // 4. AccelStepper Physics
  stepper.setMaxSpeed(MAX_SPEED);
  stepper.setAcceleration(ACCEL_RATE);
  stepper.moveTo(TARGET_STEPS);

  Serial.println("NOMAD System: Moving 3200 steps (1 Full Turn).");
}

void loop() {
  // If we reach the target, wait and reverse
  if (stepper.distanceToGo() == 0) {
    delay(1000); 
    if (stepper.currentPosition() == TARGET_STEPS) {
      stepper.moveTo(0);
      Serial.println("Returning to Home...");
    } else {
      stepper.moveTo(TARGET_STEPS);
      Serial.println("Rotating 360 degrees...");
    }
  }

  // Must run every loop to calculate pulses
  stepper.run();
}