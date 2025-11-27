#!/usr/bin/env python3
"""
Full deployment orchestrator for the Crypto Trading tool.

This script chains all automation steps:
1. Bootstraps environment + dependencies
2. Auto-configures secrets (env/encrypted)
3. Runs tests (unless --skip-tests)
4. Starts either the demo or the live bot
5. Optionally re-encrypts and removes plaintext config afterwards

Usage:
    python scripts/deploy_tool.py --mode bot --encrypt-at-rest --delete-plain
"""
from __future__ import annotations

import argparse
import sys

from scripts import bootstrap_tool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Complete deployment script.")
    parser.add_argument(
        "--mode",
        choices=["demo", "bot", "dashboard", "none"],
        default="demo",
        help="What to run after setup: demo (default), bot, dashboard-only, or none.",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip running pytest as part of deployment.",
    )
    parser.add_argument(
        "--no-auto-config",
        action="store_true",
        help="Disable secure auto-config; assumes config/config.yaml already exists.",
    )
    parser.add_argument(
        "--encrypt-at-rest",
        action="store_true",
        help="After execution, encrypt config back to api_secrets.enc.",
    )
    parser.add_argument(
        "--delete-plain",
        action="store_true",
        help="Delete plaintext config after encryption (requires --encrypt-at-rest).",
    )
    parser.add_argument(
        "--with-dashboard",
        action="store_true",
        help="Always launch the dashboard alongside the selected mode.",
    )
    parser.add_argument(
        "--config-env",
        default="CRYPTO_TOOL_CONFIG_B64",
        help="Env var containing base64 YAML payload for auto config.",
    )
    parser.add_argument(
        "--key-env",
        default="CRYPTO_TOOL_KEY",
        help="Env var containing Fernet key for encryption/decryption.",
    )
    parser.add_argument(
        "--dashboard-host",
        default="0.0.0.0",
        help="Dashboard host interface.",
    )
    parser.add_argument(
        "--dashboard-port",
        type=int,
        default=8000,
        help="Dashboard port.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    run_demo = args.mode == "demo"
    run_bot = args.mode == "bot"
    run_dashboard = args.mode == "dashboard" or args.with_dashboard

    if args.mode == "dashboard":
        run_demo = False
        run_bot = False
    auto_config = not args.no_auto_config

    try:
        bootstrap_tool.run_bootstrap(
            skip_tests=args.skip_tests,
            run_demo_flag=run_demo,
            run_bot_flag=run_bot,
            run_dashboard_flag=run_dashboard,
            dashboard_host=args.dashboard_host,
            dashboard_port=args.dashboard_port,
            auto_config=auto_config,
            config_env=args.config_env,
            key_env=args.key_env,
            encrypt_after=args.encrypt_at_rest,
            delete_plain=args.delete_plain,
        )
    except Exception as exc:
        print(f"[deploy] ERROR: {exc}")
        raise


if __name__ == "__main__":
    main()

