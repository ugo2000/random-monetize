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
