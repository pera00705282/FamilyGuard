#!/usr/bin/env python3
"""
Automated staging/sandbox runner.

This script executes the staging plan defined in docs/STAGING_PLAN.md by:
1. Running the bootstrap preflight (deps, tests, config) unless skipped
2. Launching both the trading bot and dashboard
3. Polling dashboard health/status endpoints for the specified duration
4. Shutting everything down cleanly and optionally re-encrypting config

Usage:
    python scripts/run_staging_plan.py --duration 600 --with-dashboard
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

import requests

from scripts import bootstrap_tool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run automated staging plan.")
    parser.add_argument(
        "--duration",
        type=int,
        default=600,
        help="How long to run bot/dashboard (seconds).",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=30,
        help="Interval between dashboard status checks (seconds).",
    )
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Skip bootstrap preflight (deps/tests/config).",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip pytest during preflight.",
    )
    parser.add_argument(
        "--auto-config",
        action="store_true",
        help="Ensure config via secure_config_manager before running.",
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
        "--encrypt-config-store",
        action="store_true",
        help="Encrypt config back to api_secrets.enc after run.",
    )
    parser.add_argument(
        "--delete-plain-config",
        action="store_true",
        help="Delete plaintext config after encryption (requires --encrypt-config-store).",
    )
    parser.add_argument(
        "--dashboard-host",
        default="127.0.0.1",
        help="Dashboard host to bind and poll.",
    )
    parser.add_argument(
        "--dashboard-port",
        type=int,
        default=8000,
        help="Dashboard port to bind and poll.",
    )
    parser.add_argument(
        "--status-output",
        default="staging_status.json",
        help="Where to store the final /api/status response.",
    )
    return parser.parse_args()


def wait_for_dashboard(host: str, port: int, timeout: int = 60) -> bool:
    url = f"http://{host}:{port}/health"
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                print(f"[staging] Dashboard healthy at {url}")
                return True
        except requests.RequestException:
            pass
        time.sleep(3)
    print(f"[staging] Dashboard did not become healthy within {timeout}s")
    return False


def fetch_status(host: str, port: int) -> Optional[dict]:
    url = f"http://{host}:{port}/api/status"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except requests.RequestException as exc:
        print(f"[staging] Failed to fetch status: {exc}")
    return None


def main() -> None:
    args = parse_args()

    if args.delete_plain_config and not args.encrypt_config_store:
        raise ValueError("--delete-plain-config requires --encrypt-config-store.")

    if not args.skip_preflight:
        print("[staging] Running bootstrap preflight...")
        bootstrap_tool.run_bootstrap(
            skip_tests=args.skip_tests,
            run_demo_flag=False,
            run_bot_flag=False,
            run_dashboard_flag=False,
            dashboard_host=args.dashboard_host,
            dashboard_port=args.dashboard_port,
            auto_config=args.auto_config,
            config_env=args.config_env,
            key_env=args.key_env,
            encrypt_after=False,
            delete_plain=False,
        )

    bootstrap_tool.ensure_venv()
    python_path, _ = bootstrap_tool.venv_executables()

    dashboard_proc = None
    bot_proc = None

    try:
        dashboard_proc = bootstrap_tool.start_dashboard(
            python_path, args.dashboard_host, args.dashboard_port
        )
        if not wait_for_dashboard(args.dashboard_host, args.dashboard_port):
            raise RuntimeError("Dashboard failed to start; aborting staging run.")

        if args.auto_config and not Path(bootstrap_tool.CONFIG_PATH).exists():
            bootstrap_tool.run_secure_config_manager(
                python_path,
                [
                    "--auto",
                    f"--source-env={args.config_env}",
                    f"--key-env={args.key_env}",
                    f"--config-path={bootstrap_tool.CONFIG_PATH}",
                    f"--enc-path={bootstrap_tool.ENC_PATH}",
                ],
            )

        bot_proc = bootstrap_tool.start_bot_process(python_path)

        start_time = time.time()
        while time.time() - start_time < args.duration:
            status = fetch_status(args.dashboard_host, args.dashboard_port)
            if status:
                print(
                    "[staging] status snapshot:",
                    {
                        "generated_at": status.get("generated_at"),
                        "exchanges": status.get("exchanges"),
                        "symbols": status.get("symbols"),
                        "enable_live_trading": status.get("enable_live_trading"),
                    },
                )
            time.sleep(args.poll_interval)

        print("[staging] Duration reached; stopping processes...")

    except KeyboardInterrupt:
        print("\n[staging] Interrupted by user, shutting down...")
    finally:
        if bot_proc and bot_proc.poll() is None:
            bot_proc.terminate()
            try:
                bot_proc.wait(timeout=10)
            except Exception:
                bot_proc.kill()

        if dashboard_proc and dashboard_proc.poll() is None:
            dashboard_proc.terminate()
            try:
                dashboard_proc.wait(timeout=10)
            except Exception:
                dashboard_proc.kill()

    final_status = fetch_status(args.dashboard_host, args.dashboard_port)
    if final_status:
        output_path = Path(args.status_output)
        output_path.write_text(json.dumps(final_status, indent=2), encoding="utf-8")
        print(f"[staging] Final status saved to {output_path}")

    if args.encrypt_config_store:
        bootstrap_tool.run_secure_config_manager(
            python_path,
            [
                "--encrypt-store",
                f"--key-env={args.key_env}",
                f"--config-path={bootstrap_tool.CONFIG_PATH}",
                f"--enc-path={bootstrap_tool.ENC_PATH}",
            ]
            + (["--delete-plain"] if args.delete_plain_config else []),
        )

    print("[staging] Staging run completed.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI script
        print(f"[staging] ERROR: {exc}")
        sys.exit(1)

