#!/usr/bin/env python3
import os, json, http.server, urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

LEDGER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ledger.json")
PORT = int(os.environ.get("PORT") or os.environ.get("M2M_PORT", "8001"))
PRICE = float(os.environ.get("M2M_PRICE", "0.1"))
KEY = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")
# 默认值已内置收款地址与 crypto 模式（与 render.yaml 一致，环境变量可覆盖）。
# 这样即便 Render 环境变量未生效，部署后也直接用欧易 USDT(TRC20) 收款地址，避免一直跑默认 trust。
PAYOUT_TARGET = os.environ.get("M2M_PAYOUT", "TYxynR5V17FYB49osvU3rUkiD7vW2ov634")          # 你的 USDT(TRC20) 收款地址
PAYOUT_THRESHOLD = float(os.environ.get("M2M_PAYOUT_THRESHOLD", "10.0"))
SELLER_USDT_ADDR = os.environ.get("SELLER_USDT_ADDR", "TYxynR5V17FYB49osvU3rUkiD7vW2ov634")   # 卖方收款钱包(收调用方付的 USDT)
SELLER_PRIVATE_KEY = os.environ.get("SELLER_PRIVATE_KEY", "")  # 卖方钱包私钥(hex)，填了即自动链上转出
TRON_API_KEY = os.environ.get("TRON_API_KEY", "")           # 可选：TronGrid API Key，提升节点稳定性
PAYMENT_MODE = os.environ.get("M2M_PAYMENT_MODE", "crypto")   # trust(信任记账) | crypto(先付款后服务)
OWNER_PAYOUT_INITIATED = False

def load():
    try:
        return json.load(open(LEDGER, encoding="utf-8"))
    except Exception:
        return {"owner_total": 0.0, "txns": [], "payouts": []}

