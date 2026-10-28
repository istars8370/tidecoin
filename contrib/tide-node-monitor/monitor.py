#!/usr/bin/env python3
"""Read-only Tidecoin JSON-RPC node monitor (Python 3.9+, standard library)."""
import base64
import json
import os
import sys
import urllib.error
import urllib.request

RPC_URL = os.environ.get("TIDE_RPC_URL", "http://127.0.0.1:8754")
TIMEOUT = float(os.environ.get("TIDE_RPC_TIMEOUT", "8"))


def rpc(method):
    if not RPC_URL.startswith(("http://127.0.0.1:", "http://localhost:", "http://[::1]:")):
        raise ValueError("Only loopback RPC endpoints are allowed in v0.1")
    user = os.environ.get("TIDE_RPC_USER")
    password = os.environ.get("TIDE_RPC_PASSWORD")
    if not user or not password:
        raise ValueError("Set TIDE_RPC_USER and TIDE_RPC_PASSWORD environment variables")
    payload = json.dumps({"jsonrpc": "1.0", "id": "monitor", "method": method, "params": []}).encode()
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    req = urllib.request.Request(
        RPC_URL,
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Basic {token}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
        body = json.load(response)
    if body.get("error"):
        raise RuntimeError(f"RPC {method} returned an error")
    return body["result"]


def main():
    try:
        chain = rpc("getblockchaininfo")
        network = rpc("getnetworkinfo")
        mining = rpc("getmininginfo")
    except (ValueError, RuntimeError, urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as exc:
        # Never print URL, credentials, or raw HTTP exception details.
        print(f"Monitor unavailable: {type(exc).__name__}. Check local RPC settings and node health.", file=sys.stderr)
        return 1

    output = {
        "chain": chain.get("chain"),
        "blocks": chain.get("blocks"),
        "headers": chain.get("headers"),
        "verification_progress": chain.get("verificationprogress"),
        "initial_block_download": chain.get("initialblockdownload"),
        "connections": network.get("connections"),
        "network_hashps": mining.get("networkhashps"),
        "difficulty": mining.get("difficulty"),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
