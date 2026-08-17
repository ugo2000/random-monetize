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
