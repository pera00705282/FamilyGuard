#!/usr/bin/env python3
"""
Quick Start Script for Crypto Trading Tool
Run this to start the demo mode
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Set PYTHONPATH for subprocesses
os.environ['PYTHONPATH'] = 'src'

if __name__ == "__main__":
    print("🚀 Starting Crypto Trading Tool Demo...")
    print("=" * 50)
    
    # Import and run demo
    import asyncio
    from examples.demo import main
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n✅ Demo stopped by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

