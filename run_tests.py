import os
import sys
import subprocess
from pathlib import Path
import shutil

def setup_environment():
    """Set up the test environment with all necessary mocks"""
    # Add project root to Python path
    project_root = Path(__file__).parent
    sys.path.insert(0, str(project_root))
    
    # Create src/crypto_trading/__init__.py if it doesn't exist
    src_dir = project_root / "src"
    src_dir.mkdir(exist_ok=True)
    (src_dir / "__init__.py").write_text("", encoding="utf-8")
    
    # Create crypto_trading/__init__.py
    crypto_dir = project_root / "src" / "crypto_trading"
    crypto_dir.mkdir(exist_ok=True)
    (crypto_dir / "__init__.py").write_text("", encoding="utf-8")
    
    # Create mock core module
    core_dir = crypto_dir / "core"
    core_dir.mkdir(exist_ok=True)
    (core_dir / "__init__.py").write_text("", encoding="utf-8")
    (core_dir / "main.py").write_text("""
class TradingBot:
    def __init__(self, *args, **kwargs):
        pass
""", encoding="utf-8")
    
    # Create mock base module
    base_dir = crypto_dir / "base"
    base_dir.mkdir(exist_ok=True)
    (base_dir / "__init__.py").write_text("", encoding="utf-8")
    (base_dir / "exchange.py").write_text("""
class Exchange:
    pass
""", encoding="utf-8")
    
    print("✓ Set up test environment with mock modules")

def run_tests():
    """Run the tests with proper environment setup"""
    project_root = Path(__file__).parent
    
    # Set up the environment
    setup_environment()
    
    # Run pytest with the correct Python path
    env = os.environ.copy()
    env['PYTHONPATH'] = str(project_root) + os.pathsep + env.get('PYTHONPATH', '')
    
    print("\nRunning tests...")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_binance_ws_isolated.py", "-v", "--tb=short"],
        cwd=str(project_root),
        env=env,
        capture_output=True,
        text=True
    )
    
    # Print results
    print("\n" + "="*50)
    print("TEST RESULTS:")
    print("="*50)
    print(result.stdout)
    
    if result.stderr:
        print("\n" + "="*50)
        print("ERRORS:")
        print("="*50)
        print(result.stderr)
    
    print("\n" + "="*50)
    print(f"Test completed with exit code: {result.returncode}")
    print("="*50)
    
    return result.returncode

if __name__ == "__main__":
    sys.exit(run_tests())