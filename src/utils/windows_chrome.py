"""從 WSL 接上 Windows Chrome，不要用 Linux 內建的瀏覽器。"""

from __future__ import annotations

import os
import socket
import subprocess
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
from urllib.request import urlopen

DEFAULT_PORT = 9222
WINDOWS_CHROME = Path("/mnt/c/Program Files/Google/Chrome/Application/chrome.exe")
WINDOWS_CHROME_X86 = Path("/mnt/c/Program Files (x86)/Google/Chrome/Application/chrome.exe")


def is_wsl() -> bool:
    if os.environ.get("WSL_DISTRO_NAME"):
        return True
    try:
        return "microsoft" in Path("/proc/version").read_text(encoding="utf-8").lower()
    except OSError:
        return False


def windows_chrome_path() -> Optional[Path]:
    for candidate in (WINDOWS_CHROME, WINDOWS_CHROME_X86):
        if candidate.exists():
            return candidate
    local = Path.home() / "AppData/Local/Google/Chrome/Application/chrome.exe"
    if local.exists():
        return local
    return None


def wsl_path_to_windows(path: Path) -> str:
    resolved = path.expanduser().resolve()
    text = str(resolved)
    if text.startswith("/mnt/") and len(text) > 6 and text[5].isalpha() and text[6] == "/":
        drive = text[5].upper()
        rest = text[7:].replace("/", "\\")
        return f"{drive}:\\{rest}"
    return text


def windows_host_ip() -> Optional[str]:
    try:
        resolv = Path("/etc/resolv.conf").read_text(encoding="utf-8")
    except OSError:
        return None
    for line in resolv.splitlines():
        if line.startswith("nameserver"):
            parts = line.split()
            if len(parts) >= 2:
                return parts[1]
    return None


def debugger_candidates(port: int = DEFAULT_PORT) -> list[str]:
    hosts = ["127.0.0.1"]
    win_ip = windows_host_ip()
    if win_ip and win_ip not in hosts:
        hosts.append(win_ip)
    return [f"{host}:{port}" for host in hosts]


def probe_debugger(address: str, timeout: float = 1.0) -> bool:
    parsed = address if "://" in address else f"http://{address}"
    host = urlparse(parsed).hostname or "127.0.0.1"
    port = urlparse(parsed).port or DEFAULT_PORT
    try:
        with socket.create_connection((host, port), timeout=timeout):
            pass
        with urlopen(f"http://{host}:{port}/json/version", timeout=timeout) as resp:
            return resp.status == 200
    except OSError:
        return False


def find_open_debugger(port: int = DEFAULT_PORT) -> Optional[str]:
    for address in debugger_candidates(port):
        if probe_debugger(address):
            return address
    return None


def resolve_debugger_address(configured: str = "", headless: bool = False) -> str:
    """設定有填就用設定；否則若 9222 已有 open-chrome.bat，就接上、不要再開視窗。"""
    configured = (configured or "").strip()
    if configured:
        return configured
    if headless:
        return ""
    return find_open_debugger() or ""


def _ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def launch_windows_chrome(
    user_data_dir: str = ".chrome-profile",
    port: int = DEFAULT_PORT,
    start_url: str = "https://ticketplus.com.tw/",
) -> str:
    """用 Windows chrome.exe 開遠端除錯埠，回傳可 attach 的 address。"""
    chrome = windows_chrome_path()
    if not chrome:
        raise FileNotFoundError("找不到 Windows Chrome（C:\\Program Files\\Google\\Chrome\\...）")

    existing = find_open_debugger(port)
    if existing:
        return existing

    profile = Path(user_data_dir)
    if not profile.is_absolute():
        profile = Path.cwd() / profile
    profile.mkdir(parents=True, exist_ok=True)
    win_profile = wsl_path_to_windows(profile)
    win_chrome = wsl_path_to_windows(chrome)

    ps = (
        "Start-Process -FilePath "
        + _ps_quote(win_chrome)
        + " -ArgumentList "
        + ",".join(
            _ps_quote(a)
            for a in (
                f"--remote-debugging-port={port}",
                f"--user-data-dir={win_profile}",
                "--no-first-run",
                "--no-default-browser-check",
                start_url,
            )
        )
    )
    subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", ps],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    deadline = time.time() + 15
    while time.time() < deadline:
        found = find_open_debugger(port)
        if found:
            return found
        time.sleep(0.4)
    raise TimeoutError(
        f"Windows Chrome 已啟動，但從 WSL 連不到 {port} 埠。"
        "請在 Windows 關掉其他 Chrome 後重試，或把 WSL 設成 mirrored 網路。"
    )
