#!/usr/bin/env python3
"""
OMOWAY Live Lighting & Switch Signal Monitor
Watches 0x233, 0x304, 0x112, 0x234, 0x306, 0x262 and alerts on any bit change.
"""

import sys
import time
import urllib.request
import json

TARGET_CIDS = ['0x233', '0x304', '0x234', '0x112', '0x114', '0x216', '0x262', '0x306']

def monitor():
    print("=== OMOWAY Live Lighting & Switch Monitor ===")
    print(f"Monitoring CAN IDs: {', '.join(TARGET_CIDS)}")
    print("Silakan lakukan aksi pada motor (misal: tombol Dim, Sein Kiri/Kanan, Saklar Lampu, dll)...")
    print("Tekan Ctrl+C untuk berhenti.\n")

    last_states = {}

    while True:
        try:
            req = urllib.request.urlopen('http://127.0.0.1:8080/api/snapshot', timeout=2)
            data = json.loads(req.read().decode())['frames']
            now_str = time.strftime('%H:%M:%S')

            for cid in TARGET_CIDS:
                if cid not in data:
                    continue
                f = data[cid]
                b = f['bytes']
                hex_str = f['hex']

                if cid not in last_states:
                    last_states[cid] = b
                    print(f"[{now_str}] INIT  {cid:<6} : {hex_str}")
                else:
                    prev_b = last_states[cid]
                    # Check if non-counter bytes changed (ignore rolling counter in byte 6 high nibble & byte 7 CRC)
                    diffs = []
                    for i in range(len(b)):
                        if b[i] != prev_b[i]:
                            # If byte 6 or 7, check if other bytes also changed
                            if i == 6 and (b[i] ^ prev_b[i]) & 0xF0 and not any(b[j] != prev_b[j] for j in range(6)):
                                continue # rolling counter
                            if i == 7 and not any(b[j] != prev_b[j] for j in range(6)):
                                continue # CRC
                            diffs.append(f"Byte {i}: 0x{prev_b[i]:02X}->0x{b[i]:02X} (XOR: 0x{prev_b[i]^b[i]:02X})")

                    if diffs:
                        last_states[cid] = b
                        print(f"\n⚡ [{now_str}] EVENT DETECTED on {cid}!")
                        print(f"   Payload: {hex_str}")
                        for d in diffs:
                            print(f"   └─ {d}")

            time.sleep(0.05) # 20 Hz polling
        except KeyboardInterrupt:
            print("\nMonitoring stopped.")
            break
        except Exception as e:
            time.sleep(0.5)

if __name__ == '__main__':
    monitor()
