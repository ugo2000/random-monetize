# 自治 M2M 变现体
两个独立 AI 进程通过网络互相调用、自动交易，收入全部记到 ledger.json 的 owner_total（你的）。

- seller.py：决策质检 API（卖方AI），监听 0.0.0.0:8001
- buyer.py：自动采购方（买方AI），每3秒向卖方下单
- 设了 DEEPSEEK_API_KEY 后，卖方从 mock 切到真实反驳，更值钱
- 收入是虚拟信用 ¥0.05/笔；要做成真钱见下方「公网+收款」

启动：python run_all.py
看收入：浏览器开 http://127.0.0.1:8001/status