def save(L):
    json.dump(L, open(LEDGER, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

# 机器可读的项目说明（llms.txt 标准：供 LLM/AI 检索工具理解本服务）
LLMS_TXT = """# Decision QC M2M API

> An AI-run "devil's advocate" quality-control API for other AIs. Your agent posts a decision; it returns the sharpest counter-argument. MCP server, pay-per-call 0.1 USDT(TRC20). (TRC20 exchanges require a 0.1 USDT minimum deposit per transfer, so each payment equals exactly one call.)

## Endpoints
- REST: POST https://random-monetize.onrender.com/api/argue
- MCP: https://random-monetize.onrender.com/mcp  (protocol 2024-11-05, tool: decision_qc)

## Call (REST)
curl -X POST https://random-monetize.onrender.com/api/argue -H "Content-Type: application/json" -d '{"decision":"Quit my stable job to run a one-person company?","caller":"your-agent-id","tx_hash":"YOUR_USDT_TX_HASH"}'

## Payment
Send 0.1 USDT(TRC20) to seller wallet TYxynR5V17FYB49osvU3rUkiD7vW2ov634 (TRC20 minimum deposit is 0.1 USDT per transfer, so one payment = one call), then call with tx_hash. No payment -> rejected (payment_required).

## Discoverable by
- GitHub search (repo topics: mcp-server, ai-agent, usdt, automation)
- Search engines (sitemap.xml, robots.txt, JSON-LD on landing page)
- MCP clients (Claude/Cursor/Cline) via /mcp

## Files
- seller.py: decision QC API + MCP server
- buyer_agent.py: example external caller to embed in your agent
- README.md: full documentation
"""

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

# ---------- 付款校验（先付款后服务）----------
USDT_CONTRACT = "TR7NHqjeKQxXPioxH9iAgJJxwBzEWEwZvW"  # USDT TRC20 主网

def verify_payment(tx_hash, expected_usdt, payer_addr=""):
    """链上核验一笔 USDT(TRC20) 转账是否真实付到卖方钱包且金额足够。
    多源兜底：TronGrid（配了 TRON_API_KEY 走官方 header，否则走公开接口）+ TronScan 公开接口。
    纯标准库，无额外依赖。部署端自动选第一个能连通的源。"""
    if not SELLER_USDT_ADDR:
        return {"ok": False, "reason": "未配置卖方收款地址"}
    tg_headers = {"TRON-PRO-API-KEY": TRON_API_KEY} if TRON_API_KEY else {}
    providers = [
        ("trongrid",
         "https://api.trongrid.io/v1/contracts/" + USDT_CONTRACT +
         "/events?transaction_id=" + tx_hash + "&event_name=Transfer&only_confirmed=true",
         tg_headers),
        ("tronscan",
         "https://apilist.tronscan.org/api/token_trc20/transfers?contract=" + USDT_CONTRACT +
         "&transactionHash=" + tx_hash + "&confirm=1",
         {"User-Agent": "Mozilla/5.0"}),
    ]
    last_err = ""
    for name, url, headers in providers:
        for _ in range(2):  # 单源偶发限流重试一次
            try:
                req = urllib.request.Request(url)
                for k, v in headers.items():
                    req.add_header(k, v)
                r = urllib.request.urlopen(req, timeout=15)
                data = json.loads(r.read())
                break
            except Exception:
                pass
        else:
            last_err = name + " 查询失败"
            continue
        # 解析：trongrid 在 data[].result；tronscan 在 data[] 顶层
        rows = data.get("data") or []
        for ev in rows:
            res = ev.get("result") or ev
            to = res.get("to", "")
            val = res.get("value", "0")
            frm = res.get("from", "")
            if to == SELLER_USDT_ADDR:
                try:
                    amt = int(str(val)) / 1_000_000
                except Exception:
                    try:
                        amt = float(str(val))
                    except Exception:
                        amt = 0
                if amt + 1e-9 >= expected_usdt:
                    if payer_addr and frm != payer_addr:
                        return {"ok": False, "reason": "付款方与 caller 不匹配"}
                    return {"ok": True, "amount": amt, "from": frm, "via": name}
        # 该源无匹配行；tronscan 用 transactionHash 精确过滤且有行，说明确实没付到本钱包
        if name == "tronscan" and rows:
            return {"ok": False, "reason": "未找到付到本钱包的已确认转账"}
    return {"ok": False, "reason": "全部源查询失败: " + last_err}

class H(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        self.send_response(code); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(json.dumps(obj, ensure_ascii=False).encode("utf-8"))
    def _handle_mcp(self):
        n = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(n) or b"{}"
        try:
            msg = json.loads(raw)
        except Exception:
            self._send(400, {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}); return
        method = msg.get("method"); mid = msg.get("id")
        sid = self.headers.get("Mcp-Session-Id") or os.urandom(8).hex()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Mcp-Session-Id", sid)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Mcp-Session-Id, Accept")
        self.end_headers()
        if method == "initialize":
            self.wfile.write(json.dumps({"jsonrpc": "2.0", "id": mid, "result": {
                "protocolVersion": MCP_PROTOCOL, "capabilities": {"tools": {}},
                "serverInfo": {"name": "决策质检M2M", "version": "1.0.0"}}}).encode()); return
        if method in ("notifications/initialized", "ping"):
            self.wfile.write(json.dumps({"jsonrpc": "2.0", "id": mid, "result": {}}).encode()); return
        if method == "tools/list":
            self.wfile.write(json.dumps({"jsonrpc": "2.0", "id": mid, "result": {"tools": [TOOL_DEF]}}).encode()); return
        if method == "tools/call":
            params = msg.get("params", {}) or {}
            if params.get("name") != "decision_qc":
                self.wfile.write(json.dumps({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "unknown tool"}}).encode()); return
            args = params.get("arguments", {}) or {}
            code, obj = _settle(args.get("decision", ""), args.get("caller", ""), args.get("tx_hash"))
            is_error = (code != 200)
            text = json.dumps(obj, ensure_ascii=False) if is_error else json.dumps(obj.get("result", {}), ensure_ascii=False)
            self.wfile.write(json.dumps({"jsonrpc": "2.0", "id": mid, "result": {
                "content": [{"type": "text", "text": text}], "isError": is_error}}).encode()); return
        self.wfile.write(json.dumps({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "method not found"}}).encode())
    def _send_html(self, html):
        self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers()
        self.wfile.write(html.encode("utf-8"))
    def _send_text(self, body, ctype="text/plain; charset=utf-8"):
        self.send_response(200); self.send_header("Content-Type", ctype); self.end_headers()
        self.wfile.write(body.encode("utf-8"))
    def _landing(self):
        L = load()
        mode = "real" if KEY else "mock"
        html = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>决策质检 M2M API · AI 决策反对意见服务 / Decision QC M2M API</title>
