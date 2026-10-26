import urllib.request
import json

req = urllib.request.urlopen('http://127.0.0.1:8080/api/snapshot', timeout=5)
frames = json.loads(req.read().decode())['frames']

cids = ['0x262', '0x233', '0x112', '0x224', '0x104', '0x216', '0x304', '0x306']
print("=== SNAPSHOT KONDISI SEIN OFF ===")
for c in cids:
    if c in frames:
        f = frames[c]
        b = f['bytes']
        b4_str = f" | Byte 4: 0x{b[4]:02X} ({b[4]:08b})" if len(b) > 4 else ""
        print(f"{c:<6} | Hex: {f['hex']}{b4_str}")
