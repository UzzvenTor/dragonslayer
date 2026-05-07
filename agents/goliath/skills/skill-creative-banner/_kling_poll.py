"""Polling уже созданного job'а Kling и скачивание результата."""
import json, sys, time, urllib.request, urllib.error
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ENV = Path("I:/neuro/GENERAL CLAUDE CODE/Zerocoder/dragonslayer/goliath_daily/.env")
OR_KEY = next(l.split("=",1)[1].strip() for l in ENV.read_text(encoding="utf-8").splitlines() if l.startswith("OPENROUTER_API_KEY="))

JOB = sys.argv[1] if len(sys.argv) > 1 else "5yUTmkHDVVSCq9uUKp47"
OUT = Path("I:/OBSIDIAN/Obsidian/KURZEMNEK/Зерокодер Трафик/Raw/videos/H10_test_2026-05-07")
OUT.mkdir(parents=True, exist_ok=True)

def http(url, raw=False):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {OR_KEY}"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            c = r.read()
            return r.status, c if raw else json.loads(c.decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")

print(f"polling job {JOB}")
last = None
for i in range(120):
    s, j = http(f"https://openrouter.ai/api/v1/videos/{JOB}")
    if isinstance(j, dict):
        st = j.get("status")
        if st != last:
            print(f"  [{i*5:>4}s] {st}  keys={list(j.keys())}")
            last = st
        if st in ("completed", "succeeded", "success"):
            print(json.dumps(j, indent=2, ensure_ascii=False)[:1200])
            break
        if st in ("failed", "error", "cancelled"):
            print(f"  FAIL: {j}")
            sys.exit(1)
    else:
        print(f"  [{i*5:>4}s] http={s} body={j[:300]}")
    time.sleep(5)
else:
    print("[TIMEOUT]")
    sys.exit(1)

s, content = http(f"https://openrouter.ai/api/v1/videos/{JOB}/content?index=0", raw=True)
if s != 200:
    print(f"download failed: {s} {content[:300] if isinstance(content,(bytes,bytearray)) else content}")
    sys.exit(1)
out = OUT / f"openclaw_brief1__v1__{JOB}.mp4"
out.write_bytes(content)
print(f"\nsaved: {out}  ({len(content)/1024:.1f} KB)")
