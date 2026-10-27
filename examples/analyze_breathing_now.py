import urllib.request
import json
import time

print("Recording 10 seconds of CAN snapshot history...")
history = []
start = time.time()
while time.time() - start < 6.0:
    try:
        req = urllib.request.urlopen('http://127.0.0.1:8080/api/snapshot', timeout=1)
        data = json.loads(req.read().decode('utf-8'))
        frames = data.get('frames', {})
        t = time.time() - start
        snap = {'t': round(t, 3)}
        for cid in ['0x233', '0x304', '0x112', '0x262', '0x226', '0x236', '0x104', '0x142', '0x202', '0x306']:
            if cid in frames:
                snap[cid] = frames[cid].get('hex')
        history.append(snap)
    except Exception as e:
        pass
    time.sleep(0.05)

print(f"Captured {len(history)} snapshots.")

# Analyze unique values and transitions per ID
for cid in ['0x233', '0x304', '0x112', '0x262', '0x226', '0x236', '0x306']:
    vals = [h[cid] for h in history if cid in h]
    unique_vals = list(dict.fromkeys(vals))
    print(f"\n=== CAN ID {cid} (Total readings: {len(vals)}, Unique: {len(unique_vals)}) ===")
    for u in unique_vals[:10]:
        print("  ", u)

# Look at 0x233 transitions specifically over time
print("\n=== Timeline of 0x233 ===")
last_val = None
for h in history:
    v = h.get('0x233')
    if v != last_val:
        print(f"t={h['t']:.2f}s -> {v}")
        last_val = v
