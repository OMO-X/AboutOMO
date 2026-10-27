import urllib.request
import json

req = urllib.request.urlopen('http://127.0.0.1:8080/api/snapshot', timeout=5)
data = json.loads(req.read().decode())
frames = data['frames']

print("=== ALL ACTIVE FRAMES WITH POTENTIAL SOC / METRICS ===")
for cid, f in sorted(frames.items()):
    b = f['bytes']
    hex_str = f['hex']
    
    # Check any single byte around 58 (50-65)
    candidates_byte = [(idx, val) for idx, val in enumerate(b) if 50 <= val <= 65]
    # Check 16-bit around 580 (550-620)
    candidates_u16 = []
    for i in range(len(b) - 1):
        u16_be = (b[i] << 8) | b[i+1]
        u16_le = (b[i+1] << 8) | b[i]
        if 500 <= u16_be <= 650:
            candidates_u16.append((f"BE {i}-{i+1}", u16_be, u16_be/10.0))
        if 500 <= u16_le <= 650:
            candidates_u16.append((f"LE {i}-{i+1}", u16_le, u16_le/10.0))

    if candidates_byte or candidates_u16:
        print(f"{cid:<8} | Hex: {hex_str}")
        if candidates_byte:
            print(f"   -> 1-byte candidates (50-65): {candidates_byte}")
        if candidates_u16:
            print(f"   -> 16-bit candidates (50.0-65.0%): {candidates_u16}")
