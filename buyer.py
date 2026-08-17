#!/usr/bin/env python3
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
