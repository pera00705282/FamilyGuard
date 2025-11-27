#!/usr/bin/env python3
"""
Secure configuration manager for the Crypto Trading tool.

This script automates safe handling of API secrets:

* Ensures that config/config.yaml exists by pulling it from:
    1. Environment variable CRYPTO_TOOL_CONFIG_B64 (base64-encoded YAML)
    2. Encrypted file (config/api_secrets.enc) using a Fernet key from CRYPTO_TOOL_KEY
* Can encrypt the plaintext config back to an encrypted bundle and optionally delete the plaintext version.
* Can generate ready-to-use Fernet keys.

Usage examples:
    python scripts/secure_config_manager.py --auto
    python scripts/secure_config_manager.py --auto --encrypt-store --delete-plain
    python scripts/secure_config_manager.py --generate-key
"""
from __future__ import annotations

import argparse
import base64
import os
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "config.yaml"
DEFAULT_ENC = ROOT / "config" / "api_secrets.enc"


def _read_env(name: str) -> Optional[str]:
    value = os.getenv(name)
    if value:
        value = value.strip()
    return value or None


def ensure_config_present(
    config_path: Path,
    enc_path: Path,
    source_env: str,
    key_env: str,
) -> bool:
    """Ensure config file exists by decoding env or decrypting encrypted store."""
    if config_path.exists():
        print(f"[secure-config] Config already exists at {config_path}")
        return True

    env_payload = _read_env(source_env)
    if env_payload:
        try:
            decoded = base64.b64decode(env_payload.encode("utf-8"))
        except Exception as exc:
            raise ValueError(
                f"Failed to decode base64 from env {source_env}: {exc}"
            ) from exc
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_bytes(decoded)
        print(f"[secure-config] Config created from env var {source_env}")
        return True

    if enc_path.exists():
        key = _read_env(key_env)
        if not key:
            raise RuntimeError(
                f"Encrypted store found at {enc_path}, but key env {key_env} is missing."
            )
        decrypt_to_config(enc_path, config_path, key)
        print(f"[secure-config] Config decrypted from {enc_path}")
        return True

    print(
        "[secure-config] No config found. Provide base64 config via "
        f"{source_env} or place an encrypted bundle at {enc_path}."
    )
    return False


def decrypt_to_config(enc_path: Path, config_path: Path, key: str) -> None:
    """Decrypt encrypted bundle into plaintext config."""
    fernet = Fernet(key.encode("utf-8"))
    encrypted = enc_path.read_bytes()
    decrypted = fernet.decrypt(encrypted)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_bytes(decrypted)


def encrypt_config(
    config_path: Path,
    enc_path: Path,
    key: str,
    delete_plain: bool = False,
) -> None:
    """Encrypt the config file to the encrypted bundle."""
    if not config_path.exists():
        raise FileNotFoundError(f"Cannot encrypt missing config: {config_path}")

    fernet = Fernet(key.encode("utf-8"))
    plaintext = config_path.read_bytes()
    token = fernet.encrypt(plaintext)
    enc_path.parent.mkdir(parents=True, exist_ok=True)
    enc_path.write_bytes(token)
    print(f"[secure-config] Encrypted config stored at {enc_path}")

    if delete_plain:
        config_path.unlink(missing_ok=True)
        print("[secure-config] Plain config deleted after encryption.")


def generate_key() -> str:
    """Generate and return a new Fernet key."""
    key = Fernet.generate_key().decode("utf-8")
    print(
        "[secure-config] Generated new key. Store it securely!\n"
        f"CRYPTO_TOOL_KEY={key}"
    )
    return key


def main() -> None:
    parser = argparse.ArgumentParser(description="Secure config automation utility.")
    parser.add_argument("--auto", action="store_true", help="Ensure config exists (env/decrypt).")
    parser.add_argument("--encrypt-store", action="store_true", help="Encrypt config to .enc store.")
    parser.add_argument(
        "--delete-plain",
        action="store_true",
        help="Delete plaintext config after encryption (requires --encrypt-store).",
    )
    parser.add_argument(
        "--generate-key",
        action="store_true",
        help="Generate a Fernet key and exit.",
    )
    parser.add_argument(
        "--config-path",
        default=str(DEFAULT_CONFIG),
        help="Path to plaintext config.yaml",
    )
    parser.add_argument(
        "--enc-path",
        default=str(DEFAULT_ENC),
        help="Path to encrypted secrets store",
    )
    parser.add_argument(
        "--source-env",
        default="CRYPTO_TOOL_CONFIG_B64",
        help="Env var containing base64 YAML config.",
    )
    parser.add_argument(
        "--key-env",
        default="CRYPTO_TOOL_KEY",
        help="Env var containing Fernet key for encryption/decryption.",
    )
    args = parser.parse_args()

    config_path = Path(args.config_path)
    enc_path = Path(args.enc_path)

    if args.generate_key:
        generate_key()
        return

    performed = False
    if args.auto:
        ensure_config_present(config_path, enc_path, args.source_env, args.key_env)
        performed = True

    if args.encrypt_store:
        key = _read_env(args.key_env)
        if not key:
            raise RuntimeError(
                f"--encrypt-store requested but key env {args.key_env} is missing."
            )
        encrypt_config(config_path, enc_path, key, delete_plain=args.delete_plain)
        performed = True

    if not performed:
        parser.error("No action specified. Use --auto, --encrypt-store, or --generate-key.")


if __name__ == "__main__":
    main()

