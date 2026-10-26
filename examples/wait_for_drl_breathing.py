#!/usr/bin/env python3
"""
OMOWAY Wakeup & DRL Breathing Monitor
Waits for CAN bus to wake up (when phone approaches) and records the breathing animation sequence.
"""

import sys
import time
import json
import urllib.request
import csv

def monitor_wakeup(duration=30.0, output_csv="examples/drl_breathing_wake.csv"):
    print("=== MENUNGGU MOTOR BANGUN DARI SLEEP (DIDEKATI HP) ===")
    print("Status bus saat ini: SLEEP / 0 FPS.")
    print("Silakan dekati motor dengan HP Anda...")
    print("Skrip ini akan otomatis mendeteksi begitu bus bangun dan merekam animasi nafas!\n")

    csv_file = open(output_csv, 'w', encoding='utf-8', newline='')
    writer = csv.writer(csv_file)
    writer.writerow(['Timestamp', 'RelativeSec', 'CAN_ID', 'Hex', 'Byte0', 'Byte1', 'Byte2', 'Byte3', 'Byte4', 'Byte5', 'Byte6', 'Byte7'])

    req = urllib.request.urlopen('http://127.0.0.1:8080/api/stream', timeout=60)
    start_time = None
    last_print = None
    total_frames = 0
    wake_detected = False

    try:
        while True:
            line = req.readline().decode('utf-8', errors='ignore').strip()
            if line.startswith('data:'):
                try:
                    d = json.loads(line[5:])
                    if d.get('type') == 'frame':
                        if not wake_detected:
                            wake_detected = True
                            start_time = time.time()
                            print(f"\n⚡ [WAKEUP DETECTED!] Motor telah bangun pada {time.strftime('%H:%M:%S')}!")
                            print("Merekam animasi DRL Bernafas...\n")

                        t = time.time()
                        rel_t = t - start_time
                        cid = d['id']
                        b = d['bytes']
                        hex_str = ' '.join(f"{x:02X}" for x in b)

                        writer.writerow([f"{t:.6f}", f"{rel_t:.3f}", cid, hex_str] + [f"0x{x:02X}" for x in b])
                        total_frames += 1

                        if cid in ['0x233', '0x112', '0x304', '0x262', '0x003']:
                            log_msg = f"[{rel_t:6.3f}s] {cid:<6} -> {hex_str}"
                            if cid == '0x233':
                                duty_l = b[6] if len(b) > 6 else 0
                                duty_r = b[7] if len(b) > 7 else 0
                                log_msg += f" | DRL PWM: {duty_l} / {duty_r}"
                            if log_msg != last_print:
                                print(log_msg)
                                last_print = log_msg

                        if rel_t > duration:
                            break
                except Exception:
                    pass
    except KeyboardInterrupt:
        print("\nPerekaman dihentikan.")
    finally:
        req.close()
        csv_file.close()

    print(f"\n[OK] Selesai merekam! Total {total_frames} frame disimpan ke {output_csv}")

if __name__ == '__main__':
    monitor_wakeup()
