#!/usr/bin/env python3
"""
Extract build-specific offsets from a libphp.so binary.
Usage: python3 extract_offsets.py /path/to/libphp.so
"""

import json
import subprocess
import sys
import os

def extract_offsets(binary_path):
    if not os.path.exists(binary_path):
        print(f"[-] Error: File not found: {binary_path}")
        sys.exit(1)

    offsets = {}
    
    # 1. Try 'nm -D' to find dynamic symbols
    try:
        out = subprocess.check_output(
            ["nm", "-D", binary_path], text=True, stderr=subprocess.DEVNULL
        )
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[2] in ("zif_system", "zval_ptr_dtor"):
                offsets[parts[2]] = int(parts[0], 16)
    except Exception:
        pass

    # 2. Fallback: use objdump to find zif_system
    if "zif_system" not in offsets:
        try:
            out = subprocess.check_output(
                ["objdump", "-d", binary_path], text=True, stderr=subprocess.DEVNULL
            )
            for line in out.splitlines():
                if "<zif_system>:" in line:
                    addr = int(line.split()[0], 16)
                    offsets["zif_system"] = addr
                    break
        except Exception:
            pass

    # 3. Set default fallback offsets if not found
    offsets.setdefault("htdata", 0x18)
    offsets.setdefault("zval_dtor", 0x4c1a0)
    
    return offsets

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: python3 {sys.argv[0]} <libphp.so>")
        sys.exit(1)
    
    print(f"[*] Extracting offsets from: {sys.argv[1]}")
    offsets = extract_offsets(sys.argv[1])
    
    print("[+] Extracted Offsets:")
    print(json.dumps(offsets, indent=4))
    
    # Optionally save to file
    save_choice = input("\n[?] Save to offsets.json? (y/n): ").strip().lower()
    if save_choice == 'y':
        with open("offsets.json", "w") as f:
            json.dump(offsets, f, indent=4)
        print("[+] Saved to offsets.json")
