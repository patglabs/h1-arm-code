import pygame
import serial
import serial.tools.list_ports
import time
import sys

# ==========================================
# --- CONFIGURATION & PARAMETERS ---
# ==========================================
BAUD_RATE = 115200

# Mapping physical keys to specific axes and directions.
KEY_MAPPINGS = {
    pygame.K_w: {"driver": 1, "dir": -1, "name": "Shoulder UP"},
    pygame.K_s: {"driver": 1, "dir": 1,  "name": "Shoulder DOWN"},
    pygame.K_UP:   {"driver": 2, "dir": -1, "name": "Elbow UP"},
    pygame.K_DOWN: {"driver": 2, "dir": 1,  "name": "Elbow DOWN"},
    pygame.K_a: {"driver": 3, "dir": -1, "name": "Base LEFT"},
    pygame.K_d: {"driver": 3, "dir": 1,  "name": "Base RIGHT"},
    pygame.K_q: {"driver": 4, "dir": -1, "name": "Wrist UP"},
    pygame.K_e: {"driver": 4, "dir": 1,  "name": "Wrist DOWN"},
}

# ==========================================
# --- HELPER FUNCTIONS ---
# ==========================================
def get_available_ports():
    """Scans and returns a list of available serial ports, filtering out system tty junk."""
    ports = serial.tools.list_ports.comports()
    valid_ports = []
    
    for port in ports:
        # Filter for typical USB-to-Serial identifiers
        # Linux: ttyUSB, ttyACM | Windows: COM | Mac: cu.usb
        if "USB" in port.device or "ACM" in port.device or "COM" in port.device or "cu.usb" in port.device:
            # We can also append the port description to make it look nicer in the GUI
            valid_ports.append(port.device)
            
    return valid_ports

def send_command(ser, cmd_string):
    """Sends a string command to the ESP32. Returns False if connection is dead."""
    if ser is None or not ser.is_open:
        return False
    try:
        full_cmd = f"{cmd_string}\n"
        ser.write(full_cmd.encode('utf-8'))
        return True
    except (serial.SerialException, OSError):
        return False

