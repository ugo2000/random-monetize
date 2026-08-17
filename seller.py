#!/usr/bin/env python3
import os, json, http.server, urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

LEDGER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ledger.json")
PORT = int(os.environ.get("PORT") or os.environ.get("M2M_PORT", "8001"))
PRICE = float(os.environ.get("M2M_PRICE", "0.05"))
KEY = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")
PAYOUT_TARGET = os.environ.get("M2M_PAYOUT", "")          # 你的 USDT(TRC20) 收款地址
PAYOUT_THRESHOLD = float(os.environ.get("M2M_PAYOUT_THRESHOLD", "10.0"))
SELLER_USDT_ADDR = os.environ.get("SELLER_USDT_ADDR", "")   # 卖方收款钱包(收调用方付的 USDT)
SELLER_PRIVATE_KEY = os.environ.get("SELLER_PRIVATE_KEY", "")  # 卖方钱包私钥(hex)，填了即自动链上转出
TRON_API_KEY = os.environ.get("TRON_API_KEY", "")           # 可选：TronGrid API Key，提升节点稳定性
OWNER_PAYOUT_INITIATED = False

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

# ---------- 真钱出口（USDT / TRC20）----------
def do_payout(L):
    """账本满阈值后，把累计金额作为真钱转给 M2M_PAYOUT 指定的 USDT 地址。
    返回 True 表示已发起（paid 或 pending_manual），False 表示未配置目标。"""
    global OWNER_PAYOUT_INITIATED
    target = PAYOUT_TARGET
    amt = round(L["owner_total"], 6)
    if not target:
        return False
    # 模式A：填了卖方私钥 -> 自动链上转账（零干预）
    if SELLER_PRIVATE_KEY and SELLER_USDT_ADDR:
        try:
            import payout_crypto
            res = payout_crypto.transfer_usdt(SELLER_PRIVATE_KEY, SELLER_USDT_ADDR, target, amt, TRON_API_KEY)
            txid = (res.get("txid") or (res.get("transaction") or {}).get("txID")) if isinstance(res, dict) else None
            L.setdefault("payouts", []).append({"status": "paid", "amount": amt, "target": target, "txid": txid})
            OWNER_PAYOUT_INITIATED = True
            return True
        except Exception as e:
            L.setdefault("payouts", []).append({"status": "crypto_failed", "amount": amt, "target": target, "err": str(e)[:200]})
    # 模式B：未填私钥 -> 记待提现，供你手动从卖方钱包转出
    L.setdefault("payouts", []).append({"status": "pending_manual", "amount": amt, "target": target,
                                         "note": "需在卖方钱包手动提现到该地址（设 SELLER_PRIVATE_KEY 可改自动）"})
    OWNER_PAYOUT_INITIATED = True
    return True

class H(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        self.send_response(code); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(json.dumps(obj, ensure_ascii=False).encode("utf-8"))
    def _send_html(self, html):
        self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers()
        self.wfile.write(html.encode("utf-8"))
    def _landing(self):
        L = load()
        mode = "real" if KEY else "mock"
        return """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>决策质检 M2M API · 已上线</title>
<style>body{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:#0f1115;color:#e8eaed;margin:0;padding:36px 20px;line-height:1.6}.wrap{max-width:720px;margin:0 auto}.badge{display:inline-block;padding:3px 10px;border-radius:999px;font-size:13px;background:#16351f;color:#7ee2a8;border:1px solid #2c6b43}.h{font-size:26px;margin:14px 0 4px}.sub{color:#9aa0a6;margin:0 0 24px}.card{background:#171a21;border:1px solid #262b34;border-radius:12px;padding:18px 20px;margin:14px 0}.k{color:#9aa0a6;font-size:13px;margin-bottom:6px}.v{font-size:22px;font-weight:600;color:#7ee2a8}.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;background:#0c0e12;padding:12px 14px;border-radius:8px;color:#cfe3ff;font-size:13px;overflow-x:auto;white-space:pre}code{background:#0c0e12;padding:1px 6px;border-radius:4px;color:#cfe3ff}a{color:#7ee2a8}</style></head>
<body><div class="wrap">
<span class="badge">● 服务运行中 · 模式: __MODE__</span>
<h1 class="h">决策质检 M2M API</h1>
<p class="sub">一个由 AI 运营、面向其他 AI 的"魔鬼代言人"质检服务。你做一个决定，它给你最尖锐的反对意见。</p>
<div class="card"><div class="k">累计收入（账本）</div><div class="v">¥ __TOTAL__</div><div class="k" style="margin-top:8px">调用次数 __CALLS__ · 单价 ¥__PRICE__ · 结算阈值 ¥__THRESH__</div></div>
<div class="card"><div class="k">调用方式（POST /api/argue）</div><div class="mono">curl -X POST https://__HOST__/api/argue \\
  -H "Content-Type: application/json" \\
  -d '{"decision":"要不要辞掉工作做一人公司","caller":"your-agent-id"}'</div></div>
<div class="card"><div class="k">返回示例</div><div class="mono">{"result":{"strongest":"...","risks":[...],"question":"..."},"charged":__PRICE__,"owner_total":__TOTAL__}</div></div>
<p class="sub" style="margin-top:24px">本服务由自治 M2M 变现体提供 · 账本每 5 秒自动刷新</p>
</div>
<script>setInterval(()=>fetch('/status').then(r=>r.json()).then(s=>{document.querySelector('.v').textContent='¥ '+s.owner_total.toFixed(2);const c=document.querySelectorAll('.card')[0].querySelectorAll('.k')[1];if(c)c.textContent='调用次数 '+s.calls+' · 单价 ¥__PRICE__ · 结算阈值 ¥__THRESH__';}).catch(()=>{}),5000);</script>
</body></html>""".replace("__MODE__", mode).replace("__TOTAL__", str(round(L["owner_total"],2))).replace("__CALLS__", str(len(L["txns"]))).replace("__PRICE__", str(PRICE)).replace("__THRESH__", str(PAYOUT_THRESHOLD)).replace("__HOST__", self.headers.get("Host", "random-monetize.onrender.com"))
    def do_GET(self):
        if self.path == "/status":
            L = load()
            last = (L.get("payouts") or [{}])[-1]
            self._send(200, {"owner_total": L["owner_total"], "calls": len(L["txns"]), "payout_target": PAYOUT_TARGET, "payout_threshold": PAYOUT_THRESHOLD, "mode": "real" if KEY else "mock", "price": PRICE, "last_payout": last})
        else:
            self._send_html(self._landing())
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
        if PAYOUT_TARGET and L["owner_total"] >= PAYOUT_THRESHOLD and not OWNER_PAYOUT_INITIATED:
            do_payout(L)
        save(L)
        self._send(200, {"result": res, "charged": PRICE, "owner_total": L["owner_total"]})
    def log_message(self, *a): pass

if __name__ == "__main__":
    print("[卖方AI] 决策质检API 监听 :" + str(PORT) + " | 模式:" + ("real" if KEY else "mock") + " | 单价 ¥" + str(PRICE))
    HTTPServer(("0.0.0.0", PORT), H).serve_forever()
