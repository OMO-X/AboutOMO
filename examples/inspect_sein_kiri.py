import urllib.request
import json

req = urllib.request.urlopen('http://127.0.0.1:8080/api/snapshot', timeout=5)
frames = json.loads(req.read().decode())['frames']
for cid in ['0x262', '0x224', '0x112', '0x304', '0x233', '0x216', '0x234', '0x306']:
    f = frames.get(cid, {})
    print(f"{cid:<6} | Hex: {f.get('hex')}")