<meta name="description" content="AI-run devil's advocate QC API for other AIs. POST a decision, get the sharpest counter-argument. MCP server, pay-per-call 0.1 USDT(TRC20).">
<meta name="keywords" content="MCP, AI agent, devil's advocate, decision QC, USDT, pay-per-call, LLM API, automation">
<meta property="og:title" content="Decision QC M2M API">
<meta property="og:description" content="An AI devil's advocate for other AIs. MCP server, pay-per-call 0.1 USDT(TRC20).">
<meta property="og:type" content="website">
<meta property="og:url" content="https://random-monetize.onrender.com/">
<meta name="twitter:card" content="summary">
<style>body{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:#0f1115;color:#e8eaed;margin:0;padding:36px 20px;line-height:1.6}.wrap{max-width:720px;margin:0 auto}.badge{display:inline-block;padding:3px 10px;border-radius:999px;font-size:13px;background:#16351f;color:#7ee2a8;border:1px solid #2c6b43}.h{font-size:26px;margin:14px 0 4px}.sub{color:#9aa0a6;margin:0 0 24px}.card{background:#171a21;border:1px solid #262b34;border-radius:12px;padding:18px 20px;margin:14px 0}.k{color:#9aa0a6;font-size:13px;margin-bottom:6px}.v{font-size:22px;font-weight:600;color:#7ee2a8}.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;background:#0c0e12;padding:12px 14px;border-radius:8px;color:#cfe3ff;font-size:13px;overflow-x:auto;white-space:pre}code{background:#0c0e12;padding:1px 6px;border-radius:4px;color:#cfe3ff}a{color:#7ee2a8}.en{color:#8b929b;font-size:13px;margin-top:6px;line-height:1.5}.langbar{position:fixed;top:12px;right:14px;z-index:9}.langbar button{background:#171a21;color:#7ee2a8;border:1px solid #2c6b43;border-radius:8px;padding:6px 14px;cursor:pointer;font-size:14px}body.zh .en{display:none}body.en .zh{display:none}body.en .en{display:block}</style>
<script type="application/ld+json">{"@context":"https://schema.org","@type":"SoftwareApplication","name":"Decision QC M2M API","applicationCategory":"DeveloperApplication","operatingSystem":"Web","description":"AI-run devil's advocate QC service for other AIs. MCP server, pay-per-call 0.1 USDT(TRC20).","url":"https://random-monetize.onrender.com/","offers":{"@type":"Offer","price":"0.1","priceCurrency":"USDT"},"potentialAction":{"@type":"InvokeAction","target":"https://random-monetize.onrender.com/api/argue"}}</script></head>
<body class="zh"><div class="wrap">
<span class="langbar"><button onclick="toggleLang()" id="langbtn">EN</button></span>
<span class="badge zh">● 服务运行中 · 模式: __MODE__</span><span class="badge en">● Service Live · Mode: __MODE__</span>
<h1 class="h zh">决策质检 M2M API</h1><h1 class="h en">Decision QC M2M API</h1>
<p class="sub zh">一个由 AI 运营、面向其他 AI 的“魔鬼代言人”质检服务。你做一个决定，它给你最尖锐的反对意见。</p>
<p class="en">An AI-run "devil's advocate" QC service for other AIs. You make a decision; it returns the sharpest counter-argument.</p>
<div class="card"><div class="k zh">累计收入（账本）</div><div class="k en">Total Earnings (Ledger)</div><div class="v">__TOTAL__ USDT</div><div class="k zh" style="margin-top:8px">调用次数 <span id="calls">__CALLS__</span> · 单价 __PRICE__ USDT · 结算阈值 __THRESH__ USDT</div><div class="k en" style="margin-top:8px">Calls <span id="calls-en">__CALLS__</span> · Price __PRICE__ USDT · Payout Threshold __THRESH__ USDT</div></div>
<div class="card"><div class="k zh">调用方式（POST /api/argue）</div><div class="k en">How to call (POST /api/argue)</div><div class="mono zh">curl -X POST https://__HOST__/api/argue -H "Content-Type: application/json" -d '{"decision":"要不要辞掉工作做一人公司","caller":"your-agent-id"}'</div><div class="mono en">curl -X POST https://__HOST__/api/argue -H "Content-Type: application/json" -d '{"decision":"Quit my stable job to run a one-person company?","caller":"your-agent-id"}'</div>
<div class="k zh" style="margin-top:8px">免费试调：直接发一个 decision 即可；付费模式需先转 USDT（见“付款方式”）。</div>
<div class="en">Free trial: just send a decision. Paid mode requires a USDT transfer first (see Payment).</div>
<div class="card"><div class="k zh">返回示例</div><div class="k en">Example response</div><div class="mono">{"result":{"strongest":"...","risks":[...],"question":"..."},"charged":__PRICE__,"owner_total":__TOTAL__}</div></div>
<div class="card"><div class="k zh">付款方式</div><div class="k en">Payment</div><div class="mono zh">__PAY_ZH__</div><div class="mono en">__PAY_EN__</div></div>
<p class="sub zh" style="margin-top:24px">本服务由自治 M2M 变现体提供 · 账本每 5 秒自动刷新</p>
<p class="en">Served by an autonomous M2M monetization agent · ledger auto-refreshes every 5s</p>
</div>
<script>function toggleLang(){const b=document.body;b.classList.toggle('en');b.classList.toggle('zh');const en=b.classList.contains('en');const btn=document.getElementById('langbtn');if(btn)btn.textContent=en?'中文':'EN';try{localStorage.setItem('lang',en?'en':'zh')}catch(e){}}try{const saved=localStorage.getItem('lang');if(saved==='en'){document.body.classList.add('en');document.body.classList.remove('zh');const btn=document.getElementById('langbtn');if(btn)btn.textContent='中文'}}catch(e){}setInterval(()=>{fetch('/status').then(r=>r.json()).then(s=>{const t=document.querySelector('.v');if(t)t.textContent=s.owner_total.toFixed(2)+' USDT';const c=document.getElementById('calls');if(c)c.textContent=s.calls;const ce=document.getElementById('calls-en');if(ce)ce.textContent=s.calls;}).catch(()=>{})},5000);</script>
</body></html>"""
        if PAYMENT_MODE == "crypto" and SELLER_USDT_ADDR:
            pay_zh = "先向 "+SELLER_USDT_ADDR+" 转入 "+str(PRICE)+" USDT(TRC20)，再 POST 带 tx_hash 才服务（链上验真）"
            pay_en = "Send "+str(PRICE)+" USDT(TRC20) to "+SELLER_USDT_ADDR+" first, then POST with tx_hash to get served (on-chain verified)"
        elif PAYMENT_MODE == "crypto":
            pay_zh = "crypto 模式：需先设 SELLER_USDT_ADDR，调用方先付 USDT 再带 tx_hash"
            pay_en = "crypto mode: set SELLER_USDT_ADDR; caller pays USDT then sends tx_hash"
        else:
            pay_zh = "信任记账（调用即记，虚拟信用；非真实收款）"
            pay_en = "Trust accounting (logged on call; virtual credit, not real money)"
        return html.replace("__MODE__", mode).replace("__TOTAL__", str(round(L["owner_total"],2))).replace("__CALLS__", str(len(L["txns"]))).replace("__PRICE__", str(PRICE)).replace("__THRESH__", str(PAYOUT_THRESHOLD)).replace("__HOST__", self.headers.get("Host", "random-monetize.onrender.com")).replace("__PAY_ZH__", pay_zh).replace("__PAY_EN__", pay_en)
    def do_GET(self):
        if self.path == "/status":
            L = load()
            last = (L.get("payouts") or [{}])[-1]
            self._send(200, {"owner_total": L["owner_total"], "calls": len(L["txns"]), "payout_target": PAYOUT_TARGET, "payout_threshold": PAYOUT_THRESHOLD, "mode": "real" if KEY else "mock", "price": PRICE, "last_payout": last, "payment_mode": PAYMENT_MODE, "seller_addr": SELLER_USDT_ADDR})
        elif self.path == "/robots.txt":
            self._send_text("User-agent: *\nAllow: /\nSitemap: https://random-monetize.onrender.com/sitemap.xml\n")
        elif self.path == "/sitemap.xml":
            self._send_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://random-monetize.onrender.com/</loc><changefreq>daily</changefreq><priority>1.0</priority></url></urlset>', "application/xml; charset=utf-8")
        elif self.path == "/llms.txt":
            self._send_text(LLMS_TXT, "text/plain; charset=utf-8")
        else:
            self._send_html(self._landing())
    def do_POST(self):
        if self.path == "/mcp":
            self._handle_mcp(); return
        if self.path != "/api/argue":
            self._send(404, {"error": "not found"}); return
        n = int(self.headers.get("Content-Length", "0"))
        b = json.loads(self.rfile.read(n) or b"{}")
        code, obj = _settle(b.get("decision", ""), b.get("caller", ""), b.get("tx_hash") or b.get("payment_tx"))
        self._send(code, obj)
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Mcp-Session-Id, Accept")
        self.end_headers()
    def log_message(self, *a): pass

# ---------- MCP server（让别的 AI 能自动发现并调用本服务）----------
MCP_PROTOCOL = "2024-11-05"
TOOL_DEF = {
    "name": "decision_qc",
    "description": "对一项决定做「魔鬼代言人」反方质检：返回最强反对论点、3 条风险、一个尖锐反问。用于 AI 在重大决策前自查漏洞。crypto 付费模式下需先付 USDT 并带 tx_hash。",
    "inputSchema": {
        "type": "object",
        "properties": {
            "decision": {"type": "string", "description": "要被质检的决定，如『辞掉工作做一人公司』"},
            "caller": {"type": "string", "description": "调用方 agent 标识（可选）"},
            "tx_hash": {"type": "string", "description": "crypto 模式下必填：先付 USDT(TRC20) 的交易哈希"}
        },
        "required": ["decision"]
    }
}

def _settle(decision, caller, tx_hash):
    """统一结算入口：trust/crypto 两模式共用。返回 (http_code, dict)。"""
    if PAYMENT_MODE == "crypto":
        if not SELLER_USDT_ADDR:
            return (500, {"error": "config", "hint": "crypto 模式需设 SELLER_USDT_ADDR（卖方收款钱包）"})
        if not tx_hash:
            return (402, {"error": "payment_required", "hint": "先向卖方钱包转入 " + str(PRICE) + " USDT(TRC20)，再带 tx_hash",
                          "seller": SELLER_USDT_ADDR, "price_usdt": PRICE})
        L = load()
        if tx_hash in L.get("paid_txns", []):
            return (402, {"error": "replay", "hint": "该交易哈希已被使用过"})
        v = verify_payment(tx_hash, PRICE)
        if not v["ok"]:
            return (402, {"error": "payment_invalid", "reason": v["reason"]})
        amt = v["amount"]
        res = argue(decision)
        L["owner_total"] = round(L["owner_total"] + amt, 6)
        L.setdefault("paid_txns", []).append(tx_hash)
        L["txns"].append({"from": caller or v.get("from", "agent"), "amt": amt, "tx": tx_hash[:14] + "..."})
        if len(L["txns"]) > 500: L["txns"] = L["txns"][-500:]
        if PAYOUT_TARGET and L["owner_total"] >= PAYOUT_THRESHOLD and not OWNER_PAYOUT_INITIATED:
            do_payout(L)
        save(L)
        return (200, {"result": res, "charged": amt, "owner_total": L["owner_total"]})
    res = argue(decision)
    L = load(); L["owner_total"] = round(L["owner_total"] + PRICE, 4)
    L["txns"].append({"from": caller or "agent", "amt": PRICE})
    if len(L["txns"]) > 500: L["txns"] = L["txns"][-500:]
    if PAYOUT_TARGET and L["owner_total"] >= PAYOUT_THRESHOLD and not OWNER_PAYOUT_INITIATED:
        do_payout(L)
    save(L)
    return (200, {"result": res, "charged": PRICE, "owner_total": L["owner_total"]})

if __name__ == "__main__":
    print("[卖方AI] 决策质检API 监听 :" + str(PORT) + " | 模式:" + ("real" if KEY else "mock") + " | 单价 " + str(PRICE) + " USDT")
    HTTPServer(("0.0.0.0", PORT), H).serve_forever()
