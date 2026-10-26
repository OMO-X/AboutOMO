import urllib.request
import json
import time

print("Polling /api/snapshot for live lighting frames...")
for i in range(10):
    try:
        req = urllib.request.urlopen('http://127.0.0.1:8080/api/snapshot', timeout=2)
        data = json.loads(req.read().decode('utf-8'))
        frames = data.get('frames', {})
        d233 = frames.get('0x233', {}).get('hex', 'N/A')
        d262 = frames.get('0x262', {}).get('hex', 'N/A')
        d112 = frames.get('0x112', {}).get('hex', 'N/A')
        d304 = frames.get('0x304', {}).get('hex', 'N/A')
        d234 = frames.get('0x234', {}).get('hex', 'N/A')
        t233 = frames.get('0x233', {}).get('time', 0)
        now = time.time()
        age233 = now - t233 if t233 else 999
        print(f"[{i:02d}] 0x233: {d233} (age: {age233:.2f}s) | 0x262: {d262} | 0x112: {d112} | 0x304: {d304}")
    except Exception as e:
        print(f"Error: {e}")
    time.sleep(0.5)
