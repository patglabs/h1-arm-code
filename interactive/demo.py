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
# Only the "name" value is translated for the GUI.
KEY_MAPPINGS = {
    pygame.K_w: {"driver": 1, "dir": -1, "name": "Épaule HAUT"},
    pygame.K_s: {"driver": 1, "dir": 1,  "name": "Épaule BAS"},
    pygame.K_UP:   {"driver": 2, "dir": -1, "name": "Coude HAUT"},
    pygame.K_DOWN: {"driver": 2, "dir": 1,  "name": "Coude BAS"},
    pygame.K_a: {"driver": 3, "dir": -1, "name": "Base GAUCHE"},
    pygame.K_d: {"driver": 3, "dir": 1,  "name": "Base DROITE"},
    pygame.K_q: {"driver": 4, "dir": -1, "name": "Poignet HAUT"},
    pygame.K_e: {"driver": 4, "dir": 1,  "name": "Poignet BAS"},
}

# ==========================================
# --- HELPER FUNCTIONS ---
# ==========================================
def get_available_ports():
    """Scans and returns a list of available serial ports, filtering out system tty junk."""
    ports = serial.tools.list_ports.comports()
    valid_ports = []
    
    for port in ports:
        if "USB" in port.device or "ACM" in port.device or "COM" in port.device or "cu.usb" in port.device:
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
    # Increased window size to accommodate 2x font sizes
    screen = pygame.display.set_mode((1500, 1000))
    pygame.display.set_caption("Terminal de Contrôle du Bras Robotique")
    
    # Fonts are 2x larger
    font_large = pygame.font.SysFont(None, 108)
    font_small = pygame.font.SysFont(None, 72)

    # State Variables
    app_state = "MENU"
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
                        app_state = "MENU"
                        if ser:
                            ser.close()
                            ser = None
                        active_keys.clear()
                    else:
                        running = False
                        
                if app_state == "CONTROL" and ser is not None and ser.is_open:
                    if event.key in KEY_MAPPINGS and event.key not in active_keys:
                        active_keys.add(event.key)
                        mapping = KEY_MAPPINGS[event.key]
                        success = send_command(ser, f"J {mapping['driver']} {mapping['dir']}")
                        if not success:
                            ser.close()
                            ser = None 
                        
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
            
            title = font_large.render("Sélectionnez le Port Série ESP32", True, (255, 255, 255))
            screen.blit(title, (20, 20))

            # Draw Refresh Button (scaled up)
            refresh_rect = pygame.Rect(950, 20, 200, 60)
            pygame.draw.rect(screen, (100, 100, 150), refresh_rect, border_radius=5)
            screen.blit(font_small.render("Actualiser", True, (255,255,255)), (970, 32))
            
            if click and refresh_rect.collidepoint(mouse_pos):
                available_ports = get_available_ports()

            # Draw Port List
            y_offset = 120
            if not available_ports:
                screen.blit(font_small.render("Aucun port trouvé. Branchez l'ESP32 et cliquez sur Actualiser.", True, (200, 100, 100)), (20, y_offset))
            else:
                for port in available_ports:
                    port_rect = pygame.Rect(20, y_offset, 1100, 80)
                    color = (70, 70, 90) if port_rect.collidepoint(mouse_pos) else (50, 50, 70)
                    pygame.draw.rect(screen, color, port_rect, border_radius=5)
                    screen.blit(font_large.render(port, True, (200, 255, 200)), (40, y_offset + 15))
                    
                    if click and port_rect.collidepoint(mouse_pos):
                        selected_port = port
                        app_state = "CONTROL"
                        try:
                            ser = serial.Serial(selected_port, BAUD_RATE, timeout=0.1)
                            time.sleep(1) 
                        except Exception as e:
                            ser = None 
                    
                    y_offset += 100

            instruction = font_small.render("Appuyez sur ÉCHAP pour quitter.", True, (150, 150, 150))
            screen.blit(instruction, (20, 720))

        # ---------------------------------------------------------
        # STATE: CONTROL & AUTO-RECONNECT
        # ---------------------------------------------------------
        elif app_state == "CONTROL":
            screen.fill((30, 30, 30))
            
            if ser is not None and ser.is_open:
                try:
                    while ser.in_waiting > 0:
                        line = ser.readline().decode('utf-8', errors='ignore').strip()
                        if line:
                            print(f"[ESP32] {line}") # Kept English in console
                except (serial.SerialException, OSError):
                    print("CONNECTION LOST!") # Kept English in console
                    ser.close()
                    ser = None
                    active_keys.clear() 

            if ser is None or not ser.is_open:
                status_text = font_large.render(f"DÉCONNECTÉ de {selected_port}", True, (255, 100, 100))
                sub_text = font_small.render("Tentative de reconnexion auto... Veuillez brancher l'USB.", True, (200, 200, 200))
                
                if current_time - last_reconnect_time > 1.0:
                    last_reconnect_time = current_time
                    try:
                        ser = serial.Serial(selected_port, BAUD_RATE, timeout=0.1)
                        print(f"Reconnected to {selected_port}!")
                        time.sleep(1) 
                    except:
                        pass 
            else:
                status_text = font_large.render(f"CONNECTÉ : {selected_port}", True, (100, 255, 100))
                sub_text = font_small.render("Contrôles actifs. Mettez la fenêtre au premier plan.", True, (200, 200, 200))
                
            screen.blit(status_text, (20, 20))
            screen.blit(sub_text, (20, 90))
            
            # --- Draw Key Mapping Map (Left Side) ---
            map_title = font_small.render("Assignation des Touches :", True, (255, 255, 100))
            screen.blit(map_title, (20, 180))
            
            # Split data into (Keys, Description) so we can color them differently
            controls_data = [
                ("W / S", ": Épaule (Axe 1)"),
                ("HAUT / BAS", ": Coude (Axe 2)"),
                ("A / D", ": Base G/D (Axe 3)"),
                ("Q / E", ": Poignet (Axe 4)")
            ]
            
            map_y = 240
            for keys_text, desc_text in controls_data:
                # 1. Render Keys in Bright Yellow
                keys_surface = font_small.render(keys_text, True, (255, 255, 0))
                screen.blit(keys_surface, (20, map_y))
                
                # 2. Render Description in Gray (Aligned to an X offset of 280)
                desc_surface = font_small.render(desc_text, True, (180, 180, 180))
                screen.blit(desc_surface, (280, map_y))
                
                map_y += 50

            # --- Draw Active Keys (Right Side) ---
            active_title = font_small.render("Actuellement Actif :", True, (255, 255, 100))
            screen.blit(active_title, (700, 180))

            y_offset = 240
            if not active_keys:
                idle_text = font_small.render("En attente...", True, (100, 100, 100))
                screen.blit(idle_text, (700, y_offset))
            else:
                for key in active_keys:
                    action_text = font_large.render(f"{KEY_MAPPINGS[key]['name']}", True, (100, 200, 255))
                    screen.blit(action_text, (700, y_offset))
                    y_offset += 70

            instruction = font_small.render("Appuyez sur ÉCHAP pour vous déconnecter et retourner au Menu.", True, (150, 150, 150))
            screen.blit(instruction, (20, 720))

        # Update display
        pygame.display.flip()
        time.sleep(0.01) 

    # Cleanup before closing
    if ser is not None and ser.is_open:
        for i in range(1, 5):
            send_command(ser, f"S {i}")
        ser.close()
    pygame.quit()

if __name__ == '__main__':
    main()