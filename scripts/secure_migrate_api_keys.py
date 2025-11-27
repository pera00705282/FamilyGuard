#!/usr/bin/env python3
"""
SECURE API KEY MIGRATION SCRIPT
Moves all valid keys from api/API_final.txt into config/config.yaml
Deletes the source .txt file after migration (Windows safe)
Verifies yaml is gitignored
No secrets ever printed/logged.
"""
import os
import sys
import yaml
from pathlib import Path
import re
import shutil

CONFIG_PATH = Path("config/config.yaml")
API_KEYS_PATH = Path("api/API_final.txt")
GITIGNORE_PATH = Path(".gitignore")
AUDIT_LOG = Path("migration_audit.log")

EXCHANGES = [
    "ascendex",
    "binance",
    "bitfinex",
    "bitget",
    "bitrue",
    "bitstamp",
    "bybit",
    "coinbase",
    "gate.io",
    "kraken",
    "kucoin",
    "poloniex",
]

KW_MAP = [
    ("api_key", ["api key", "api_key", "api name", "api key name"]),
    ("secret", ["secret", "private key"]),
    ("passphrase", ["passphrase", "trading password", "passkey"]),
]

def secure_print(msg):
    print(f"[secure-migrate] {msg}")

def scrub(s):
    if not s: return ""
    return s[:4] + "..." + s[-4:] if len(s) > 10 else "***"

def parse_api_final(fp):
    with open(fp, encoding="utf-8") as f:
        lines = [l.strip() for l in f]
    entries = {}
    curr_ex = None
    for line in lines:
        m = re.match(r"^\d+\. ([A-Z0-9.]+) ", line)
        if m:
            curr_ex = m.group(1).lower().replace(".io", "io").replace(".", "")
            entries[curr_ex] = {}
            continue
        if curr_ex:
            for field, kws in KW_MAP:
                for kw in kws:
                    pat = rf"^{kw}[:]?(.+)$"
                    v = re.search(pat, line, re.I)
                    if v:
                        val = v.group(1).strip()
                        if val:
                            entries[curr_ex][field] = val
    # remove empty entries
    entries = {k: v for k, v in entries.items() if v and any(vv for vv in v.values())}
    return entries

def load_yaml_config(fp):
    if not fp.exists():
        return {"exchanges": {}}
    with open(fp, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {"exchanges": {}}

def write_yaml_config(cfg, fp):
    os.makedirs(fp.parent, exist_ok=True)
    with open(fp, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, default_flow_style=False, indent=2)

def ensure_gitignore(fp):
    if not fp.exists():
        return False
    with open(fp, "r", encoding="utf-8") as f:
        ignored = [l.strip() for l in f if l.strip() and not l.startswith("#")]
    return "config/config.yaml" in ignored

def safe_delete(fp):
    try:
        os.remove(fp)
        return True
    except Exception:
        try:
            # Windows sometimes keeps handles. Move then delete
            trash = fp.parent / (fp.name + ".deleted")
            shutil.move(fp, trash)
            os.remove(trash)
            return True
        except Exception as e:
            secure_print(f"Error deleting {fp}: {e}")
            return False

def log_audit(msg):
    try:
        with open(AUDIT_LOG, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass

def main():
    secure_print("Starting API key secure migration...")
    if not API_KEYS_PATH.exists():
        secure_print(f"No {API_KEYS_PATH}, nothing to do!")
        return
    secrets = parse_api_final(API_KEYS_PATH)
    if not secrets:
        secure_print("No valid secrets detected in API_final.txt - aborting.")
        return
    config = load_yaml_config(CONFIG_PATH)
    exchanges = config.get("exchanges", {})
    changed = False
    for ex, vals in secrets.items():
        if not vals: continue
        old = exchanges.get(ex, {})
        merged = {**old, **vals, "sandbox": True, "rate_limit": 100, "enable_rate_limit": True}
        exchanges[ex] = merged
        secure_print(f"Exchange {ex} updated. Keys: " + ", ".join(f"{k}=[hidden]" for k in vals.keys()))
        log_audit(f"Migrated {ex} keys: " + ", ".join(f"{k}={scrub(v)}" for k, v in vals.items()))
        changed = True
    if changed:
        config["exchanges"] = exchanges
        write_yaml_config(config, CONFIG_PATH)
        secure_print(f"Wrote {CONFIG_PATH} with migrated secrets.")
    else:
        secure_print("Nothing to update in YAML config.")
    # Safe delete
    if changed and safe_delete(API_KEYS_PATH):
        secure_print("Original API_final.txt securely deleted.")
        log_audit("Deleted API_final.txt after successful migration.")
    # Ensure .gitignore state
    if not ensure_gitignore(GITIGNORE_PATH):
        secure_print("\n[!] WARNING: config/config.yaml is NOT in .gitignore! ADD IT NOW!")
    else:
        secure_print(".gitignore status: config/config.yaml is protected.")
    secure_print("Migration completed. Review your config/config.yaml and keep it private!")

if __name__ == "__main__":
    main()
