import sys
import time
import json
import urllib.request
import csv

print("=== MEREKAM DRL BERNAFAS SECARA REAL-TIME (7 DETIK) ===")
output_csv = "examples/drl_breathing_capture.csv"
csv_file = open(output_csv, 'w', encoding='utf-8', newline='')
writer = csv.writer(csv_file)
writer.writerow(['Timestamp', 'RelativeSec', 'CAN_ID', 'Hex', 'Byte0', 'Byte1', 'Byte2', 'Byte3', 'Byte4', 'Byte5', 'Byte6', 'Byte7'])

req = urllib.request.urlopen('http://127.0.0.1:8080/api/stream', timeout=15)
start_time = time.time()
samples_233 = []
total_frames = 0

while time.time() - start_time < 7.0:
    line = req.readline().decode('utf-8', errors='ignore').strip()
    if line.startswith('data:'):
        try:
            d = json.loads(line[5:])
            if d.get('type') == 'frame':
                cid = d['id']
                b = d['bytes']
                t = time.time()
                rel_t = t - start_time
                hex_str = ' '.join(f"{x:02X}" for x in b)
                writer.writerow([f"{t:.6f}", f"{rel_t:.3f}", cid, hex_str] + [f"0x{x:02X}" for x in b])
                total_frames += 1

                if cid == '0x233':
                    samples_233.append((rel_t, b, hex_str))
        except Exception:
            pass
req.close()
csv_file.close()

elapsed = time.time() - start_time
print(f"Selesai merekam! Total: {total_frames} frame dalam {elapsed:.2f}s ({len(samples_233)} frame 0x233).")

print("\n--- ANALISIS FRAME 0x233 SAAT DRL BERNAFAS ---")
if samples_233:
    unique_payloads = []
    last_hex = None
    for t, b, hx in samples_233:
        if hx != last_hex:
            duty_l = b[6] if len(b) > 6 else 0
            duty_r = b[7] if len(b) > 7 else 0
            unique_payloads.append((t, hx, duty_l, duty_r, b))
            last_hex = hx
    
    print(f"Total payload unik pada 0x233: {len(unique_payloads)}")
    print("Timeline perubahan 0x233 saat bernafas:")
    for t, hx, dl, dr, b in unique_payloads[:30]:
        print(f"  [{t:5.3f}s] {hx}  |  PWM Duty: {dl} / {dr}")
else:
    print("Tidak ada frame 0x233 terdeteksi saat bernafas.")

# Cek frame lain yang berubah selama bernafas
print("\n--- FRAME LAIN YANG AKTIF SELAMA BERNAFAS ---")
with open(output_csv, 'r', encoding='utf-8') as f:
    r = list(csv.DictReader(f))
    active_cids = sorted(list(set(row['CAN_ID'] for row in r)))
    print(f"Active CAN IDs ({len(active_cids)}): {', '.join(active_cids)}")
