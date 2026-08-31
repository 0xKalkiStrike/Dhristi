"""DRISHTI-V — Unified All-in-One Runner with Port Forwarding.

Starts backend (FastAPI :8000), frontend (Vite React :5173), local port-forwarder
(:9000), and public internet port-forwarding tunnel in a single terminal.
Displays all accessible URLs in a clean, unified dashboard with live streaming logs.
"""
from __future__ import annotations

import argparse
import atexit
import os
import re
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"

# ANSI Color codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
WHITE = "\033[97m"

# Enable ANSI colors on Windows console and force unbuffered output
try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass

if os.name == "nt":
    os.system("color")
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass

processes: list[subprocess.Popen] = []
is_shutting_down = False


def get_lan_ip() -> str:
    """Detect local LAN IPv4 address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def get_public_ip() -> str:
    """Fetch public IP (useful for localtunnel password)."""
    try:
        req = urllib.request.Request(
            "https://api.ipify.org",
            headers={"User-Agent": "DRISHTI-V-Runner/1.0"}
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.read().decode("utf-8").strip()
    except Exception:
        return "Unavailable"


def get_python_exe() -> str:
    """Find the best Python executable (virtual environment preferred)."""
    venv_py = BACKEND_DIR / ".venv" / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")
    if venv_py.exists():
        return str(venv_py)
    return sys.executable or "python"


def stream_output(proc: subprocess.Popen, prefix: str, color: str) -> None:
    """Stream process stdout/stderr with a colorized prefix."""
    try:
        for line in iter(proc.stdout.readline, ""):
            if not line:
                break
            line_str = line.rstrip("\r\n")
            if line_str and not is_shutting_down:
                print(f"{color}{BOLD}[{prefix}]{RESET} {line_str}", flush=True)
    except Exception:
        pass


def kill_process_tree(pid: int) -> None:
    """Reliably kill a process and all its children on Windows/Unix."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except Exception:
            try:
                os.kill(pid, signal.SIGTERM)
            except Exception:
                pass


def cleanup() -> None:
    """Terminate all spawned background child processes."""
    global is_shutting_down
    if is_shutting_down:
        return
    is_shutting_down = True
    print(f"\n{YELLOW}{BOLD}[DRISHTI-V] Stopping all services...{RESET}", flush=True)
    for p in processes:
        if p.poll() is None:
            try:
                kill_process_tree(p.pid)
            except Exception:
                pass
    print(f"{GREEN}[DRISHTI-V] All services stopped cleanly. Goodbye!{RESET}", flush=True)


atexit.register(cleanup)


def signal_handler(signum, frame):
    cleanup()
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def wait_for_backend(port: int, timeout: float = 12.0) -> bool:
    """Wait until the backend API server is fully running and answering health checks."""
    start_time = time.time()
    url = f"http://127.0.0.1:{port}/api/system/health"
    while time.time() - start_time < timeout:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "DRISHTI-V-Runner/1.0"})
            with urllib.request.urlopen(req, timeout=1) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.3)
    return False


def start_tunnel_worker(port: int, state: dict, public_ip: str) -> None:
    """Background worker to start tunnel and capture public URL."""
    # 1. Try localtunnel via npx
    try:
        cmd = ["cmd.exe", "/c", "npx", "--yes", "localtunnel", "--port", str(port)] if os.name == "nt" else ["npx", "--yes", "localtunnel", "--port", str(port)]
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=str(ROOT_DIR),
        )
        processes.append(proc)

        start_time = time.time()
        while time.time() - start_time < 15:
            line = proc.stdout.readline()
            if not line:
                if proc.poll() is not None:
                    break
                time.sleep(0.1)
                continue
            
            m = re.search(r"https?://[^\s]+", line)
            if m:
                url = m.group(0).rstrip(".")
                state["url"] = url
                state["type"] = "localtunnel"
                state["ready"] = True
                print(f"\n{YELLOW}{BOLD}[DRISHTI-V] 🌍 PUBLIC TUNNEL URL ESTABLISHED: {url}{RESET}", flush=True)
                if public_ip != "Unavailable":
                    print(f"{DIM}[If prompted for localtunnel password, enter your public IP: {WHITE}{BOLD}{public_ip}{RESET}{DIM}]{RESET}\n", flush=True)
                threading.Thread(target=stream_output, args=(proc, "TUNNEL", YELLOW), daemon=True).start()
                return
    except Exception:
        pass

    # 2. Fallback to SSH Pinggy
    try:
        cmd = ["ssh.exe", "-o", "StrictHostKeyChecking=no", "-o", "ServerAliveInterval=30", "-R", f"0:localhost:{port}", "a.pinggy.io"] if os.name == "nt" else ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ServerAliveInterval=30", "-R", f"0:localhost:{port}", "a.pinggy.io"]
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=str(ROOT_DIR),
        )
        processes.append(proc)

        start_time = time.time()
        while time.time() - start_time < 10:
            line = proc.stdout.readline()
            if not line:
                if proc.poll() is not None:
                    break
                time.sleep(0.1)
                continue
            m = re.search(r"https://[a-zA-Z0-9\-]+\.a\.pinggy\.link", line) or re.search(r"https://[a-zA-Z0-9\-]+\.free\.pinggy\.link", line)
            if m:
                url = m.group(0)
                state["url"] = url
                state["type"] = "pinggy"
                state["ready"] = True
                print(f"\n{YELLOW}{BOLD}[DRISHTI-V] 🌍 PUBLIC TUNNEL URL ESTABLISHED: {url}{RESET}\n", flush=True)
                threading.Thread(target=stream_output, args=(proc, "TUNNEL", YELLOW), daemon=True).start()
                return
    except Exception:
        pass

    state["ready"] = True