# ==========================================
# --- MAIN APPLICATION ---
# ==========================================
def main():
    pygame.init()
    screen = pygame.display.set_mode((500, 400))
    pygame.display.set_caption("Robotic Arm Control Terminal")
    
    font_large = pygame.font.SysFont(None, 36)
    font_small = pygame.font.SysFont(None, 24)

    # State Variables
    app_state = "MENU" # Can be "MENU" or "CONTROL"
    selected_port = None
    ser = None
    available_ports = get_available_ports()
    
    # Auto-reconnect timer
    last_reconnect_time = 0 
    
    active_keys = set()

    running = True
    while running:
        current_time = time.time()
        mouse_pos = pygame.mouse.get_pos()
        click = False

        # 1. Process Pygame Events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    click = True

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if app_state == "CONTROL":
                        # Go back to menu and disconnect
                        app_state = "MENU"
                        if ser:
                            ser.close()
                            ser = None
                        active_keys.clear()
                    else:
                        running = False
                        
                # Handle robot control keys only if connected
                if app_state == "CONTROL" and ser is not None and ser.is_open:
                    if event.key in KEY_MAPPINGS and event.key not in active_keys:
                        active_keys.add(event.key)
                        mapping = KEY_MAPPINGS[event.key]
                        success = send_command(ser, f"J {mapping['driver']} {mapping['dir']}")
                        if not success:
                            ser.close()
                            ser = None # Trigger reconnect logic
                        
            elif event.type == pygame.KEYUP:
                if app_state == "CONTROL" and event.key in active_keys:
                    active_keys.remove(event.key)
                    mapping = KEY_MAPPINGS[event.key]
                    if ser is not None and ser.is_open:
                        send_command(ser, f"S {mapping['driver']}")

        # ---------------------------------------------------------
        # STATE: MENU (Port Selection)
        # ---------------------------------------------------------
        if app_state == "MENU":
            screen.fill((30, 30, 40))
            
            title = font_large.render("Select ESP32 Serial Port", True, (255, 255, 255))
            screen.blit(title, (20, 20))

            # Draw Refresh Button
            refresh_rect = pygame.Rect(350, 20, 120, 30)
            pygame.draw.rect(screen, (100, 100, 150), refresh_rect, border_radius=5)
            screen.blit(font_small.render("Refresh", True, (255,255,255)), (375, 26))
            if click and refresh_rect.collidepoint(mouse_pos):
                available_ports = get_available_ports()

            # Draw Port List
            y_offset = 80
            if not available_ports:
                screen.blit(font_small.render("No ports found. Plug in ESP32 and click Refresh.", True, (200, 100, 100)), (20, y_offset))
            else:
                for port in available_ports:
                    port_rect = pygame.Rect(20, y_offset, 450, 40)
                    color = (70, 70, 90) if port_rect.collidepoint(mouse_pos) else (50, 50, 70)
                    pygame.draw.rect(screen, color, port_rect, border_radius=5)
                    screen.blit(font_large.render(port, True, (200, 255, 200)), (35, y_offset + 8))
                    
                    if click and port_rect.collidepoint(mouse_pos):
                        selected_port = port
                        app_state = "CONTROL"
                        # Try initial connection
                        try:
                            ser = serial.Serial(selected_port, BAUD_RATE, timeout=0.1)
                            time.sleep(1) # Give ESP32 a moment to boot
                        except Exception as e:
                            ser = None # Will auto-reconnect in CONTROL loop
                    
                    y_offset += 50

            instruction = font_small.render("Press ESC to exit.", True, (150, 150, 150))
            screen.blit(instruction, (20, 360))

        # ---------------------------------------------------------
        # STATE: CONTROL & AUTO-RECONNECT
        # ---------------------------------------------------------
        elif app_state == "CONTROL":
            screen.fill((30, 30, 30))
            
            # Read Serial Data (and catch physical disconnects)
            if ser is not None and ser.is_open:
                try:
                    while ser.in_waiting > 0:
                        line = ser.readline().decode('utf-8', errors='ignore').strip()
                        if line:
                            print(f"[ESP32] {line}")
                except (serial.SerialException, OSError):
                    # Cable was likely unplugged
                    print("CONNECTION LOST!")
                    ser.close()
                    ser = None
                    active_keys.clear() # Reset keys so robot doesn't run away on reconnect

            # Auto-Reconnect Logic
            if ser is None or not ser.is_open:
                status_text = font_large.render(f"DISCONNECTED from {selected_port}", True, (255, 100, 100))
                sub_text = font_small.render("Attempting auto-reconnect... Please plug in USB.", True, (200, 200, 200))
                
                # Try to reconnect every 1 second
                if current_time - last_reconnect_time > 1.0:
                    last_reconnect_time = current_time
                    try:
                        ser = serial.Serial(selected_port, BAUD_RATE, timeout=0.1)
                        print(f"Reconnected to {selected_port}!")
                        time.sleep(1) # Important: Wait for ESP32 boot cycle
                    except:
                        pass # Still waiting
            else:
                status_text = font_large.render(f"CONNECTED: {selected_port}", True, (100, 255, 100))
                sub_text = font_small.render("Controls active. Focus window to jog.", True, (200, 200, 200))
                
            screen.blit(status_text, (20, 20))
            screen.blit(sub_text, (20, 50))
            
            # Display active keys
            y_offset = 100
            for key in active_keys:
                action_text = font_large.render(f"Jogging: {KEY_MAPPINGS[key]['name']}", True, (100, 200, 255))
                screen.blit(action_text, (20, y_offset))
                y_offset += 40

            instruction = font_small.render("Press ESC to Disconnect and return to Menu.", True, (150, 150, 150))
            screen.blit(instruction, (20, 360))

        # Update display
        pygame.display.flip()
        time.sleep(0.01) # Keep CPU usage low

    # Cleanup before closing
    if ser is not None and ser.is_open:
        for i in range(1, 5):
            send_command(ser, f"S {i}")
        ser.close()
    pygame.quit()

if __name__ == '__main__':
    main()