# Tidecoin local node monitor (v0.1 prototype)

A read-only command-line monitor for a **locally operated** Tidecoin node.
It does not modify consensus, wallet state, transactions, or mining settings.

## Requirements
- Python 3.9+
- A running Tidecoin node with local JSON-RPC enabled
- RPC credentials configured in the node (use dedicated credentials if supported)

## Run

Set the following environment variables in your shell (do not commit passwords):

- `TIDE_RPC_URL`: your local node RPC URL, for example `http://127.0.0.1:<your-rpc-port>`
- `TIDE_RPC_USER`: RPC username
- `TIDE_RPC_PASSWORD`: RPC password
- `TIDE_RPC_TIMEOUT`: optional timeout in seconds (default 8)

Then run:

```sh
python3 contrib/tide-node-monitor/monitor.py
```

The prototype defaults to port 8754 as an **unverified convenience value**.
Check your node's actual RPC port before use. The P2P port (8755 in the
project README) is **not** necessarily the RPC port.

## Output
JSON with chain name, block and header heights, verification progress,
initial download state, peer count, estimated network hashrate and difficulty.
Fields unavailable in a given node version may be null.

## Safety and limitations
- Only loopback HTTP RPC URLs are accepted; never expose RPC publicly.
- Credentials are read from environment variables, never hard-coded.
- No wallet RPC calls, private keys, or transactions are used.
- Error output intentionally avoids raw HTTP messages that may contain secrets.
- This is a prototype; it has **not** been tested against a running Tidecoin node.
- Future work: mock RPC unit tests, explicit cookie-auth support, periodic
  sampling, stale-tip detection, and a local browser dashboard.
