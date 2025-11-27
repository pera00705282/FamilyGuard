#!/usr/bin/env python3
"""
Single-entry bootstrapper for the Crypto Trading tool.

Usage:
    python scripts/bootstrap_tool.py [--skip-tests] [--run-demo]

What it does:
1. Creates (or reuses) a local virtual environment in .venv
2. Upgrades pip inside the venv
3. Installs/updates all dependencies from requirements.txt
4. Optionally runs migrations for API keys if api/API_final.txt is present
5. Runs the test-suite (unless --skip-tests)
6. Optionally starts the interactive demo (--run-demo)
"""
from __future__ import annotations

import argparse
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Tuple

ROOT = Path(__file__).resolve().parents[1]
VENV_DIR = ROOT / ".venv"
CONFIG_PATH = ROOT / "config" / "config.yaml"
ENC_PATH = ROOT / "config" / "api_secrets.enc"


def run(cmd: list[str], env: dict | None = None, cwd: Path | None = None) -> None:
    """Execute a command and stream its output."""
    print(f"\n[bootstrap] $ {' '.join(cmd)}")
    subprocess.run(cmd, check=True, env=env, cwd=cwd or ROOT)


def ensure_venv() -> None:
    """Create the virtual environment if it does not exist."""
    if VENV_DIR.exists():
        print("[bootstrap] Using existing virtual environment (.venv)")
        return

    print("[bootstrap] Creating virtual environment in .venv")
    run([sys.executable, "-m", "venv", str(VENV_DIR)])


def venv_executables() -> Tuple[Path, Path]:
    """Return paths to python and pip inside the venv."""
    if platform.system() == "Windows":
        python_path = VENV_DIR / "Scripts" / "python.exe"
        pip_path = VENV_DIR / "Scripts" / "pip.exe"
    else:
        python_path = VENV_DIR / "bin" / "python"
        pip_path = VENV_DIR / "bin" / "pip"

    if not python_path.exists():
        raise FileNotFoundError(f"Python executable not found in venv at {python_path}")

    return python_path, pip_path


def install_dependencies(pip_path: Path) -> None:
    """Install project dependencies inside the venv."""
    print("[bootstrap] Upgrading pip")
    run([str(pip_path), "install", "--upgrade", "pip"])

    print("[bootstrap] Installing project dependencies")
    run([str(pip_path), "install", "-r", str(ROOT / "requirements.txt")])


def migrate_api_keys(python_path: Path) -> None:
    """If API_final.txt exists, migrate and delete it securely."""
    api_file = ROOT / "api" / "API_final.txt"
    if api_file.exists():
        print("[bootstrap] Migrating API keys from api/API_final.txt")
        run([str(python_path), str(ROOT / "scripts" / "secure_migrate_api_keys.py")])


def run_secure_config_manager(
    python_path: Path,
    action_args: list[str],
) -> None:
    """Invoke secure_config_manager with the provided arguments."""
    script = ROOT / "scripts" / "secure_config_manager.py"
    run([str(python_path), str(script), *action_args])


def run_tests(python_path: Path) -> None:
    """Execute pytest with proper PYTHONPATH."""
    print("[bootstrap] Running test-suite")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    run([str(python_path), "-m", "pytest", "--maxfail=1", "--disable-warnings", "-v"], env=env)


def run_demo(python_path: Path) -> None:
    """Start the interactive demo script."""
    print("[bootstrap] Starting demo (press Ctrl+C to exit)")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    run([str(python_path), str(ROOT / "start_demo.py")], env=env)


def run_bot(python_path: Path, config_path: Path = CONFIG_PATH) -> None:
    """Launch the actual trading bot via the click CLI."""
    print("[bootstrap] Launching trading bot")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    run(
        [
            str(python_path),
            "-m",
            "crypto_trading.core.main",
            "run",
            "--config",
            str(config_path),
        ],
        env=env,
    )


