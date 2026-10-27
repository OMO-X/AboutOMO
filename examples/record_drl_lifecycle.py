#!/usr/bin/env python3
"""
OMOWAY DRL Lifecycle Recorder
Captures all 4 phases of DRL:
1. Mati (Key OFF / DRL OFF)
2. Bernafas (Breathing / Welcome fade)
3. Bergerak (Running / Sweep on ignition)
4. Nyala Full (Solid DRL ON)
"""

import sys
import time
import json
import urllib.request
import csv

def record_drl_lifecycle(duration=25.0, output_csv="examples/drl_lifecycle.csv"):
    print(f"=== MEREKAM SIKLUS DRL OMOWAY ({duration} DETIK) ===")
    print("Merekam CAN ID 0x233, 0x304, 0x112, 0x224, 0x262...")
    print("Silakan ikuti instruksi:")
    print("  1. Matikan kontak (Mati)")
    print("  2. Dekati HP / Standby (Bernafas)")
    print("  3. Nyalakan kontak (Bergerak -> Nyala Full)\n")

    csv_file = open(output_csv, 'w', encoding='utf-8', newline='')
    writer = csv.writer(csv_file)
    writer.writerow(['Timestamp', 'RelativeSec', 'CAN_ID', 'Hex', 'Byte0', 'Byte1', 'Byte2', 'Byte3', 'Byte4', 'Byte5', 'Byte6', 'Byte7'])

    req = urllib.request.urlopen('http://127.0.0.1:8080/api/stream', timeout=30)
    start_time = time.time()
    last_print_233 = None
    last_print_112 = None
    total_events = 0

    try:
        while time.time() - start_time < duration:
            line = req.readline().decode('utf-8', errors='ignore').strip()
            if line.startswith('data:'):
                try:
                    d = json.loads(line[5:])
                    if d.get('type') == 'frame':
                        cid = d['id']
                        if cid in ['0x233', '0x304', '0x112', '0x224', '0x262']:
                            b = d['bytes']
                            t = time.time()
                            rel_t = t - start_time
                            hex_str = ' '.join(f"{x:02X}" for x in b)
                            
                            writer.writerow([f"{t:.6f}", f"{rel_t:.3f}", cid, hex_str] + [f"0x{x:02X}" for x in b])
                            total_events += 1

                            if cid == '0x233' and hex_str != last_print_233:
                                duty_l = b[6] if len(b) > 6 else 0
                                duty_r = b[7] if len(b) > 7 else 0
                                print(f"[{rel_t:6.2f}s] 0x233 (DRL) -> {hex_str} | Duty: {duty_l}/{duty_r}")
                                last_print_233 = hex_str
                            
                            elif cid == '0x112' and hex_str != last_print_112:
                                print(f"[{rel_t:6.2f}s] 0x112 (Pwr/Mode) -> {hex_str}")
                                last_print_112 = hex_str
                except Exception:
                    pass
    except KeyboardInterrupt:
        print("\nPerekaman dihentikan pengguna.")
    finally:
        req.close()
        csv_file.close()

    elapsed = time.time() - start_time
    print(f"\n[OK] Selesai merekam! Total {total_events} event disimpan ke {output_csv}")

if __name__ == '__main__':
    dur = float(sys.argv[1]) if len(sys.argv) > 1 else 25.0
    record_drl_lifecycle(duration=dur)
