#!/usr/bin/env python3
import subprocess, sys, time, os
def start(name):
    return subprocess.Popen([sys.executable, name], cwd=os.path.dirname(os.path.abspath(__file__)),
                             creationflags=0x00000008 if sys.platform == "win32" else 0)
procs = {"seller.py": start("seller.py"), "buyer.py": start("buyer.py")}
print("[自治M2M] 卖方+买方已启动，收入记到 ledger.json。Ctrl+C 停止。")
try:
    while True:
        for k, p in procs.items():
            if p.poll() is not None:
                print("[自治M2M] " + k + " 掉线，重启"); procs[k] = start(k)
        time.sleep(5)
except KeyboardInterrupt:
    for p in procs.values(): p.terminate()
    print("已停止。看 ledger.json 赚了多少。")
