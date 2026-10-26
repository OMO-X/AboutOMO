import urllib.request
import json

req = urllib.request.urlopen('http://127.0.0.1:8080/api/snapshot', timeout=5)
data = json.loads(req.read().decode())['frames']

lighting_cids = ['0x233', '0x304', '0x234', '0x112', '0x114', '0x216', '0x262', '0x306']
print("=== CURRENT PAYLOADS FOR CANDIDATE LIGHTING / BODY FRAMES ===")
for cid in lighting_cids:
    if cid in data:
        f = data[cid]
        b = f['bytes']
        bin_strs = [f"{x:08b}" for x in b]
        print(f"{cid:<6} | Hex: {f['hex']}")
        print(f"       | Dec: {b}")
        print(f"       | Bin: {' '.join(bin_strs)}")
