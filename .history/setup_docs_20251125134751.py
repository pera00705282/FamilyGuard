#!/usr/bin/env python3
"""
Script to set up and build the documentation.
"""
import os
import sys
import subprocess
import webbrowser
from pathlib import Path

def run_command(command, cwd=None):
    """Run a shell command and return its output."""
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            shell=True,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {command}")
        print(f"Error: {e.stderr}")
        sys.exit(1)

def main():
    print("Setting up documentation...")
    
    # Get the project root directory
    project_root = Path(__file__).parent
    docs_dir = project_root / 'docs'
    
    # Install required packages
    print("\nInstalling documentation dependencies...")
    requirements = [
        'sphinx>=4.0.0',
        'sphinx-rtd-theme>=1.0.0',
        'sphinx-autobuild>=2021.3.14',
        'myst-parser>=0.15.0',
        'sphinxcontrib-httpdomain>=1.7.0',
    ]
    
    for pkg in requirements:
        print(f"Installing {pkg}...")
        run_command(f'pip install "{pkg}"')
    
    # Build the documentation
    print("\nBuilding documentation...")
    run_command('sphinx-build -b html . _build/html', cwd=docs_dir)
    
    # Open the documentation in the default web browser
    index_path = docs_dir / '_build' / 'html' / 'index.html'
    if index_path.exists():
        print("\nDocumentation built successfully!")
        print(f"Opening {index_path} in your default browser...")
        webbrowser.open(f'file://{index_path.absolute()}')
    else:
        print("\nError: Documentation build failed. Please check the output for errors.")
        sys.exit(1)

if __name__ == "__main__":
    main()
