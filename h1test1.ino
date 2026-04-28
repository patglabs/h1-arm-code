#include <TMCStepper.h>
#include <AccelStepper.h>

// --- GLOBAL CONFIGURATION ---
const int MAX_SPEED    = 200; 
const int ACCEL_RATE   = 100;

// --- UART DRIVER CONFIGURATION (Drivers 1 & 2 Only) ---
const int RMS_CURRENT  = 1000; // 1000mA for high torque
const int MICROSTEPS   = 16;   // 1/16 microstepping
#define R_SENSE 0.11f       
#define DRIVER_ADDRESS 0b00    // Assuming separate UART pins, address can be 00 for both

// ==========================================
// --- PIN DEFINITIONS (ESP32-S3 Example) ---
// ==========================================

// Driver 1 (UART Enabled) (bottom right)
const int EN_PIN_1   = 3;
const int STEP_PIN_1 = 42; // was 1
const int DIR_PIN_1  = 2; 
const int UART_PIN_1 = 4; // Uses Serial1 was 4

// Driver 2 (UART Enabled) (top right)
const int EN_PIN_2   = 48;
const int STEP_PIN_2 = 45;
const int DIR_PIN_2  = 46; 
const int UART_PIN_2 = 47; // Uses Serial2

// Driver 3 (Standalone - No UART) (bottom left)
const int EN_PIN_3   = 34;
const int STEP_PIN_3 = 33;
const int DIR_PIN_3  = 6; 

// Driver 4 (Standalone - No UART) (top left)
const int EN_PIN_4   = 26;
const int STEP_PIN_4 = 5;
const int DIR_PIN_4  = 7; 

// ==========================================
// --- OBJECT INSTANTIATIONS ---
// ==========================================

// UART Drivers (TMC2209)
TMC2209Stepper driver1(&Serial1, R_SENSE, DRIVER_ADDRESS);
TMC2209Stepper driver2(&Serial2, R_SENSE, DRIVER_ADDRESS);

// AccelStepper Objects
AccelStepper stepper1(AccelStepper::DRIVER, STEP_PIN_1, DIR_PIN_1);
AccelStepper stepper2(AccelStepper::DRIVER, STEP_PIN_2, DIR_PIN_2);
AccelStepper stepper3(AccelStepper::DRIVER, STEP_PIN_3, DIR_PIN_3);
AccelStepper stepper4(AccelStepper::DRIVER, STEP_PIN_4, DIR_PIN_4);

// Array of pointers for easier looping
AccelStepper* steppers[4] = {&stepper1, &stepper2, &stepper3, &stepper4};
const int EN_PINS[4]      = {EN_PIN_1, EN_PIN_2, EN_PIN_3, EN_PIN_4};

// Serial Input Buffer
const byte MAX_INPUT_LEN = 32;
char inputBuffer[MAX_INPUT_LEN];
byte inputIndex = 0;

void setup() {
  Serial.begin(115200); 
  delay(1000); // Give serial monitor time to connect

  Serial.println("\n--- Multi-Stepper Test Initializing ---");

  // 1. Initialize All Enable Pins
  for (int i = 0; i < 4; i++) {
    pinMode(EN_PINS[i], OUTPUT);
    digitalWrite(EN_PINS[i], LOW); // Enable drivers
  }

  // 2. Start Hardware UART for Drivers 1 & 2
  // ESP32-S3 allows mapping hardware serial to any pin (Half-Duplex mode)
  Serial1.begin(115200, SERIAL_8N1, UART_PIN_1, UART_PIN_1); 
  driver1.begin();             

  Serial2.begin(115200, SERIAL_8N1, UART_PIN_2, UART_PIN_2); 
  driver2.begin();

  // 3. Configure UART Drivers (Drivers 1 & 2)
  setupUARTDriver(driver1, "Driver 1");
  setupUARTDriver(driver2, "Driver 2");

  // 4. Configure AccelStepper Physics for All Drivers
  for (int i = 0; i < 4; i++) {
    steppers[i]->setMaxSpeed(MAX_SPEED);
    steppers[i]->setAcceleration(ACCEL_RATE);
  }

  Serial.println("\n--- Setup Complete ---");
  Serial.println("Format to move: <DRIVER_NUM> <STEPS>");
  Serial.println("Example: '1 200' moves Driver 1 forward 200 steps.");
  Serial.println("Example: '3 -800' moves Driver 3 backward 800 steps.");
}

void loop() {
  // 1. Non-blocking check for Serial commands
  handleSerialCommand();

  // 2. Must run constantly to calculate step pulses for all motors
  for (int i = 0; i < 4; i++) {
    steppers[i]->run();
  }
}

// ==========================================
// --- HELPER FUNCTIONS ---
// ==========================================

void setupUARTDriver(TMC2209Stepper &driver, const char* name) {
  driver.toff(4);                     // Enable driver logic
  driver.rms_current(RMS_CURRENT);    // Set power via code
  driver.microsteps(MICROSTEPS);      // Set microstepping
  driver.en_spreadCycle(true);        // Enable high-torque mode (The Squeak)
  driver.pwm_autoscale(false);        // Assist SpreadCycle stability

  // UART Diagnostic Check
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

    // If end of line character received
    if (inChar == '\n' || inChar == '\r') {
      if (inputIndex > 0) {
        inputBuffer[inputIndex] = '\0'; // Null-terminate the string
        processCommand(inputBuffer);
        inputIndex = 0; // Reset buffer index
      }
    } 
    // Otherwise add to buffer
    else if (inputIndex < MAX_INPUT_LEN - 1) {
      inputBuffer[inputIndex++] = inChar;
    }
  }
}

void processCommand(char* cmd) {
  int driverNum;
  long steps;

  // Parse the command using sscanf: looking for an int and a long integer
  int numParsed = sscanf(cmd, "%d %ld", &driverNum, &steps);

  if (numParsed == 2) {
    if (driverNum >= 1 && driverNum <= 4) {
      steppers[driverNum - 1]->move(steps);
      Serial.print("-> Command Accepted: Driver ");
      Serial.print(driverNum);
      Serial.print(" moving ");
      Serial.print(steps);
      Serial.println(" steps from current position.");
    } else {
      Serial.println("-> Error: Driver number must be 1, 2, 3, or 4.");
    }
  } else {
    Serial.println("-> Error: Invalid format. Please use: <1-4> <+-STEPS>");
  }
}