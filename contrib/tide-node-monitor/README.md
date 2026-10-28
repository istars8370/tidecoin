# Tidecoin local node monitor (v0.2 prototype)

A **read-only** Python command-line monitor for a locally operated Tidecoin node.
It does not modify consensus, wallet state, transactions, or mining settings.

## Requirements
- Python 3.9+ (no third-party packages)
- A running Tidecoin node with local JSON-RPC enabled for live monitoring
- RPC credentials configured in the node

## Run on Windows PowerShell

Open PowerShell in the repository root. Replace the RPC port with the actual
port from your Tidecoin node configuration; do not confuse it with the P2P port.

```powershell
$env:TIDE_RPC_URL = "http://127.0.0.1:YOUR_RPC_PORT"
$env:TIDE_RPC_USER = "YOUR_RPC_USER"
$env:TIDE_RPC_PASSWORD = "YOUR_RPC_PASSWORD"
py -3 contrib/tide-node-monitor/monitor.py
```

Remove the temporary variables from that PowerShell session after use:

```powershell
Remove-Item Env:TIDE_RPC_PASSWORD
Remove-Item Env:TIDE_RPC_USER
```

**Caution:** Setting secrets interactively may expose them in terminal history.
Do not share screenshots of credentials or commit them to GitHub. Prefer a
dedicated local RPC account when available.

## Run on Linux/macOS

Set `TIDE_RPC_URL`, `TIDE_RPC_USER`, and `TIDE_RPC_PASSWORD`
in your process environment, then:

```sh
python3 contrib/tide-node-monitor/monitor.py
```

Optional: `TIDE_RPC_TIMEOUT` in seconds, greater than 0 and at most 60
(default 8). The fallback port 8754 is **not verified** for Tidecoin;
explicitly configure the correct local RPC port. The project's documented
P2P port (8755) is not necessarily the RPC port.

## Run offline tests (no node or credentials required)

Windows:

```powershell
py -3 -m unittest discover -s contrib/tide-node-monitor -p "test_*.py" -v
```

Linux/macOS:

```sh
python3 -m unittest discover -s contrib/tide-node-monitor -p 'test_*.py' -v
```

## Output

JSON containing chain name, block/header heights, verification progress,
initial download status, peer count, estimated network hashrate and difficulty.
Missing fields may be null depending on node version.

## Safety and limitations

- Only loopback HTTP RPC endpoints with explicit ports are accepted.
- Only three read-only RPC methods are permitted.
- HTTP proxies are disabled for RPC requests.
- No wallet RPC calls, private keys, or transactions are used.
- Errors do not print raw HTTP response bodies, credentials, or URLs.
- Offline tests use mocks; a **real Tidecoin node integration test has not
  yet been performed**.
- Planned improvements: redirect prevention, cookie authentication, periodic
  sampling, stale-tip detection, and a local browser dashboard.

## Browser dashboard (v0.3)

The local dashboard runs on loopback only. In PowerShell, after configuring the
Tidecoin RPC environment variables as described above, start it from the
repository root:

```powershell
py -3 contrib/tide-node-monitor/dashboard.py
```

Open `http://127.0.0.1:8766/` in a browser on **the same computer**.
Use Ctrl+C to stop. Override the browser port with `TIDE_DASHBOARD_PORT`
if needed (1024–65535). The page polls every 15 seconds and displays RPC
connection errors without exposing credentials.

The dashboard requires a running Tidecoin node for live data. The offline
tests use a mocked node and can run without one:

```powershell
py -3 -m unittest discover -s contrib/tide-node-monitor -p "test_*.py" -v
```

The dashboard is a local developer prototype, not a public hosting service.
Do not expose its port through firewall rules, proxies, or tunnels.
The RPC port must be checked against the actual Tidecoin configuration.