def print_banner(backend_port: int, frontend_port: int, forwarder_port: int, lan_ip: str, public_ip: str, tunnel_url: str | None, tunnel_type: str | None, has_forwarder: bool) -> None:
    print("\n" + "=" * 78, flush=True)
    print(f"{BOLD}{WHITE}                   DRISHTI-V ALL ACCESS URLS & SERVICES{RESET}", flush=True)
    print("=" * 78, flush=True)
    print(f" {BOLD}1. WEB DASHBOARD (Command Center UI):{RESET}", flush=True)
    print(f"    • Local Access:        {GREEN}{BOLD}http://localhost:{frontend_port}{RESET}", flush=True)
    print(f"    • Network / LAN Access:{GREEN}{BOLD}http://{lan_ip}:{frontend_port}{RESET}  (For mobile & other laptops on Wi-Fi)", flush=True)
    
    if tunnel_url:
        print(f"    • {YELLOW}{BOLD}PUBLIC TUNNEL URL:   {YELLOW}{BOLD}{tunnel_url}{RESET}  (Worldwide Internet Access)", flush=True)
        if tunnel_type == "localtunnel" and public_ip != "Unavailable":
            print(f"      {DIM}[If prompted by localtunnel for Tunnel Password, enter: {WHITE}{BOLD}{public_ip}{RESET}{DIM}]{RESET}", flush=True)
    else:
        print(f"    • {YELLOW}Public Tunnel URL:     Connecting in background... (will appear above when ready){RESET}", flush=True)
        
    print("\n" + f" {BOLD}2. BACKEND API & WEBSOCKETS:{RESET}", flush=True)
    print(f"    • API Base URL:        {CYAN}http://localhost:{backend_port}{RESET}  (LAN: http://{lan_ip}:{backend_port})", flush=True)
    print(f"    • Swagger Docs (API):  {CYAN}{BOLD}http://localhost:{backend_port}/docs{RESET}", flush=True)
    print(f"    • ReDoc Docs:          {CYAN}http://localhost:{backend_port}/redoc{RESET}", flush=True)

    if has_forwarder:
        print("\n" + f" {BOLD}3. LOCAL PORT FORWARDER / REVERSE PROXY:{RESET}", flush=True)
        print(f"    • Forwarder Entrypoint:{MAGENTA}http://localhost:{forwarder_port}{RESET}  (LAN: http://{lan_ip}:{forwarder_port})", flush=True)

    print("=" * 78, flush=True)
    print(f"{WHITE}{BOLD} System is ONLINE & READY. Press {RED}Ctrl+C{WHITE} in this terminal to stop.{RESET}", flush=True)
    print("=" * 78 + "\n", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="DRISHTI-V Unified Runner with Port Forwarding")
    parser.add_argument("--backend-port", type=int, default=8000, help="Backend port (default: 8000)")
    parser.add_argument("--frontend-port", type=int, default=5173, help="Frontend port (default: 5173)")
    parser.add_argument("--forwarder-port", type=int, default=9000, help="Local port forwarder port (default: 9000)")
    parser.add_argument("--no-tunnel", action="store_true", help="Disable public port forwarding tunnel")
    parser.add_argument("--no-forwarder", action="store_true", help="Disable local port forwarder (port 9000)")
    args = parser.parse_args()

    python_exe = get_python_exe()
    lan_ip = get_lan_ip()
    public_ip = get_public_ip()

    print(f"{CYAN}{BOLD}", flush=True)
    print("  ____  ____  ___ ____  _   _ _____ ___      __     __", flush=True)
    print(" |  _ \\|  _ \\|_ _/ ___|| | | |_   _|_ _|     \\ \\   / /", flush=True)
    print(" | | | | |_) || |\\___ \\| |_| | | |  | |  ____ \\ \\ / / ", flush=True)
    print(" | |_| |  _ < | | ___) |  _  | | |  | | |____| \\ V /  ", flush=True)
    print(" |____/|_| \\_\\___|____/|_| |_| |_| |___|        \\_/   ", flush=True)
    print(f" Dynamic Road Intelligence & Surveillance Through Intelligent Vision{RESET}\n", flush=True)

    # Step 1: Initialize Database
    init_db_script = ROOT_DIR / "scripts" / "setup" / "init_db.py"
    if init_db_script.exists():
        print(f"{DIM}[DRISHTI-V] Checking database schema...{RESET}", flush=True)
        try:
            subprocess.run([python_exe, str(init_db_script)], cwd=str(ROOT_DIR), check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except Exception:
            pass

    # Step 2: Start Backend API
    print(f"{CYAN}[DRISHTI-V] Starting Backend API on port {args.backend_port}...{RESET}", flush=True)
    backend_env = os.environ.copy()
    backend_env["PYTHONPATH"] = str(BACKEND_DIR)
    backend_env["OPENCV_FFMPEG_THREAD_COUNT"] = "1"
    backend_env["PYTHONIOENCODING"] = "utf-8"
    backend_env["PYTHONUNBUFFERED"] = "1"
    backend_proc = subprocess.Popen(
        [python_exe, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", str(args.backend_port)],
        cwd=str(BACKEND_DIR),
        env=backend_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    processes.append(backend_proc)
    threading.Thread(target=stream_output, args=(backend_proc, "BACKEND", CYAN), daemon=True).start()

    # Step 3: Wait for Backend to be fully ready before launching proxy/frontend
    print(f"{DIM}[DRISHTI-V] Waiting for Backend API startup...{RESET}", flush=True)
    if not wait_for_backend(args.backend_port, timeout=12.0):
        print(f"{YELLOW}[DRISHTI-V] Warning: Backend took longer than expected to answer health check.{RESET}", flush=True)
    else:
        print(f"{GREEN}[DRISHTI-V] Backend API is online and responding.{RESET}", flush=True)

    # Step 4: Start Frontend UI
    print(f"{GREEN}[DRISHTI-V] Starting Frontend UI on port {args.frontend_port}...{RESET}", flush=True)
    npm_cmd = ["cmd.exe", "/c", "npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", str(args.frontend_port)] if os.name == "nt" else ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", str(args.frontend_port)]
    frontend_proc = subprocess.Popen(
        npm_cmd,
        cwd=str(FRONTEND_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    processes.append(frontend_proc)
    threading.Thread(target=stream_output, args=(frontend_proc, "FRONTEND", GREEN), daemon=True).start()

    # Step 5: Start Local Port Forwarder
    has_forwarder = False
    if not args.no_forwarder:
        port_forward_script = ROOT_DIR / "scripts" / "port_forward.py"
        if port_forward_script.exists():
            has_forwarder = True
            print(f"{MAGENTA}[DRISHTI-V] Starting Local Port Forwarder on port {args.forwarder_port}...{RESET}", flush=True)
            forwarder_proc = subprocess.Popen(
                [python_exe, str(port_forward_script), "--listen-host", "0.0.0.0", "--listen-port", str(args.forwarder_port), "--target", f"http://127.0.0.1:{args.backend_port}"],
                cwd=str(ROOT_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            processes.append(forwarder_proc)
            threading.Thread(target=stream_output, args=(forwarder_proc, "FORWARDER", MAGENTA), daemon=True).start()

    # Step 6: Start Public Port Forwarding Tunnel
    tunnel_state = {"url": None, "type": None, "ready": False}
    if not args.no_tunnel:
        print(f"{YELLOW}[DRISHTI-V] Establishing Public Port Forwarding Tunnel for port {args.frontend_port}...{RESET}", flush=True)
        tunnel_thread = threading.Thread(target=start_tunnel_worker, args=(args.frontend_port, tunnel_state, public_ip), daemon=True)
        tunnel_thread.start()

        # Wait up to 5 seconds for tunnel to resolve before initial banner
        start_wait = time.time()
        while time.time() - start_wait < 5:
            if tunnel_state.get("ready"):
                break
            time.sleep(0.2)

    # Print Clean Master Summary Banner with all URLs
    print_banner(
        backend_port=args.backend_port,
        frontend_port=args.frontend_port,
        forwarder_port=args.forwarder_port,
        lan_ip=lan_ip,
        public_ip=public_ip,
        tunnel_url=tunnel_state.get("url"),
        tunnel_type=tunnel_state.get("type"),
        has_forwarder=has_forwarder,
    )

    # Keep main thread alive monitoring child processes
    try:
        while True:
            time.sleep(1)
            if backend_proc.poll() is not None:
                print(f"{RED}[DRISHTI-V] Backend process exited with code {backend_proc.poll()}.{RESET}", flush=True)
                break
            if frontend_proc.poll() is not None:
                print(f"{RED}[DRISHTI-V] Frontend process exited with code {frontend_proc.poll()}.{RESET}", flush=True)
                break
    except KeyboardInterrupt:
        pass
    finally:
        cleanup()


if __name__ == "__main__":
    main()
