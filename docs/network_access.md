# Access from other devices (LAN / port forwarding)

Run DRISHTI-V so **phones and laptops on the same Wi-Fi** can open it.

## One command
```powershell
scripts\setup\run_network.ps1                 # backend + frontend on 0.0.0.0
scripts\setup\run_network.ps1 -WithForwarder  # also run the :9000 port-forwarder
```
It detects your LAN IP, tries to open the Windows Firewall ports, starts the backend
(`0.0.0.0:8000`) and frontend (`0.0.0.0:5173`), and prints the URL to open on other devices,
e.g. `http://192.168.1.4:5173`.

`GET /api/system/network` returns the same info (and the Camera Management page shows an
"Open on other devices" banner):
```json
{ "primary_ip": "192.168.1.4",
  "urls": { "frontend": "http://192.168.1.4:5173", "backend": "http://192.168.1.4:8000",
            "port_forwarder": "http://192.168.1.4:9000" } }
```

## How it works
- **Frontend** — Vite binds `0.0.0.0` (`server.host: true`) and proxies `/api` and `/ws` to the
  backend, so another device just opens `http://<LAN-IP>:5173` — API and the live WebSocket are
  proxied through the same origin (no CORS issues).
- **Backend** — run with `--host 0.0.0.0`. CORS additionally allows any private-LAN origin
  (`192.168.*`, `10.*`, `172.16–31.*`) via `CORS_ALLOW_LAN=true`, so a device hitting the
  backend or forwarder **directly** is also permitted.
- **Port-forwarder** — [`scripts/port_forward.py`](../scripts/port_forward.py) binds `0.0.0.0:9000`
  and relays HTTP + WebSocket to the backend, giving a single forwarded port you can expose via a
  router/NAT rule. See [port_forwarding.md](port_forwarding.md).

## Firewall
Inbound connections may be blocked by Windows Firewall. `run_network.ps1` tries to add rules; if
it can't (not admin), run once as administrator:
```powershell
scripts\setup\open_firewall.ps1     # opens TCP 8000, 5173, 9000
```

## Pointing the frontend at a specific backend
By default the frontend talks to the backend through the Vite proxy. To target a specific host
(e.g. the forwarder), set at build/dev time:
```
VITE_API_BASE=http://192.168.1.4:9000
VITE_WS_BASE=ws://192.168.1.4:9000
```

## Beyond the LAN
For access outside the local network, forward the chosen port on your router to this machine, or
put a hardened reverse proxy (nginx/Caddy) with TLS + auth in front. Do not expose the raw dev
servers to the public internet.
