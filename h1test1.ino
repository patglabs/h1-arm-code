#include <TMCStepper.h>
#include <AccelStepper.h>

// --- GLOBAL CONFIGURATION ---
const int MAX_SPEED    = 800;  
const int ACCEL_RATE   = 200;  // Smooth acceleration to prevent stalling on start
const int DECEL_RATE   = 4000; // Massive acceleration for a rapid, snappy stop

// --- UART DRIVER CONFIGURATION (Drivers 1 & 2 Only) ---
const int RMS_CURRENT  = 1000; 
const int MICROSTEPS   = 16;   
#define R_SENSE 0.11f       
#define DRIVER_ADDRESS 0b00    

// ==========================================
// --- PIN DEFINITIONS (ESP32-S3 Example) ---
// ==========================================
// Driver 1 (UART Enabled) SHOULDER 
const int EN_PIN_1   = 3;
const int STEP_PIN_1 = 42; 
const int DIR_PIN_1  = 2; 
const int UART_PIN_1 = 4; 

// Driver 2 (UART Enabled) ELBOW 
const int EN_PIN_2   = 48;
const int STEP_PIN_2 = 45;
const int DIR_PIN_2  = 46; 
const int UART_PIN_2 = 47; 

// Driver 3 (Standalone) BASE L/R 
const int EN_PIN_3   = 34;
const int STEP_PIN_3 = 33;
const int DIR_PIN_3  = 6; 

// Driver 4 (Standalone) WRIST 
const int EN_PIN_4   = 26;
const int STEP_PIN_4 = 5;
const int DIR_PIN_4  = 7; 

// ==========================================
// --- OBJECT INSTANTIATIONS ---
// ==========================================
TMC2209Stepper driver1(&Serial1, R_SENSE, DRIVER_ADDRESS);
TMC2209Stepper driver2(&Serial2, R_SENSE, DRIVER_ADDRESS);

AccelStepper stepper1(AccelStepper::DRIVER, STEP_PIN_1, DIR_PIN_1);
AccelStepper stepper2(AccelStepper::DRIVER, STEP_PIN_2, DIR_PIN_2);
AccelStepper stepper3(AccelStepper::DRIVER, STEP_PIN_3, DIR_PIN_3);
AccelStepper stepper4(AccelStepper::DRIVER, STEP_PIN_4, DIR_PIN_4);

AccelStepper* steppers[4] = {&stepper1, &stepper2, &stepper3, &stepper4};
const int EN_PINS[4]      = {EN_PIN_1, EN_PIN_2, EN_PIN_3, EN_PIN_4};

const byte MAX_INPUT_LEN = 32;
char inputBuffer[MAX_INPUT_LEN];
byte inputIndex = 0;

void setup() {
  Serial.begin(115200); 
  delay(1000); 

  Serial.println("\n--- 4-Axis Arm Controller Initializing ---");

  for (int i = 0; i < 4; i++) {
    pinMode(EN_PINS[i], OUTPUT);
    digitalWrite(EN_PINS[i], LOW); 
  }

  Serial1.begin(115200, SERIAL_8N1, UART_PIN_1, UART_PIN_1); 
  driver1.begin();             

  Serial2.begin(115200, SERIAL_8N1, UART_PIN_2, UART_PIN_2); 
  driver2.begin();

  setupUARTDriver(driver1, "Shoulder (D1)");
  setupUARTDriver(driver2, "Elbow (D2)");

  for (int i = 0; i < 4; i++) {
    steppers[i]->setMaxSpeed(MAX_SPEED);
    steppers[i]->setAcceleration(ACCEL_RATE);
  }

  Serial.println("\n--- Setup Complete ---");
  Serial.println("Supported Commands:");
  Serial.println("  <1-4> <steps>   : Move exact steps (Legacy)");
  Serial.println("  J <1-4> <1|-1>  : Jog continuous");
  Serial.println("  S <1-4>         : Smooth Stop");
}

void loop() {
  handleSerialCommand();
  for (int i = 0; i < 4; i++) {
    steppers[i]->run(); // Must run continuously to process accel/decel
  }
}

// ==========================================
// --- HELPER FUNCTIONS ---
// ==========================================
void setupUARTDriver(TMC2209Stepper &driver, const char* name) {
  driver.toff(4);                     
  driver.rms_current(RMS_CURRENT);    
  driver.microsteps(MICROSTEPS);      
  driver.en_spreadCycle(true);        
  driver.pwm_autoscale(false);        

  uint32_t drv_status = driver.DRV_STATUS();
  Serial.print(name);
  if (drv_status == 0xFFFFFFFF || drv_status == 0) {
    Serial.println(" -> UART ERROR: TX likely working, RX blocked. Continuing...");
  } else {
    Serial.print(" -> UART SUCCESS! Version: ");
    Serial.println(driver.version());
  }
}

void handleSerialCommand() {
  while (Serial.available() > 0) {
    char inChar = (char)Serial.read();

    if (inChar == '\n' || inChar == '\r') {
      if (inputIndex > 0) {
        inputBuffer[inputIndex] = '\0'; 
        processCommand(inputBuffer);
        inputIndex = 0; 
      }
    } 
    else if (inputIndex < MAX_INPUT_LEN - 1) {
      inputBuffer[inputIndex++] = inChar;
    }
  }
}

void processCommand(char* cmd) {
  char cmdType;
  int driverNum;
  long param; // Could be steps or direction

  // 1. Try parsing the new explicit command format (e.g., "J 1 1" or "S 1")
  if (sscanf(cmd, "%c %d %ld", &cmdType, &driverNum, &param) >= 2) {
    
    if (driverNum < 1 || driverNum > 4) {
      Serial.println("-> Error: Invalid driver number.");
      return;
    }

    int idx = driverNum - 1;

    if (cmdType == 'J' || cmdType == 'j') {
      // RESET to normal, smooth acceleration for starting
      steppers[idx]->setAcceleration(ACCEL_RATE);
      
      long target = (param > 0) ? 100000000 : -100000000;
      steppers[idx]->move(target); 
      Serial.print("-> Jogging Driver "); Serial.println(driverNum);
    } 
    else if (cmdType == 'S' || cmdType == 's') {
      // TEMPORARILY CRANK acceleration to slam the brakes
      steppers[idx]->setAcceleration(DECEL_RATE);
      steppers[idx]->stop();
      Serial.print("-> Stopping Driver "); Serial.println(driverNum);
    }
  } 
  // 2. Fallback to Legacy format (e.g., "1 200")
  else if (sscanf(cmd, "%d %ld", &driverNum, &param) == 2) {
    if (driverNum >= 1 && driverNum <= 4) {
      // Ensure we are using standard smooth acceleration for legacy moves
      steppers[driverNum - 1]->setAcceleration(ACCEL_RATE);
      steppers[driverNum - 1]->move(param);
      
      Serial.print("-> Legacy Move: Driver "); Serial.print(driverNum);
      Serial.print(" moving "); Serial.println(param);
    }
  } else {
    Serial.println("-> Error: Unrecognized command format.");
  }
}