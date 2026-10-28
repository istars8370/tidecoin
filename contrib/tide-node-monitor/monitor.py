#!/usr/bin/env python3
"""Read-only Tidecoin JSON-RPC monitor (Python 3.9+, standard library)."""
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

METHODS = ("getblockchaininfo", "getnetworkinfo", "getmininginfo")


def local_rpc_url():
    url = os.environ.get("TIDE_RPC_URL", "http://127.0.0.1:8754")
    parsed = urllib.parse.urlsplit(url)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Invalid local RPC port") from exc
    if (parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost", "::1")
            or not port or parsed.username is not None or parsed.password is not None
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment):
        raise ValueError("RPC URL must be a local HTTP endpoint with an explicit port")
    return url


def rpc(method):
    if method not in METHODS:
        raise ValueError("RPC method is not permitted")
    url = local_rpc_url()
    user = os.environ.get("TIDE_RPC_USER")
    password = os.environ.get("TIDE_RPC_PASSWORD")
    if not user or not password:
        raise ValueError("Set TIDE_RPC_USER and TIDE_RPC_PASSWORD")
    try:
        timeout = float(os.environ.get("TIDE_RPC_TIMEOUT", "8"))
    except ValueError as exc:
        raise ValueError("Invalid RPC timeout") from exc
    if not 0 < timeout <= 60:
        raise ValueError("RPC timeout must be between 0 and 60 seconds")
    payload = json.dumps({"jsonrpc": "1.0", "id": "monitor", "method": method, "params": []}).encode()
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    request = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Basic {token}"},
        method="POST",
    )
    # Disable proxy use: local credentials must never be forwarded to a proxy.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=timeout) as response:
        body = json.load(response)
    if not isinstance(body, dict) or body.get("error") or not isinstance(body.get("result"), dict):
        raise RuntimeError("RPC returned an invalid result")
    return body["result"]


def collect():
    chain, network, mining = (rpc(method) for method in METHODS)
    return {
        "chain": chain.get("chain"),
        "blocks": chain.get("blocks"),
        "headers": chain.get("headers"),
        "verification_progress": chain.get("verificationprogress"),
        "initial_block_download": chain.get("initialblockdownload"),
        "connections": network.get("connections"),
        "network_hashps": mining.get("networkhashps"),
        "difficulty": mining.get("difficulty"),
    }


def main():
    try:
        result = collect()
    except (ValueError, RuntimeError, urllib.error.URLError, TimeoutError, OSError,
            KeyError, TypeError, json.JSONDecodeError) as exc:
        # Deliberately suppress raw URL, response body and exception details.
        print(f"Monitor unavailable: {type(exc).__name__}. Check local RPC configuration.", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
