#!/usr/bin/env python3
"""
OMOWAY CAN Bus Telemetry Web Dashboard Server
Serves static dashboard files and streams live CAN frames from COM3 via Server-Sent Events (SSE).
Falls back cleanly to replaying captured data if COM3 is busy or disconnected.
"""

import os
import sys
import time
import json
import csv
import threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import serial
import serial.tools.list_ports

PORT = 8080
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

# Global broadcast queue & clients
clients = []
clients_lock = threading.Lock()
bus_stats = {
    'fps': 0,
    'total_frames': 0,
    'com3_connected': False
}
latest_frames = {}
latest_frames_lock = threading.Lock()

def parse_slcan_line(line: str):
    line = line.strip()
    if not line:
        return None
    
    if line.startswith('t'):
        cid = f"0x{int(line[1:4], 16):03X}"
        dlc = int(line[4:5], 16)
        data_hex = line[5:5 + dlc * 2]
    elif line.startswith('T'):
        cid = f"0x{int(line[1:9], 16):08X}"
        dlc = int(line[9:10], 16)
        data_hex = line[10:10 + dlc * 2]
    else:
        return None

    try:
        data_bytes = list(bytes.fromhex(data_hex))
        return {
            'type': 'frame',
            'id': cid,
            'bytes': data_bytes,
            'dlc': dlc
        }
    except Exception:
        return None

def broadcast_event(event_dict):
    if event_dict.get('type') == 'frame':
        with latest_frames_lock:
            latest_frames[event_dict['id']] = {
                'bytes': event_dict['bytes'],
                'hex': ' '.join(f"{b:02X}" for b in event_dict['bytes']),
                'dlc': event_dict.get('dlc', len(event_dict['bytes'])),
                'time': time.time()
            }

    payload = f"data: {json.dumps(event_dict)}\n\n".encode('utf-8')
    with clients_lock:
        to_remove = []
        for client_wfile in clients:
            try:
                client_wfile.write(payload)
                client_wfile.flush()
            except Exception:
                to_remove.append(client_wfile)
        for dead in to_remove:
            if dead in clients:
                clients.remove(dead)

def can_worker():
    """Reads from COM3 or replays captured CSV if COM3 cannot be opened."""
    port = 'COM3'
    baud_cmd = 'S6' # 500k

    while True:
        ser = None
        try:
            available_ports = [p.device for p in serial.tools.list_ports.comports()]
            if port in available_ports:
                print(f"[CAN Worker] Opening {port} at 500kbps...")
                ser = serial.Serial(port, baudrate=115200, timeout=0.1)
                ser.write(b'C\r')
                time.sleep(0.05)
                ser.write((baud_cmd + '\r').encode('ascii'))
                time.sleep(0.05)
                ser.write(b'O\r')
                time.sleep(0.05)
                ser.reset_input_buffer()
                bus_stats['com3_connected'] = True
                print(f"[CAN Worker] Connected to {port}! Streaming live CAN frames...")
        except Exception as e:
            print(f"[CAN Worker] Could not open {port}: {e}")
            ser = None
            bus_stats['com3_connected'] = False

        if ser:
            raw_buf = ""
            last_sec = time.time()
            frames_in_sec = 0
            try:
                while True:
                    in_waiting = ser.in_waiting
                    if in_waiting > 0:
                        chunk = ser.read(in_waiting).decode('ascii', errors='ignore')
                        raw_buf += chunk
                        while '\r' in raw_buf:
                            line, _, raw_buf = raw_buf.partition('\r')
                            frame = parse_slcan_line(line)
                            if frame:
                                bus_stats['total_frames'] += 1
                                frames_in_sec += 1
                                broadcast_event(frame)

                    now = time.time()
                    if now - last_sec >= 1.0:
                        bus_stats['fps'] = frames_in_sec
                        frames_in_sec = 0
                        last_sec = now
                        broadcast_event({
                            'type': 'stats',
                            'fps': bus_stats['fps'],
                            'totalFrames': bus_stats['total_frames']
                        })
                    time.sleep(0.002)
            except Exception as e:
                print(f"[CAN Worker] Serial read error: {e}")
                try:
                    ser.write(b'C\r')
                    ser.close()
                except Exception:
                    pass
                bus_stats['com3_connected'] = False

        # Replay fallback mode
        print("[CAN Worker] Running replay from captured OMOWAY datasets...")
        replay_files = [
            os.path.join(DIRECTORY, '..', 'examples', 'can_capture.csv'),
            os.path.join(DIRECTORY, '..', 'examples', 'can_brake_pressed.csv')
        ]
        
        # Load CSV rows
        all_frames = []
        for rf in replay_files:
            if os.path.exists(rf):
                with open(rf, 'r', encoding='utf-8') as f:
                    r = csv.DictReader(f)
                    for row in r:
                        bytes_list = []
                        for i in range(8):
                            val = row.get(f'Byte{i}', '')
                            if val.startswith('0x'):
                                bytes_list.append(int(val, 16))
                            elif val:
                                bytes_list.append(int(val))
                        all_frames.append({
                            'type': 'frame',
                            'id': row['CAN_ID'],
                            'bytes': bytes_list,
                            'dlc': int(row['DLC'])
                        })

        if not all_frames:
            time.sleep(1)
            continue

        # Replay loop
        frame_idx = 0
        last_sec = time.time()
        frames_in_sec = 0
        while not bus_stats['com3_connected']:
            # Check every 200 frames if COM3 has become available
            if frame_idx % 200 == 0:
                available_ports = [p.device for p in serial.tools.list_ports.comports()]
                if port in available_ports:
                    break # try connecting

            f = all_frames[frame_idx % len(all_frames)]
            frame_idx += 1
            bus_stats['total_frames'] += 1
            frames_in_sec += 1
            broadcast_event(f)

            now = time.time()
            if now - last_sec >= 1.0:
                bus_stats['fps'] = frames_in_sec
                frames_in_sec = 0
                last_sec = now
                broadcast_event({
                    'type': 'stats',
                    'fps': bus_stats['fps'],
                    'totalFrames': bus_stats['total_frames']
                })
            time.sleep(0.001)

class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

    def do_GET(self):
        if self.path == '/api/snapshot':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            with latest_frames_lock:
                data = {
                    'stats': bus_stats,
                    'frames': latest_frames
                }
            self.wfile.write(json.dumps(data).encode('utf-8'))
            return
        elif self.path == '/api/stream':
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'keep-alive')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            with clients_lock:
                clients.append(self.wfile)

            try:
                # Keep connection alive
                while True:
                    time.sleep(1)
            except Exception:
                pass
            finally:
                with clients_lock:
                    if self.wfile in clients:
                        clients.remove(self.wfile)
        else:
            super().do_GET()

def main():
    # Start CAN background worker
    worker_thread = threading.Thread(target=can_worker, daemon=True)
    worker_thread.start()

    server = ThreadingHTTPServer(('127.0.0.1', PORT), DashboardHandler)
    print(f"\n=======================================================")
    print(f"[OK] OMOWAY CAN Bus Cockpit Dashboard is RUNNING!")
    print(f"--> Local URL: http://127.0.0.1:{PORT}")
    print(f"=======================================================\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard server...")
        server.server_close()

if __name__ == '__main__':
    main()
