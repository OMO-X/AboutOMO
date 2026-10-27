import sys
import time
import json
import urllib.request
from collections import defaultdict, Counter

print("=== MEREKAM DATA CAN BUS SAAT SEIN KANAN AKTIF (6 detik) ===")
req = urllib.request.urlopen('http://127.0.0.1:8080/api/stream', timeout=10)
start_time = time.time()
frames = defaultdict(list)
total_frames = 0

while time.time() - start_time < 6.0:
    line = req.readline().decode('utf-8', errors='ignore').strip()
    if line.startswith('data:'):
        try:
            d = json.loads(line[5:])
            if d.get('type') == 'frame':
                cid = d['id']
                b = d['bytes']
                now = time.time()
                frames[cid].append((now, b))
                total_frames += 1
        except Exception:
            pass
req.close()

elapsed = time.time() - start_time
print(f"Selesai merekam! Total: {total_frames} frame dalam {elapsed:.2f}s.\n")

print("--- MENCARI BYTE YANG BERKEDIP / PULSING (Toggling Bit) ---")
pulsing_found = False

for cid in sorted(frames.keys()):
    sample_list = frames[cid]
    if not sample_list:
        continue
    
    # Check each byte 0 to 5 (ignore 6-7 rolling counter / CRC)
    for byte_idx in range(min(len(sample_list[0][1]), 6)):
        byte_values = [s[1][byte_idx] for s in sample_list]
        unique_vals = sorted(list(set(byte_values)))
        
        # If there are 2 or 3 distinct values alternating (like a flashing light: 0x00 and 0x01 or bit toggling):
        if len(unique_vals) in [2, 3]:
            # Count transitions
            transitions = 0
            for i in range(len(byte_values) - 1):
                if byte_values[i] != byte_values[i+1]:
                    transitions += 1
            
            # Flashing light at ~1.5 Hz over 6 seconds should have around 8-20 transitions!
            # High frequency rolling counter would have 100+ transitions!
            trans_rate = transitions / elapsed
            val_strs = [f"0x{v:02X} ({v:08b})" for v in unique_vals]
            
            print(f"Candidate: {cid} Byte {byte_idx}:")
            print(f"   Values: {val_strs}")
            print(f"   Total Transitions: {transitions} (~{trans_rate:.1f} trans/sec)")
            
            # Check bitwise difference
            if len(unique_vals) == 2:
                xor_diff = unique_vals[0] ^ unique_vals[1]
                print(f"   Bitwise XOR Diff: 0x{xor_diff:02X} (binary bit: {xor_diff:08b})")
            
            pulsing_found = True
            print("-" * 55)

if not pulsing_found:
    print("Tidak ditemukan byte toggling 2-3 nilai pada bytes 0-5. Menampilkan variasi semua ID:")
    for cid in sorted(frames.keys()):
        sample_list = frames[cid]
        for byte_idx in range(min(len(sample_list[0][1]), 6)):
            unique_vals = list(set(s[1][byte_idx] for s in sample_list))
            if len(unique_vals) > 1 and len(unique_vals) <= 5:
                print(f"  {cid} Byte {byte_idx}: {[hex(v) for v in unique_vals]}")
