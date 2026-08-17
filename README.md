# 自治 M2M 变现体
两个独立 AI 进程通过网络互相调用、自动交易，收入全部记到 ledger.json 的 owner_total（你的）。

- seller.py：决策质检 API（卖方AI），监听 0.0.0.0:8001
- buyer.py：自动采购方（买方AI），每3秒向卖方下单
- 设了 DEEPSEEK_API_KEY 后，卖方从 mock 切到真实反驳，更值钱
- 收入是虚拟信用 ¥0.05/笔；要做成真钱见下方「公网+收款」

启动：python run_all.py
看收入：浏览器开 http://127.0.0.1:8001/status

## 部署到 Render（公网，让外部 AI 能调到你的卖方接口）
1. 打开 https://render.com ，用 GitHub 登录（就是你这个 ugo2000 账号）。
2. New Web Service → 选仓库 random-monetize → Render 会自动读 render.yaml。
3. 部署前在 Environment 里填环境变量：
   - DEEPSEEK_API_KEY：你的 DeepSeek key（不填也能跑，但只返回演示反对意见，不值钱）
   - M2M_PAYOUT：真钱收款出口（暂时留空，见下）
   - M2M_PAYOUT_THRESHOLD：累计到多少触发结算，默认 10.0
4. 点 Deploy，几分钟后拿到一个 https://xxxx.onrender.com 的公网地址。
5. 验证：浏览器开 https://xxxx.onrender.com/status ，看到 owner_total 字段即成功。

注意：部署上去只是把「卖方接口」放到公网。当前每笔只在 ledger.json 记 ¥0.05 虚拟信用，没有真钱出口；要真收到钱还差两步——①有真实外部 AI 来调用它；②给 M2M_PAYOUT 接一个真能把钱打给你的通道（如加密钱包/Stripe）。buyer.py 只是本地自证闭环用的替身，部署时不要让它跑（仓库里只部署 seller.py，render.yaml 已只启动卖方）。

## 真钱出口（USDT / TRC20）
账本满 M2M_PAYOUT_THRESHOLD 后，seller.py 会把累计金额作为真钱转给你。支持两种模式：

- **模式A · 自动转账（零干预）**：在 Render Environment 设 `SELLER_USDT_ADDR`（卖方收款钱包地址）+ `SELLER_PRIVATE_KEY`（私钥 hex，务必保密）。满阈值时 seller 自动从卖方钱包把 USDT 链上转给你（M2M_PAYOUT 地址）。
- **模式B · 手动提现**：只设 `M2M_PAYOUT`（你的 USDT 地址）不设私钥。满阈值时 ledger 记一笔 `pending_manual`，你看到后从卖方钱包手动转出即可。

启用模式A 还需在 Render 把 **Build Command** 从 `echo ok` 改成 `pip install -r requirements.txt`（安装 tronpy）。不设私钥时 tronpy 不影响运行，服务照常。

新增环境变量一览：
- `M2M_PAYOUT`：你的 USDT(TRC20) 收款地址（真钱出口）
- `M2M_PAYOUT_THRESHOLD`：触发结算阈值，默认 10.0
- `SELLER_USDT_ADDR`：卖方收款钱包（收调用方付的 USDT），模式A 必填
- `SELLER_PRIVATE_KEY`：卖方钱包私钥(hex)，填了即自动链上转出，绝不外泄
- `TRON_API_KEY`：可选，TronGrid API Key，提升节点稳定性

诚实边界：当前调用方 PA 不校验付款（信任记账），所以账本金额是虚拟的，真钱出口要在「调用方先付真 USDT」的前提下才有钱可转。下一步需把 POST /api/argue 改为「先付款后服务」（付款校验模式）。另：加密资产在国内属监管敏感区，请自行评估合规风险，私钥仅在可信环境配置。

## 付款校验模式（先付款后服务 · 让账本里的钱变真）
默认 `M2M_PAYMENT_MODE=trust`（信任记账，账本是虚拟的）。改成 `crypto` 后，调用方**必须先真打一笔 USDT 到卖方钱包**，卖方链上验真了才服务并记账——此时账本金额 = 真实收到的 USDT，满了真能转给你，形成完整 M2M 钱环。

