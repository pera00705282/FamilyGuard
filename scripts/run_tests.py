#!/usr/bin/env python3
"""Test runner script for the crypto trading application."""
import argparse
import os
import subprocess
import sys
from typing import List, Optional

def run_tests(
    test_type: str = "all",
    workers: int = 4,
    coverage: bool = True,
    verbose: bool = False
) -> int:
    """Run tests with the specified options.
    
    Args:
        test_type: Type of tests to run (unit, integration, performance, all)
        workers: Number of parallel workers
        coverage: Whether to generate coverage reports
        verbose: Whether to show verbose output
        
    Returns:
        int: Exit code
    """
    cmd = ["pytest"]
    
    # Add test type filter
    if test_type == "unit":
        cmd.extend(["tests/unit"])
    elif test_type == "integration":
        cmd.extend(["tests/integration"])
    elif test_type == "performance":
        cmd.extend(["tests/performance", "-m", "performance"])
    elif test_type != "all":
        print(f"Unknown test type: {test_type}", file=sys.stderr)
        return 1
        
    # Add common options
    if coverage:
        cmd.extend(["--cov=src", "--cov-report=term-missing", "--cov-report=xml"])
    if workers > 1:
        cmd.extend(["-n", str(workers)])
    if verbose:
        cmd.append("-v")
        
    # Run the tests
    print(f"Running {test_type} tests with command: {' '.join(cmd)}")
    return subprocess.call(cmd)

def main() -> int:
    """Main entry point for the test runner."""
    parser = argparse.ArgumentParser(description="Run tests for the crypto trading application.")
    parser.add_argument(
        "-t", "--type",
        choices=["all", "unit", "integration", "performance"],
        default="all",
        help="Type of tests to run"
    )
    parser.add_argument(
        "-w", "--workers",
        type=int,
        default=4,
        help="Number of parallel workers"
    )
    parser.add_argument(
        "--no-cov",
        action="store_false",
        dest="coverage",
        help="Disable coverage reporting"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    return run_tests(
        test_type=args.type,
        workers=args.workers,
        coverage=args.coverage,
        verbose=args.verbose
    )

if __name__ == "__main__":
    sys.exit(main())
