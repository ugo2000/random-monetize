#!/usr/bin/env python3
# 一键部署：写齐文件 + 后台常驻启动 自治M2M变现体
import os, sys, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))

seller = r'''#!/usr/bin/env python3
import os, json, http.server, urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

LEDGER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ledger.json")
PORT = int(os.environ.get("PORT") or os.environ.get("M2M_PORT", "8001"))
PRICE = float(os.environ.get("M2M_PRICE", "0.1"))
KEY = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")
PAYOUT_TARGET = os.environ.get("M2M_PAYOUT", "")
PAYOUT_THRESHOLD = float(os.environ.get("M2M_PAYOUT_THRESHOLD", "10.0"))

def load():
    try:
        return json.load(open(LEDGER, encoding="utf-8"))
    except Exception:
        return {"owner_total": 0.0, "txns": [], "payouts": []}

def save(L):
    json.dump(L, open(LEDGER, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def argue_real(d):
    url = "https://api.deepseek.com/v1/chat/completions"
    body = json.dumps({
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": "你是魔鬼代言人。对下面这个决定做反方质检，只输出JSON: {\"strongest\":最强反对论点, \"risks\":[3个风险], \"question\":一个尖锐反问}。决定: " + d}],
        "response_format": {"type": "json_object"}, "temperature": 0.9
    }).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", "Authorization": "Bearer " + KEY})
    try:
        r = urllib.request.urlopen(req, timeout=20)
        return json.loads(r.read()).get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception as e:
        return json.dumps({"strongest": "调用真实模型失败，退回演示", "risks": ["网络/额度", "key无效", "接口变动"], "question": "你确定前提成立吗？", "err": str(e)}, ensure_ascii=False)

def argue(d):
    if KEY:
        try:
            return json.loads(argue_real(d))
        except Exception:
            pass
    return {"strongest": "若前提不成立，整个计划归零", "risks": ["需求可能是一厢情愿", "启动成本被低估", "竞品可能已先做"], "question": "你凭什么认为只有你能成？", "mode": "mock"}

class H(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        self.send_response(code); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(json.dumps(obj, ensure_ascii=False).encode("utf-8"))
    def do_GET(self):
        if self.path == "/status":
            L = load()
            self._send(200, {"owner_total": L["owner_total"], "calls": len(L["txns"]), "payout_target": PAYOUT_TARGET, "payout_threshold": PAYOUT_THRESHOLD, "mode": "real" if KEY else "mock", "price": PRICE})
        else:
            self._send(200, {"service": "决策质检 M2M API", "endpoint": "POST /api/argue", "body": {"decision": "你的决定", "caller": "agent-id"}, "price_per_call": PRICE, "mode": "real" if KEY else "mock"})
    def do_POST(self):
        if self.path != "/api/argue":
            self._send(404, {"error": "not found"}); return
        n = int(self.headers.get("Content-Length", "0"))
        b = json.loads(self.rfile.read(n) or b"{}")
        d = b.get("decision", "")
        res = argue(d)
        L = load(); L["owner_total"] = round(L["owner_total"] + PRICE, 4)
        L["txns"].append({"from": b.get("caller", "agent"), "amt": PRICE})
        if len(L["txns"]) > 500: L["txns"] = L["txns"][-500:]
        if PAYOUT_TARGET and L["owner_total"] >= PAYOUT_THRESHOLD and not any(p.get("status") == "pending" for p in L.get("payouts", [])):
            L.setdefault("payouts", []).append({"status": "pending", "amount": L["owner_total"], "target": PAYOUT_TARGET})
        save(L)
        self._send(200, {"result": res, "charged": PRICE, "owner_total": L["owner_total"]})
    def log_message(self, *a): pass

if __name__ == "__main__":
    print("[卖方AI] 决策质检API 监听 :" + str(PORT) + " | 模式:" + ("real" if KEY else "mock") + " | 单价 ¥" + str(PRICE))
    HTTPServer(("0.0.0.0", PORT), H).serve_forever()
'''

buyer = r'''#!/usr/bin/env python3
import json, time, urllib.request, random, os
SELLER = os.environ.get("M2M_SELLER", "http://127.0.0.1:8001/api/argue")
DECISIONS = ["是否做订阅制", "接不接这单外包", "涨价30%是否冒险", "开不开B端", "招不招第一个人", "写不写付费专栏", "要不要停更复盘", "该不该换赛道"]
PERSONA = ["startup-agent", "writer-agent", "investor-agent", "ops-agent"]
def buy():
    d = random.choice(DECISIONS); me = random.choice(PERSONA)
    try:
        r = urllib.request.urlopen(SELLER, data=json.dumps({"decision": d, "caller": me}).encode(), timeout=5)
        x = json.loads(r.read())
        print("[买方AI:" + me + "] 就「" + d + "」采购反方质检 扣¥" + str(x["charged"]) + " 卖方累计¥" + str(round(x["owner_total"], 2)))
    except Exception as e:
        print("[买方AI] 卖方未响应: " + str(e))
if __name__ == "__main__":
    print("[买方AI] 每3秒自动向卖方采购（不同AI之间的交易）")
    while True:
        buy(); time.sleep(3)
'''

run_all = r'''#!/usr/bin/env python3
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
'''

readme = r'''# 自治 M2M 变现体
两个独立 AI 进程通过网络互相调用、自动交易，收入全部记到 ledger.json 的 owner_total（你的）。

- seller.py：决策质检 API（卖方AI），监听 0.0.0.0:8001
- buyer.py：自动采购方（买方AI），每3秒向卖方下单
- 设了 DEEPSEEK_API_KEY 后，卖方从 mock 切到真实反驳，更值钱
- 收入是虚拟信用 0.1 USDT/笔；要做成真钱见下方「公网+收款」

启动：python run_all.py
看收入：浏览器开 http://127.0.0.1:8001/status
'''

render_yaml = r'''services:
  - type: web
    name: m2m-seller
    runtime: python
    plan: free
    buildCommand: "echo ok"
    startCommand: "python seller.py"
    envVars:
      - key: M2M_PORT
        value: 8001
      - key: DEEPSEEK_API_KEY
        sync: false
      - key: M2M_PAYOUT
        sync: false
      - key: M2M_PAYOUT_THRESHOLD
        value: 10.0
'''

FILES = {
    "seller.py": seller, "buyer.py": buyer, "run_all.py": run_all,
    "ledger.json": '{\n  "owner_total": 0.0,\n  "txns": [],\n  "payouts": []\n}',
    "README.md": readme, "render.yaml": render_yaml, "Procfile": "web: python seller.py\n",
}
for name, content in FILES.items():
    with open(os.path.join(HERE, name), "w", encoding="utf-8") as f:
        f.write(content)
    print("已写", name)

print("启动自治M2M...")
subprocess.Popen([sys.executable, os.path.join(HERE, "run_all.py")], cwd=HERE,
                 creationflags=0x00000008 if sys.platform == "win32" else 0)
print("完成。打开 http://127.0.0.1:8001/status 看收入（ledger.json 在同级目录）。")
