"""Restricted local read-only Tidecoin JSON-RPC client (prototype).

Never authorize merchant settlement based solely on this client.
"""
import base64
import json
import os
import re
import urllib.parse
import urllib.request

TXID = re.compile(r"^[a-fA-F0-9]{64}$")
MAX_RPC_RESPONSE_BYTES = 2 * 1024 * 1024
ALLOWED_METHODS = frozenset(("getblockchaininfo", "getrawtransaction", "getblockheader"))


class RPCError(RuntimeError):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def _local_url(url):
    try:
        parsed = urllib.parse.urlsplit(url)
        port = parsed.port
    except (TypeError, ValueError) as exc:
        raise RPCError("Invalid RPC URL or port") from None
    if (parsed.scheme != "http"
            or parsed.hostname not in ("127.0.0.1", "::1", "localhost")
            or port is None or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment):
        raise RPCError("RPC must use an explicit local HTTP host and port")
    return url


class TideRPC:
    def __init__(self, url=None, user=None, password=None, timeout=8):
        endpoint = url if url is not None else os.environ.get("TIDE_RPC_URL")
        if not endpoint:
            raise RPCError("Explicit TIDE_RPC_URL required; verify port from running node")
        self.url = _local_url(endpoint)
        self.user = user if user is not None else os.environ.get("TIDE_RPC_USER")
        self.password = password if password is not None else os.environ.get("TIDE_RPC_PASSWORD")
        if not isinstance(self.user, str) or not self.user or not isinstance(self.password, str) or not self.password:
            raise RPCError("Local RPC credentials missing")
        try:
            self.timeout = float(timeout)
        except (TypeError, ValueError, OverflowError):
            raise RPCError("Invalid RPC timeout") from None
        if not 0 < self.timeout <= 60:
            raise RPCError("RPC timeout outside allowed range")
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())

    def _call(self, method, params):
        if method not in ALLOWED_METHODS:
            raise RPCError("RPC method not allowed")
        if not isinstance(params, list):
            raise RPCError("RPC params must be an array")
        token = base64.b64encode(f"{self.user}:{self.password}".encode()).decode()
        body = json.dumps({"jsonrpc": "1.0", "id": "payment-kit",
                           "method": method, "params": params}).encode()
        request = urllib.request.Request(
            self.url, data=body, method="POST",
            headers={"Content-Type": "application/json",
                     "Authorization": "Basic " + token})
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                status = getattr(response, "status", 200)
                if status != 200:
                    raise RPCError("Unexpected RPC HTTP status")
                content_length = response.headers.get("Content-Length") if getattr(response, "headers", None) else None
                if content_length is not None:
                    try:
                        declared_size = int(content_length)
                    except (ValueError, TypeError):
                        raise RPCError("Invalid RPC response length") from None
                    if declared_size < 0 or declared_size > MAX_RPC_RESPONSE_BYTES:
                        raise RPCError("RPC response exceeds size limit")
                raw = response.read(MAX_RPC_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RPC_RESPONSE_BYTES:
                    raise RPCError("RPC response exceeds size limit")
            payload = json.loads(raw.decode("utf-8"))
        except RPCError:
            raise
        except (Exception) as exc:
            # Never expose credentials, URLs, server-provided messages or payloads.
            raise RPCError("Local RPC request or response failed") from None
        if (not isinstance(payload, dict)
                or payload.get("error") is not None
                or payload.get("id") != "payment-kit"
                or "result" not in payload):
            raise RPCError("Invalid or unsuccessful local RPC response")
        return payload["result"]

    def blockchain_info(self):
        result = self._call("getblockchaininfo", [])
        if (not isinstance(result, dict)
                or not isinstance(result.get("chain"), str)
                or not result["chain"]):
            raise RPCError("Invalid blockchain info")
        return result

    def raw_transaction(self, txid):
        if not isinstance(txid, str) or not TXID.fullmatch(txid):
            raise RPCError("Invalid transaction ID")
        result = self._call("getrawtransaction", [txid, True])
        if (not isinstance(result, dict)
                or not isinstance(result.get("txid"), str)
                or result["txid"].lower() != txid.lower()):
            raise RPCError("Transaction ID mismatch")
        return result

    def block_header(self, block_hash):
        if not isinstance(block_hash, str) or not TXID.fullmatch(block_hash):
            raise RPCError("Invalid block hash")
        result = self._call("getblockheader", [block_hash, True])
        if (not isinstance(result, dict)
                or not isinstance(result.get("hash"), str)
                or result["hash"].lower() != block_hash.lower()):
            raise RPCError("Block hash mismatch")
        return result


def inspect_payment(rpc, invoice, txid, expected_chain):
    """Read-only confirmed-transaction inspection, not final settlement."""
    from transaction_validation import verify_transaction
    if not isinstance(expected_chain, str) or not expected_chain:
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
