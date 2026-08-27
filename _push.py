import subprocess, sys, time
def run(args, timeout=60):
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
for attempt in range(1, 21):
    r = run(["git", "ls-remote", "https://github.com/good-boy4069/statlab-mcp.git", "HEAD"], timeout=45)
    if r.returncode != 0:
        time.sleep(8); continue
    p = run(["git", "push", "origin", "main"], timeout=300)
    if p.returncode == 0 or "Everything up-to-date" in (p.stdout or "") + (p.stderr or ""):
        print("PUSH-OK"); sys.exit(0)
    time.sleep(10)
print("PUSH-FAIL"); sys.exit(1)
