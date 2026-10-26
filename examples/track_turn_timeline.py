import urllib.request
import json
import time

print("Tracking 0x262 Byte 4 and 0x233 transitions over 4 seconds...")
req = urllib.request.urlopen('http://127.0.0.1:8080/api/stream', timeout=5)
start = time.time()
timeline = []

last_262 = None
last_233 = None

while time.time() - start < 4:
    line = req.readline().decode('utf-8', errors='ignore').strip()
    if line.startswith('data:'):
        try:
            d = json.loads(line[5:])
            if d.get('type') == 'frame':
                cid = d['id']
                b = d['bytes']
                t = time.time() - start
                if cid == '0x262':
                    val = b[4]
                    if val != last_262:
                        print(f"[{t:6.3f}s] 0x262:B4 changed to 0x{val:02X} ({val:08b})")
                        last_262 = val
                elif cid == '0x233':
                    val = (b[3], b[4], b[5])
                    if val != last_233:
                        print(f"[{t:6.3f}s] 0x233:B3-5 changed to {['0x%02X'%x for x in val]}")
                        last_233 = val
        except Exception:
            pass
req.close()
