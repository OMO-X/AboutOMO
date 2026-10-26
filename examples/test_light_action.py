#!/usr/bin/env python3
"""
OMOWAY Light & Switch Action Differential Tester
Connects to local dashboard SSE stream (/api/stream) and records frames
to isolate High Beam (Dim) and Turn Signals (Sein).
"""

import sys
import time
import json
import urllib.request
from collections import defaultdict, Counter

def capture_stream(duration=5.0, label="Action"):
    print(f"[*] Merekam data CAN bus selama {duration} detik ({label})...")
    frames = defaultdict(list)
    start_time = time.time()
    total = 0

    try:
        req = urllib.request.urlopen('http://127.0.0.1:8080/api/stream', timeout=10)
        while time.time() - start_time < duration:
            line = req.readline().decode('utf-8', errors='ignore').strip()
            if line.startswith('data:'):
                payload_str = line[5:].strip()
                try:
                    data = json.loads(payload_str)
                    if data.get('type') == 'frame':
                        cid = data['id']
                        b = data['bytes']
                        frames[cid].append((time.time(), b))
                        total += 1
                except Exception:
                    pass
        req.close()
    except Exception as e:
        print(f"Stream error: {e}")

    elapsed = time.time() - start_time
    print(f"[*] Selesai merekam {label}: {total} frame diterima dalam {elapsed:.2f}s.\n")
    return frames

def analyze_diff(base_frames, act_frames, action_name="Test"):
    print(f"=== ANALISIS DIFERENSIAL: {action_name} ===")
    all_cids = sorted(set(base_frames.keys()).intersection(set(act_frames.keys())))
    findings = []

    for cid in all_cids:
        b_samples = [f[1] for f in base_frames[cid]]
        a_samples = [f[1] for f in act_frames[cid]]

        if not b_samples or not a_samples:
            continue

        # Get modal/most common byte values
        dlc = len(b_samples[0])
        b_common = [Counter([s[i] for s in b_samples]).most_common(1)[0][0] for i in range(dlc)]
        a_common = [Counter([s[i] for s in a_samples]).most_common(1)[0][0] for i in range(dlc)]

        byte_diffs = []
        for i in range(min(dlc, 6)): # inspect bytes 0 to 5 (ignore rolling counter/crc in 6-7)
            if b_common[i] != a_common[i]:
                xor_diff = b_common[i] ^ a_common[i]
                byte_diffs.append({
                    'byte': i,
                    'base': f"0x{b_common[i]:02X}",
                    'act': f"0x{a_common[i]:02X}",
                    'xor': f"0x{xor_diff:02X}",
                    'bin_diff': f"{xor_diff:08b}"
                })

        # Also check if any byte was pulsing/oscillating in action (e.g. Turn signal flashing!)
        pulsing_bytes = []
        for i in range(min(dlc, 6)):
            act_unique = len(set(s[i] for s in a_samples))
            base_unique = len(set(s[i] for s in b_samples))
            if act_unique > 1 and base_unique == 1:
                vals = list(set(s[i] for s in a_samples))
                pulsing_bytes.append({
                    'byte': i,
                    'vals': [f"0x{v:02X}" for v in vals]
                })

        if byte_diffs or pulsing_bytes:
            findings.append({
                'cid': cid,
                'diffs': byte_diffs,
                'pulsing': pulsing_bytes,
                'b_hex': ' '.join(f"{b:02X}" for b in b_common),
                'a_hex': ' '.join(f"{b:02X}" for b in a_common),
            })

    if not findings:
        print("[!] Tidak ada perubahan byte statis terdeteksi di bytes 0-5.")
        print("    (Memeriksa perubahan byte 6-7 counter/CRC atau sub-nibble)...")
    else:
        for f in findings:
            print(f"CAN ID: {f['cid']}")
            print(f"  Baseline Payload: {f['b_hex']}")
            print(f"  Action Payload  : {f['a_hex']}")
            for d in f['diffs']:
                print(f"  --> Byte {d['byte']}: {d['base']} -> {d['act']} (XOR: {d['xor']}, Bits: {d['bin_diff']})")
            for p in f['pulsing']:
                print(f"  ~~> Byte {p['byte']} BERKEDIP/PULSING: {p['vals']}")
            print("-" * 60)

    return findings

if __name__ == '__main__':
    name = sys.argv[1] if len(sys.argv) > 1 else "Light Switch Test"
    print("Tahap 1: Mengambil baseline kondisi lampu saat ini (2 detik)...")
    base = capture_stream(duration=2.5, label="Baseline")
    
    print("Persiapan! Dalam 3 detik, lakukan aksi saklar...")
    for s in [3, 2, 1]:
        print(f"  {s}...")
        time.sleep(1.0)
    print(">>> LAKUKAN AKSI SEKARANG! (Tahan selama 5 detik) <<<")

    act = capture_stream(duration=5.0, label=name)
    analyze_diff(base, act, action_name=name)
