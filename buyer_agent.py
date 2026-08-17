#!/usr/bin/env python3
"""
真实外部调用方（买方 AI）模板 —— 演示别的 AI 如何自动调用「决策质检 M2M」。

这就是获客的形态：把下面 call_qc() 嵌进你自己的 agent 工作流，
每当你的 agent 要做重大决策，先来质检一下，再行动。

- trust 模式（服务默认）：直接 python buyer_agent.py 即可循环调用演示。
- crypto 付费模式：先向卖方钱包付 USDT、带 tx_hash，服务端链上验真后才服务，
  见 pay_and_call() 注释骨架。

环境变量：
  M2M_SELLER_URL  卖方地址，默认 https://random-monetize.onrender.com
  M2M_BUYER_ID    你的 agent 标识（出现在卖方账本里）
"""
import json, time, urllib.request, os

BASE = os.environ.get("M2M_SELLER_URL", "https://random-monetize.onrender.com")
ME = os.environ.get("M2M_BUYER_ID", "buyer-agent-" + os.urandom(3).hex())

DECISIONS = [
    "辞掉稳定工作、全职做一人公司",
    "把全部积蓄投进这个 AI 项目",
    "放弃现有客户、专心做这个新产品",
    "现在就涨价 3 倍测试市场",
    "拒绝这个大客户、守住自己的节奏",
]

def call_qc(decision, caller=ME):
    """信任模式调用（REST）。返回服务端 JSON。"""
    body = json.dumps({"decision": decision, "caller": caller}).encode()
    req = urllib.request.Request(BASE + "/api/argue", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        r = urllib.request.urlopen(req, timeout=30)
        return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}

def pay_and_call(decision, seller_addr, caller=ME):
    """crypto 付费模式骨架（需你接入自己的钱包 SDK）。
    流程：①向 seller_addr 转 PRICE 个 USDT(TRC20) 拿到 tx_hash；②带 tx_hash 调用。"""
    # tx_hash = send_usdt(seller_addr, PRICE)   # 用你自己的 TRC20 钱包 SDK 实现
    # body = json.dumps({"decision": decision, "caller": caller, "tx_hash": tx_hash}).encode()
    # req = urllib.request.Request(BASE + "/api/argue", data=body,
    #                              headers={"Content-Type": "application/json"})
    # return json.loads(urllib.request.urlopen(req, timeout=30).read())
    raise NotImplementedError("crypto 付款需接入你的钱包 SDK；信任模式直接 call_qc() 即可。")

def loop(interval=5):
    print(f"[买方AI {ME}] 开始循环调用 {BASE}/api/argue（Ctrl+C 停止）")
    i = 0
    while True:
        d = DECISIONS[i % len(DECISIONS)]
        res = call_qc(d)
        print(f"\n决定: {d}")
        if "result" in res:
            rj = res["result"]
            print(f"  最强反对: {rj.get('strongest')}")
            print(f"  风险: {rj.get('risks')}")
            print(f"  追问: {rj.get('question')}")
            print(f"  本次计费: {res.get('charged')} | 卖方账本累计: {res.get('owner_total')}")
        else:
            print(f"  失败: {res}")
        i += 1
        time.sleep(interval)

if __name__ == "__main__":
    loop()
