import sys
import time
import serial
import serial.tools.list_ports

def scan_slcan(port='COM3', timeout_per_baud=3.0):
    print(f"=== MKS CANable v2 Pro Diagnostic on {port} ===")
    
    # 1. Check if COM port exists
    ports = [p.device for p in serial.tools.list_ports.comports()]
    print(f"Available serial ports: {ports}")
    if port not in ports:
        print(f"ERROR: {port} not found in available ports!")
        return

    # 2. Try opening serial port
    try:
        ser = serial.Serial(port, baudrate=115200, timeout=0.5)
    except Exception as e:
        print(f"ERROR: Cannot open {port}: {e}")
        return

    print(f"Successfully opened {port}.")

    def send_cmd(cmd):
        ser.write((cmd + '\r').encode('ascii'))
        time.sleep(0.05)
        resp = ser.read_all().decode('ascii', errors='ignore')
        return resp.strip()

    # Reset/Close channel first
    send_cmd('C')

    # Query device version
    hw_ver = send_cmd('V')
    sw_ver = send_cmd('v')
    serial_no = send_cmd('N')
    print(f"Hardware Version (V): {hw_ver or 'No response'}")
    print(f"Software Version (v): {sw_ver or 'No response'}")
    print(f"Serial Number    (N): {serial_no or 'No response'}")

    # Baudrate mapping in SLCAN
    # S3 = 100k, S4 = 125k, S5 = 250k, S6 = 500k, S7 = 800k, S8 = 1M
    baud_rates = [
        ('500 kbps (S6)', 'S6'),
        ('250 kbps (S5)', 'S5'),
        ('125 kbps (S4)', 'S4'),
        ('1 Mbps   (S8)', 'S8'),
    ]

    print("\n--- Testing CAN Listen-Only Mode across common baud rates ---")
    for name, cmd in baud_rates:
        print(f"\n[*] Testing baud rate: {name}...")
        send_cmd('C')  # Close
        ser.read_all()
        
        # Set baudrate
        res = send_cmd(cmd)
        
        # Open in Listen-Only mode ('L')
        # Note: In standard SLCAN, 'L' opens listen-only, 'O' opens normal.
        open_res = send_cmd('L')
        
        # Flush input buffer
        ser.reset_input_buffer()
        
        # Listen for frames
        start_time = time.time()
        frames_received = []
        raw_buffer = ""
        
        while time.time() - start_time < timeout_per_baud:
            if ser.in_waiting > 0:
                chunk = ser.read(ser.in_waiting).decode('ascii', errors='ignore')
                raw_buffer += chunk
                while '\r' in raw_buffer or '\n' in raw_buffer:
                    # Split lines
                    for delimiter in ['\r', '\n']:
                        if delimiter in raw_buffer:
                            line, _, raw_buffer = raw_buffer.partition(delimiter)
                            line = line.strip()
                            if line:
                                frames_received.append(line)
                                print(f"    [FRAME RECEIVED] {line}")
                                if len(frames_received) >= 10:
                                    break
                    if len(frames_received) >= 10:
                        break
            if len(frames_received) >= 10:
                break
            time.sleep(0.02)

        # Close channel
        send_cmd('C')

        if frames_received:
            print(f"--> SUCCESS! Received {len(frames_received)} frames at {name}!")
            ser.close()
            return name, frames_received
        else:
            print(f"    (No frames detected within {timeout_per_baud}s)")

    ser.close()
    print("\n=== Result: No CAN frames detected on COM3 across tested baud rates ===")
    return None, []

if __name__ == '__main__':
    scan_slcan('COM3')
