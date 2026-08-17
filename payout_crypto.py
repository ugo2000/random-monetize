#!/usr/bin/env python3
"""真钱出口 · USDT(TRC20) 链上转账。
依赖 tronpy（仅在启用自动转账时才需要；未安装/未配置私钥时卖方服务仍正常运行，退回手动提现模式）。
USDT TRC20 主网合约：TR7NHqjeKQxXPioxH9iAgJJxwBzEWEwZvW（6 位小数）。
"""
from urllib.request import urlopen
import json

USDT_CONTRACT = "TR7NHqjeKQxXPioxH9iAgJJxwBzEWEwZvW"

def _client(api_key=""):
    from tronpy import Tron
    return Tron(network="mainnet", api_key=api_key) if api_key else Tron(network="mainnet")

def transfer_usdt(private_key_hex, from_addr, to_addr, amount_usdt, api_key=""):
    """从卖方钱包把 amount_usdt 个 USDT 转到 to_addr。返回广播结果(dict, 含 txid)。"""
    from tronpy.keys import PrivateKey
    client = _client(api_key)
    sk = PrivateKey(bytes.fromhex(private_key_hex))
    usdt = client.get_contract(USDT_CONTRACT)
    # TRC20 transfer(to, amount*1e6)
    txn = usdt.functions.transfer(to_addr, int(round(amount_usdt * 1_000_000)))
    txn = txn.with_owner(from_addr)
    signed = txn.sign(sk)
    return client.broadcast(signed)

def balance_usdt(addr, api_key=""):
    """查询某地址 USDT 余额（用于校验卖方钱包是否到账/够 gas）。"""
    try:
        url = f"https://api.trongrid.io/v1/accounts/{addr}/tokens/trc20?contract_address={USDT_CONTRACT}"
        if api_key:
            url += f"&api_key={api_key}"
        r = urlopen(url, timeout=15)
        data = json.loads(r.read())
        for t in data.get("data", []):
            if t.get("token_id") == USDT_CONTRACT:
                return float(t.get("balance", 0)) / 1_000_000
        return 0.0
    except Exception:
        return None

if __name__ == "__main__":
    print("payout_crypto 模块：由 seller.py 在满阈值时调用 transfer_usdt()。")
