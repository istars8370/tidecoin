"""Read-only authenticated local Tidecoin JSON-RPC client.

Prototype only: this module does not authorize payment settlement.
"""
import base64
import json
import os
import urllib.parse
import urllib.request
import re

TXID = re.compile(r"^[a-fA-F0-9]{64}$")


class RPCError(RuntimeError):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def _local_url(url):
    parsed = urllib.parse.urlsplit(url)
    try:
        port = parsed.port
    except ValueError as exc:
        raise RPCError("Invalid RPC port") from exc
    if (parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "::1", "localhost")
            or port is None or parsed.username is not None or parsed.password is not None
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment):
        raise RPCError("RPC must use an explicit local HTTP host and port")
    return url


class TideRPC:
    def __init__(self, url=None, user=None, password=None, timeout=8):
        self.url = _local_url(url or os.environ.get("TIDE_RPC_URL", "http://127.0.0.1:8754"))
        self.user = user if user is not None else os.environ.get("TIDE_RPC_USER")
        self.password = password if password is not None else os.environ.get("TIDE_RPC_PASSWORD")
        if not self.user or not self.password:
            raise RPCError("Local RPC credentials missing")
        try:
            self.timeout = float(timeout)
        except (TypeError, ValueError) as exc:
            raise RPCError("Invalid RPC timeout") from exc
        if not 0 < self.timeout <= 60:
            raise RPCError("RPC timeout outside allowed range")
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())

    def _call(self, method, params):
        if method not in ("getblockchaininfo", "getrawtransaction", "getblockheader"):
            raise RPCError("RPC method not allowed")
        token = base64.b64encode(f"{self.user}:{self.password}".encode()).decode()
        body = json.dumps({"jsonrpc": "1.0", "id": "payment-kit", "method": method,
                           "params": params}).encode()
        request = urllib.request.Request(self.url, data=body, method="POST",
                                         headers={"Content-Type": "application/json",
                                                  "Authorization": "Basic " + token})
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                payload = json.load(response)
        except Exception as exc:
            raise RPCError("Local RPC request failed") from None
        if not isinstance(payload, dict) or payload.get("error") is not None:
            raise RPCError("Local RPC returned an error")
        return payload.get("result")

    def blockchain_info(self):
        result = self._call("getblockchaininfo", [])
        if not isinstance(result, dict) or not isinstance(result.get("chain"), str):
            raise RPCError("Invalid blockchain info")
        return result

    def raw_transaction(self, txid):
        if not isinstance(txid, str) or not TXID.fullmatch(txid):
            raise RPCError("Invalid transaction ID")
        result = self._call("getrawtransaction", [txid, True])
        if not isinstance(result, dict) or result.get("txid", "").lower() != txid.lower():
            raise RPCError("Transaction ID mismatch")
        return result

    def block_header(self, block_hash):
        if not isinstance(block_hash, str) or not TXID.fullmatch(block_hash):
            raise RPCError("Invalid block hash")
        result = self._call("getblockheader", [block_hash, True])
        if not isinstance(result, dict) or result.get("hash", "").lower() != block_hash.lower():
            raise RPCError("Block hash mismatch")
        return result


def inspect_payment(rpc, invoice, txid, expected_chain):
    """Return an observation, never a final settlement decision.

    Require an explicitly selected chain and an active-chain block header.
    A future reorg can invalidate previously observed confirmations.
    """
    from transaction_validation import verify_transaction
    if not expected_chain or not isinstance(expected_chain, str):
        raise RPCError("Expected chain must be specified")
    info = rpc.blockchain_info()
    if info["chain"] != expected_chain:
        raise RPCError("Wrong Tidecoin network")
    tx = rpc.raw_transaction(txid)
    blockhash = tx.get("blockhash")
    confirmations = tx.get("confirmations")
    if (not isinstance(blockhash, str) or not TXID.fullmatch(blockhash)
            or type(confirmations) is not int or confirmations < 1):
        raise RPCError("Transaction is not confirmed in a block")
    header = rpc.block_header(blockhash)
    header_confirmations = header.get("confirmations")
    if type(header_confirmations) is not int or header_confirmations < 1:
        raise RPCError("Block is not in the active chain")
    if confirmations != header_confirmations:
        raise RPCError("Inconsistent confirmation counts; retry later")
    observation = verify_transaction(invoice, tx)
    observation["confirmations"] = header_confirmations
    observation["blockhash"] = blockhash.lower()
    return observation
