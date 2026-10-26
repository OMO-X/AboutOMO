import urllib.request
import json
import time

print("Listening to SSE stream for 4 seconds...")
req = urllib.request.urlopen('http://127.0.0.1:8080/api/stream', timeout=5)
start = time.time()
samples = {}

while time.time() - start < 4:
    line = req.readline().decode('utf-8', errors='ignore').strip()
    if line.startswith('data:'):
        try:
            d = json.loads(line[5:])
            if d.get('type') == 'frame':
                cid = d['id']
                if cid in ['0x233', '0x304', '0x112', '0x262', '0x234', '0x104', '0x216']:
                    hex_str = ' '.join(f"{x:02X}" for x in d['bytes'])
                    if cid not in samples:
                        samples[cid] = set()
                    samples[cid].add(hex_str)
        except Exception:
            pass
req.close()

for cid, payloads in sorted(samples.items()):
    print(f"\n{cid} (total unique payloads: {len(payloads)}):")
    for p in sorted(payloads):
        print(f"   {p}")
