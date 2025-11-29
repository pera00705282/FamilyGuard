import os
import sys
import subprocess
import platform
from pathlib import Path

def run_command(command, cwd=None, check=True):
    """Run a shell command and return the result."""
    print(f"Running: {' '.join(command)}")
    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True
    )
    if check and result.returncode != 0:
        print(f"Command failed with error:\n{result.stderr}")
        return False
    return True

def setup_venv():
    """Set up a Python virtual environment."""
    venv_dir = os.path.abspath(".venv")
    
    # Check if virtual environment already exists
    if os.path.exists(venv_dir):
        print("Virtual environment already exists")
        return True
        
    print("Creating virtual environment...")
    if not run_command([sys.executable, "-m", "venv", venv_dir]):
        return False
    
    # Get the correct pip path based on the OS
    if platform.system() == "Windows":
        pip_path = os.path.join(venv_dir, "Scripts", "pip")
    else:
        pip_path = os.path.join(venv_dir, "bin", "pip")
    
    # Upgrade pip
    print("Upgrading pip...")
    if not run_command([pip_path, "install", "--upgrade", "pip"]):
        return False
    
    return True

def install_dependencies():
    """Install required dependencies."""
    # Get the correct pip path based on the OS
    if platform.system() == "Windows":
        pip_path = os.path.abspath(os.path.join(".venv", "Scripts", "pip"))
    else:
        pip_path = os.path.abspath(os.path.join(".venv", "bin", "pip"))
    
    # Create requirements files
    print("Creating requirements files...")
    with open("requirements.txt", "w") as f:
        f.write("""aiohttp>=3.9.0
asyncio-mqtt>=0.16.1
cryptography>=41.0.0
numpy>=1.24.0
pandas>=1.5.0
prometheus-client>=0.20.0
pydantic>=2.0.0
python-dotenv>=1.0.0
websockets>=12.0
""")

    with open("test-requirements.txt", "w") as f:
        f.write("""pytest>=8.0.0
pytest-asyncio>=0.23.0
pytest-cov>=4.1.0
pytest-mock>=3.12.0
pytest-xdist>=3.5.0
pytest-benchmark>=4.0.0
pytest-timeout>=2.3.1
codecov>=2.1.13
""")

    # Install main dependencies
    print("Installing main dependencies...")
    if not run_command([pip_path, "install", "-r", "requirements.txt"]):
        return False
    
    # Install test dependencies
    print("Installing test dependencies...")
    if not run_command([pip_path, "install", "-r", "test-requirements.txt"]):
        return False
    
    return True

def run_tests():
    """Run the test suite."""
    # Get the correct pytest path based on the OS
    if platform.system() == "Windows":
        pytest_path = os.path.abspath(os.path.join(".venv", "Scripts", "pytest"))
    else:
        pytest_path = os.path.abspath(os.path.join(".venv", "bin", "pytest"))
    
    print("Running tests...")
    return run_command([
        pytest_path,
        "tests/",
        "-v",
        "--cov=src",
        "--cov-report=term-missing",
        "--cov-report=xml"
    ])

def main():
    print("Starting test automation setup...")
    
    # Set up virtual environment
    if not setup_venv():
        print("Failed to set up virtual environment")
        return 1
    
    # Install dependencies
    if not install_dependencies():
        print("Failed to install dependencies")
        return 1
    
    # Run tests
    if not run_tests():
        print("Some tests failed")
        return 1
    
    print("\nTest automation completed successfully!")
    return 0

if __name__ == "__main__":
    sys.exit(main())