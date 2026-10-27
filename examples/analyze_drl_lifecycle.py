import csv
from collections import defaultdict

csv_path = "examples/drl_breathing_wake.csv"
print(f"=== ANALISIS SIKLUS WAKEUP & DRL: {csv_path} ===")

with open(csv_path, 'r', encoding='utf-8') as f:
    r = csv.DictReader(f)
    rows = list(r)

print(f"Total frame terekam: {len(rows)}")
start_rel = float(rows[0]['RelativeSec'])
end_rel = float(rows[-1]['RelativeSec'])
print(f"Rentang waktu: {start_rel:.2f}s s/d {end_rel:.2f}s (Durasi: {end_rel-start_rel:.2f}s)\n")

# 1. Analisis 0x233 (DRL Animation & PWM)
f233 = [row for row in rows if row['CAN_ID'] == '0x233']
print(f"--- 0x233 (DRL Stream, total: {len(f233)} frame) ---")
unique_233 = []
last_payload = None

for row in f233:
    payload = row['Hex']
    t = float(row['RelativeSec'])
    if payload != last_payload:
        unique_233.append((t, payload, row['Byte6'], row['Byte7']))
        last_payload = payload

print(f"Total transisi payload 0x233: {len(unique_233)}")
print("Timeline perubahan 0x233:")
for t, payload, b6, b7 in unique_233[:35]: # show first 35 transitions
    duty_l = int(b6, 16) if b6.startswith('0x') else int(b6)
    duty_r = int(b7, 16) if b7.startswith('0x') else int(b7)
    print(f"  [{t:6.3f}s] {payload}  |  PWM L/R: {duty_l} / {duty_r}")

if len(unique_233) > 35:
    print(f"  ... dan {len(unique_233)-35} transisi lainnya")

# 2. Analisis 0x112 (Power / Ignition)
f112 = [row for row in rows if row['CAN_ID'] == '0x112']
print(f"\n--- 0x112 (Power/Mode Status, total: {len(f112)} frame) ---")
unique_112 = []
last_112 = None
for row in f112:
    # Look at byte 0-5 (ignore rolling counter in byte 6-7)
    state_sig = ' '.join([row[f'Byte{i}'] for i in range(6)])
    t = float(row['RelativeSec'])
    if state_sig != last_112:
        unique_112.append((t, state_sig, row['Hex']))
        last_112 = state_sig

for t, sig, full_hex in unique_112:
    print(f"  [{t:6.3f}s] Bytes 0-5: {sig}  (Full: {full_hex})")

# 3. Analisis 0x262 (Standar / Safety Switch)
f262 = [row for row in rows if row['CAN_ID'] == '0x262']
print(f"\n--- 0x262 (Safety / Standar Samping, total: {len(f262)} frame) ---")
unique_262 = []
last_262 = None
for row in f262:
    state_sig = ' '.join([row[f'Byte{i}'] for i in range(6)])
    t = float(row['RelativeSec'])
    if state_sig != last_262:
        unique_262.append((t, state_sig, row['Hex']))
        last_262 = state_sig

for t, sig, full_hex in unique_262:
    print(f"  [{t:6.3f}s] Bytes 0-5: {sig}  (Full: {full_hex})")

# 4. Kapan masing-masing CAN ID pertama kali muncul (Boot sequence)
first_seen = {}
for row in rows:
    cid = row['CAN_ID']
    t = float(row['RelativeSec'])
    if cid not in first_seen:
        first_seen[cid] = t

print("\n--- URUTAN BOOTING CAN ID (Boot Sequence) ---")
for cid, t in sorted(first_seen.items(), key=lambda x: x[1]):
    print(f"  [{t:6.3f}s] {cid}")