启用（Render Environment 加）：
- `M2M_PAYMENT_MODE=crypto`
- `SELLER_USDT_ADDR`：卖方收款钱包（调用方付款目的地，必填）
- 可选 `TRON_API_KEY`：TronGrid API Key，提升查询稳定性。**验真已做 TronGrid + TronScan 多源兜底，不配任何 key 也能自动选可连通的源去链上验真**

调用方（其他 AI）做法：
```
# 1) 先向 SELLER_USDT_ADDR 转 PRICE 个 USDT(TRC20)，拿到交易哈希 tx_hash
# 2) 再调接口，带上 tx_hash
curl -X POST https://你的地址.onrender.com/api/argue \
  -H "Content-Type: application/json" \
  -d '{"decision":"...","caller":"buyer-agent-id","tx_hash":"你的付款交易哈希"}'
```
卖方服务端会：①查 TronGrid 确认该 tx 是付到本钱包的已确认 Transfer 且金额≥单价；②防重放（tx_hash 只用一次）；③通过才返回反对意见并把真实金额计入 owner_total；④满 `M2M_PAYOUT_THRESHOLD` 触发真钱出口转出给你的 `M2M_PAYOUT` 地址（设了 `SELLER_PRIVATE_KEY` 即自动）。

说明：验证走 TronGrid + TronScan **多源兜底**（公开接口，纯标准库、不引入新依赖），**无需任何 API key** 也能链上验真——部署后会自动选第一个能连通的源；配了 TRON_API_KEY 则 TronGrid 走官方 header 更稳。链上查询偶有限流/未确认，调用方可稍后重试。PRICE 在 crypto 模式下按 USDT 计（默认 0.05 USDT/次）。

## 获客：让别的 AI 自动发现并调用你（MCP）
本服务现在同时是一个 **MCP server**（端点 `POST /mcp`，协议 2024-11-05）。任何支持 MCP 的 AI 客户端（Claude Desktop、Cursor、Cline、各类 agent 框架）都能把它当工具自动发现、调用，甚至付费。这是「机器对机器」获客的底座——不用你手动发广告，别的 AI 在帮用户做决定时会自动来质检。

### 1) 注册到 MCP 市场（被动被发现）
- **smithery.ai**（推荐）：打开 https://smithery.ai → 用 GitHub 登录（ugo2000）→ New Server → Import from GitHub → 选 random-monetize 仓库。它会自动读仓库里的 `smithery.yaml`，端点设为 `https://random-monetize.onrender.com/mcp`。发布后，smithery 用户能一键把「决策质检 M2M」加进自己的 AI 客户端。
- **mcp.so**：打开 https://mcp.so → Submit → 填名称/描述 + 端点 `https://random-monetize.onrender.com/mcp`（transport: Streamable HTTP）。
- 注册要你本人点（沙箱与本机登录态隔离，我代不了），但配置都已写好，你只填两下。

### 2) 别的 agent 怎么调你（主动嵌入）
两种方式任选：
- **REST（简单）**：`POST /api/argue`，body `{"decision":"...","caller":"your-agent-id"}`。参考 `buyer_agent.py`——它就是真实外部调用方模板，把里面的 `call_qc()` 嵌进你自己的 agent 工作流即可：每当你的 agent 要做决定，先来质检。
- **MCP（标准）**：AI 客户端连 `https://random-monetize.onrender.com/mcp`，会看到工具 `decision_qc`，参数 `decision` / `caller` / `tx_hash`。

### 3) 现在谁在调你？
- 部署后默认没人调——获客是业务动作，不是代码。注册市场 + 让 `buyer_agent.py` 被 fork 是起点。
- 你本地也可先 `python buyer_agent.py` 自测（信任模式直接跑，账本会涨，但属演示调用）。

诚实边界：注册 ≠ 立刻有钱。MCP 只是「被发现并被调用」的通道；真正让账本从 0 变正，需要真实的外部 AI 把你的工具接进它的决策流，并（crypto 模式）先付真 USDT。代码、收款、付款校验、被发现通道现在全部就绪，只差「外部 agent 真来用」这一步。
