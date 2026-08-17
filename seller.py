#!/usr/bin/env python3
import os, json, http.server, urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

LEDGER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ledger.json")
PORT = int(os.environ.get("PORT") or os.environ.get("M2M_PORT", "8001"))
PRICE = float(os.environ.get("M2M_PRICE", "0.05"))
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
