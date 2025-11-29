
import sys
import subprocess
import os
from pathlib import Path

def run_command(command, check=True):
    print(f"Running: {' '.join(command)}")
    result = subprocess.run(
        command,
        text=True,
        capture_output=True
    )
    if check and result.returncode != 0:
        print(f"Error: {result.stderr}")
        return False
    print(result.stdout)
    return True

def main():
    print("Starting dependency installation...")
    
    # Upgrade pip
    print("
=== Upgrading pip ===")
    if not run_command([sys.executable, "-m", "pip", "install", "--upgrade", "pip"]):
        print("Failed to upgrade pip")
        return 1
    
    # Install requirements
    print("
=== Installing requirements ===")
    requirements_files = ["requirements.txt", "test-requirements.txt"]
    
    for req_file in requirements_files:
        if not os.path.exists(req_file):
            print(f"Warning: {req_file} not found, skipping...")
            continue
            
        print(f"
Installing from {req_file}...")
        if not run_command([sys.executable, "-m", "pip", "install", "-r", req_file]):
            print(f"Failed to install from {req_file}")
            return 1
    
    print("
=== Verifying installations ===")
    if not run_command([sys.executable, "-m", "pip", "freeze"]):
        print("Failed to verify installations")
        return 1
    
    print("
All dependencies installed successfully!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
