#!/usr/bin/env python3
"""
ZeroHack php2shell - Target Checker

A fast, standalone script to fingerprint PHP versions and check for 
CVE-2026-109618 / CVE-2026-109619 vulnerability. 
Supports single targets or mass scanning from a file.

Usage:
    python3 check_target.py -u http://target.com
    python3 check_target.py -f targets.txt -t 20
"""

import argparse
import re
import sys
import concurrent.futures
from urllib.parse import urlparse

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except ImportError:
    print("[-] Missing dependency: requests. Install it with: pip install requests")
    sys.exit(1)

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Patched versions
PATCHED_VERSIONS = {
    (8, 2): (8, 2, 35),
    (8, 3): (8, 3, 36),
    (8, 4): (8, 4, 27),
    (8, 5): (8, 5, 12),
}

def is_vulnerable(version_str):
    """Compare the detected version against patched thresholds."""
    try:
        v = tuple(map(int, version_str.split('.')))
        if len(v) < 3:
            return True # Suspicious/incomplete version
        
        major, minor = v[0], v[1]
        
        # Anything below PHP 8 is EOL and vulnerable
        if major < 8:
            return True
            
        # Check against specific branch patches
        if (major, minor) in PATCHED_VERSIONS:
            if v < PATCHED_VERSIONS[(major, minor)]:
                return True
            else:
                return False
                
        # Future versions (8.6+) are assumed patched if they exist
        return False
    except Exception:
        return True # Fail safe: if we can't parse it, assume vulnerable

def check_target(url):
    """Fingerprint a single target."""
    # Ensure URL has a scheme
    if not url.startswith('http://') and not url.startswith('https://'):
        url = 'http://' + url

    result = {
        "url": url,
        "version": None,
        "vulnerable": False,
        "status": "ERROR",
        "error": None
    }

    # Setup session with retries
    session = requests.Session()
    retries = Retry(total=2, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
    session.mount('http://', HTTPAdapter(max_retries=retries))
    session.mount('https://', HTTPAdapter(max_retries=retries))

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        resp = session.get(url, headers=headers, timeout=10, verify=False)

        # 1. Check X-Powered-By Header
        powered_by = resp.headers.get("X-Powered-By", "")
        match = re.search(r"PHP/(\d+\.\d+\.\d+)", powered_by)
        
        # 2. Check Body (for error pages, phpinfo leaks)
        if not match:
            body_match = re.search(r"PHP\s*Version\s*(\d+\.\d+\.\d+)", resp.text)
            if body_match:
                match = body_match

        if match:
            version = match.group(1)
            result["version"] = version
            result["vulnerable"] = is_vulnerable(version)
            result["status"] = "VULNERABLE" if result["vulnerable"] else "PATCHED"
        else:
            result["status"] = "UNKNOWN_VERSION"

    except requests.exceptions.RequestException as e:
        result["error"] = str(e)

    return result

def main():
    parser = argparse.ArgumentParser(description="ZeroHack php2shell Target Checker")
    parser.add_argument("-u", "--url", help="Single target URL to check")
    parser.add_argument("-f", "--file", help="File containing list of URLs")
    parser.add_argument("-t", "--threads", type=int, default=10, help="Number of concurrent threads (default: 10)")
    args = parser.parse_args()

    targets = []
    if args.url:
        targets.append(args.url)
    elif args.file:
        try:
            with open(args.file, 'r') as f:
                targets = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        except FileNotFoundError:
            print(f"[-] File not found: {args.file}")
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)

    print(f"[*] Loaded {len(targets)} targets. Starting scan with {args.threads} threads...\n")
    print(f"{'URL':<40} | {'PHP Version':<12} | {'STATUS'}")
    print("-" * 70)

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.threads) as executor:
        future_to_url = {executor.submit(check_target, url): url for url in targets}
        
        for future in concurrent.futures.as_completed(future_to_url):
            res = future.result()
            url_display = res['url'][:38] + '..' if len(res['url']) > 40 else res['url']
            ver_display = res['version'] if res['version'] else "UNKNOWN"
            
            # Colorize output based on status
            if res['status'] == "VULNERABLE":
                status_display = f"\033[91m[!] {res['status']}\033[0m"
            elif res['status'] == "PATCHED":
                status_display = f"\033[92m[+] {res['status']}\033[0m"
            elif res['error']:
                status_display = f"\033[90m[-] {res['error'][:20]}\033[0m"
            else:
                status_display = f"\033[93m[?] {res['status']}\033[0m"

            print(f"{url_display:<40} | {ver_display:<12} | {status_display}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[-] Scan aborted.")
        sys.exit(0)