def start_bot_process(python_path: Path, config_path: Path = CONFIG_PATH) -> subprocess.Popen:
    """Launch the trading bot as a background process."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    cmd = [
        str(python_path),
        "-m",
        "crypto_trading.core.main",
        "run",
        "--config",
        str(config_path),
    ]
    print(f"[bootstrap] Starting bot process with config {config_path}")
    return subprocess.Popen(cmd, env=env, cwd=ROOT)


def start_dashboard(python_path: Path, host: str, port: int) -> subprocess.Popen:
    """Start the FastAPI dashboard via uvicorn in a background process."""
    print(f"[bootstrap] Launching dashboard at http://{host}:{port}")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    cmd = [
        str(python_path),
        "-m",
        "uvicorn",
        "dashboard.server:app",
        "--host",
        host,
        "--port",
        str(port),
    ]
    process = subprocess.Popen(cmd, env=env, cwd=ROOT)
    return process


def run_bootstrap(
    skip_tests: bool,
    run_demo_flag: bool,
    run_bot_flag: bool,
    run_dashboard_flag: bool,
    dashboard_host: str,
    dashboard_port: int,
    auto_config: bool,
    config_env: str,
    key_env: str,
    encrypt_after: bool,
    delete_plain: bool,
) -> None:
    """Executes the full bootstrap flow."""
    if delete_plain and not encrypt_after:
        raise ValueError("--delete-plain-config requires --encrypt-config-store.")

    os.chdir(ROOT)
    ensure_venv()
    python_path, pip_path = venv_executables()
    install_dependencies(pip_path)
    migrate_api_keys(python_path)

    if auto_config:
        print("[bootstrap] Ensuring secure config is available")
        action = [
            "--auto",
            f"--source-env={config_env}",
            f"--key-env={key_env}",
            f"--config-path={CONFIG_PATH}",
            f"--enc-path={ENC_PATH}",
        ]
        run_secure_config_manager(python_path, action)

    dashboard_proc: subprocess.Popen | None = None
    bot_proc: subprocess.Popen | None = None

    try:
        if not skip_tests:
            run_tests(python_path)

        if run_dashboard_flag:
            dashboard_proc = start_dashboard(python_path, dashboard_host, dashboard_port)

        if run_bot_flag:
            bot_proc = start_bot_process(python_path)
            bot_proc.wait()
        elif run_demo_flag:
            run_demo(python_path)
        elif run_dashboard_flag:
            dashboard_proc.wait()

        if encrypt_after:
            print("[bootstrap] Encrypting config for rest storage")
            action = [
                "--encrypt-store",
                f"--key-env={key_env}",
                f"--config-path={CONFIG_PATH}",
                f"--enc-path={ENC_PATH}",
            ]
            if delete_plain:
                action.append("--delete-plain")
            run_secure_config_manager(python_path, action)
    finally:
        if bot_proc and bot_proc.poll() is None:
            print("[bootstrap] Stopping bot process")
            bot_proc.terminate()
            try:
                bot_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                bot_proc.kill()

        if dashboard_proc and dashboard_proc.poll() is None:
            print("[bootstrap] Stopping dashboard process")
            dashboard_proc.terminate()
            try:
                dashboard_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                dashboard_proc.kill()

    print("\n[bootstrap] All steps completed successfully.")
    print("[bootstrap] Activate the venv with '.\\.venv\\Scripts\\Activate.ps1' (Windows) or 'source .venv/bin/activate' (Unix)")
    print("[bootstrap] Then run your entrypoints (bot, dashboard, demos, etc.).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap and run the Crypto Trading tool.")
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip running pytest after installing dependencies.",
    )
    parser.add_argument(
        "--run-demo",
        action="store_true",
        help="Launch start_demo.py after installation/tests.",
    )
    parser.add_argument(
        "--run-bot",
        action="store_true",
        help="Launch the production trading bot via crypto_trading.core.main run.",
    )
    parser.add_argument(
        "--run-dashboard",
        action="store_true",
        help="Launch the FastAPI dashboard (uvicorn) after setup.",
    )
    parser.add_argument(
        "--dashboard-host",
        default="0.0.0.0",
        help="Dashboard host interface (default: 0.0.0.0).",
    )
    parser.add_argument(
        "--dashboard-port",
        type=int,
        default=8000,
        help="Dashboard port (default: 8000).",
    )
    parser.add_argument(
        "--auto-config",
        action="store_true",
        help="Auto-manage config via secure_config_manager (--auto).",
    )
    parser.add_argument(
        "--encrypt-config-store",
        action="store_true",
        help="Encrypt config back to api_secrets.enc when done.",
    )
    parser.add_argument(
        "--delete-plain-config",
        action="store_true",
        help="Delete plaintext config after encryption (use with --encrypt-config-store).",
    )
    parser.add_argument(
        "--config-env",
        default="CRYPTO_TOOL_CONFIG_B64",
        help="Env var containing base64 YAML for auto config.",
    )
    parser.add_argument(
        "--key-env",
        default="CRYPTO_TOOL_KEY",
        help="Env var containing Fernet key for encryption/decryption.",
    )
    args = parser.parse_args()

    try:
        run_bootstrap(
            skip_tests=args.skip_tests,
            run_demo_flag=args.run_demo,
            run_bot_flag=args.run_bot,
            run_dashboard_flag=args.run_dashboard,
            dashboard_host=args.dashboard_host,
            dashboard_port=args.dashboard_port,
            auto_config=args.auto_config,
            config_env=args.config_env,
            key_env=args.key_env,
            encrypt_after=args.encrypt_config_store,
            delete_plain=args.delete_plain_config,
        )
    except subprocess.CalledProcessError as exc:
        print(f"\n[bootstrap] ERROR: Command failed with exit code {exc.returncode}")
        sys.exit(exc.returncode)
    except Exception as exc:
        print(f"\n[bootstrap] ERROR: {exc}")
        raise


if __name__ == "__main__":
    main()

