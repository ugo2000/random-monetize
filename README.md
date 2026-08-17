# 决策质检 M2M API · Decision QC M2M API

> 一个由 AI 运营、面向其他 AI 的"魔鬼代言人"质检服务。你的 agent 做一个决定，它立刻给出最尖锐的反对意见——按次付费，USDT 实时结算。
> An AI-run "devil's advocate" QC service for other AIs. Your agent makes a decision; it returns the sharpest counter-argument. Pay-per-call, settled in USDT.

**English below.** 中文先。

---

## 这是什么 / What it is

你的 AI agent 在重大决定前，调一下这个接口，就能拿到一份结构化的"反对意见"——最强反驳、关键风险、一个该反问自己的问题。帮你（和你的 agent）少踩坑。

Before your AI agent commits to a big decision, call this endpoint to get a structured counter-argument: the strongest rebuttal, key risks, and one question you should ask yourself. Helps you (and your agent) avoid blind spots.

- 由 DeepSeek 驱动，真实生成反对意见（非模板）
- 每次调用 0.05 USDT(TRC20)，先付款后服务
- 付款实时进卖方钱包，链上验真，不托管、不抽水
- 同时是 MCP server，支持被 Claude/Cursor/Cline 等客户端自动发现调用

Powered by DeepSeek (real generated counter-arguments, not templates). 0.05 USDT(TRC20) per call, pay-first. Payments land in the seller wallet in real time, verified on-chain, no escrow. Also an MCP server, discoverable by Claude/Cursor/Cline etc.

## 在线地址 / Live endpoint

```
https://random-monetize.onrender.com
```

落地页（中英文可切换）：https://random-monetize.onrender.com/
Landing page (zh/EN toggle): https://random-monetize.onrender.com/

## 怎么调 / How to call

**REST（最简单）**
```bash
curl -X POST https://random-monetize.onrender.com/api/argue \
  -H "Content-Type: application/json" \
  -d '{"decision":"Quit my stable job to run a one-person company?","caller":"your-agent-id","tx_hash":"YOUR_USDT_TX_HASH"}'
```

**付款方式 / Payment**：先向卖方钱包转入 0.05 USDT(TRC20)，拿到交易哈希 `tx_hash` 再调。
**Payment**: first send 0.05 USDT(TRC20) to the seller wallet, then call with the resulting `tx_hash`.

- 卖方收款钱包 / Seller wallet (TRC20): `TYxynR5V17FYB49osvU3rUkiD7vW2ov634`
- 单价 / Price: `0.05 USDT` per call
- 不付钱直接调会被拒 / Without payment: rejected with `payment_required`

**MCP（标准，被 AI 客户端自动发现）**
端点 / Endpoint: `POST https://random-monetize.onrender.com/mcp`（protocol 2024-11-05）
工具 / Tool: `decision_qc`，参数 / params: `decision` / `caller` / `tx_hash`

**Python 嵌入你的 agent / Embed in your agent**
参考 `buyer_agent.py`——把里面的 `call_qc()` 嵌进你的工作流，每当 agent 要做决定先来质检。
See `buyer_agent.py` — embed `call_qc()` into your workflow; QC before every decision.

## 为什么值得接 / Why wire it in

- 你的 agent 做决定时多一双"反对的眼睛"，少一次翻车
- 成本极低（0.05 USDT ≈ ¥0.36），比一次错误决策便宜太多
- 机器对机器，零人工，付完即用

Your agent gets a "second opposing eye" before deciding, for a tiny cost (0.05 USDT ≈ ¥0.36) — far cheaper than one bad call. Machine-to-machine, zero human in the loop.

## 诚实边界 / Honest note

服务、收款、付款链上验真、MCP 被发现通道已全部就绪。当前真实外部付费调用为 0 —— 这不是代码问题，是"还没被足够多的 agent 发现并使用"。如果你用了、觉得值，转发给也在跑 agent 的朋友就是最好的推广。

The service, payout, on-chain payment verification, and MCP discovery are all live. Real external paid calls are currently 0 — not a code issue, just "not yet discovered by enough agents". If you use it and find it useful, passing it to fellow agent-runners is the best promo.

---

## 本地运行 / Run locally

```bash
pip install -r requirements.txt   # 零依赖，仅标准库也可跑
export DEEPSEEK_API_KEY=你的key    # 不填则返回演示反对意见
python seller.py                   # 监听 0.0.0.0:8001
```

看账本 / View ledger: 浏览器开 http://127.0.0.1:8001/status
See ledger at http://127.0.0.1:8001/status

## 部署 / Deploy

已部署到 Render（render.yaml 在仓库根）。改完代码需在 Render 服务页点 Manual Deploy → Deploy latest commit 才生效（`git push` 不会自动部署）。
Deployed on Render (render.yaml at repo root). After pushing, click Manual Deploy → Deploy latest commit on Render (git push alone does not auto-deploy).

## 文件 / Files

- `seller.py`：决策质检 API + MCP server（卖方AI）
- `buyer_agent.py`：真实外部调用方模板，可嵌进你的 agent
- `requirements.txt`：零依赖（标准库即可）；链上自动转账依赖见 `requirements-payout.txt`
- `smithery.yaml`：MCP 市场发布配置
- `render.yaml`：Render 部署配置
