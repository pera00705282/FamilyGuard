#!/usr/bin/env python3
"""
Interactive API Key Setup Script
Helps you securely configure API keys for the crypto trading tool
"""

import os
import sys
from pathlib import Path
import yaml
from getpass import getpass

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from crypto_trading.utils.config import create_default_config, save_config, load_config

def print_header(text):
    """Print a formatted header"""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60 + "\n")

def print_warning(text):
    """Print a warning message"""
    print(f"\n⚠️  WARNING: {text}\n")

def get_exchange_config(exchange_name):
    """Get API key configuration for an exchange"""
    print_header(f"Configure {exchange_name.upper()}")
    
    print(f"To get your {exchange_name} API keys:")
    if exchange_name == "binance":
        print("  1. Go to https://www.binance.com/en/my/settings/api-management")
        print("  2. Create a new API key")
        print("  3. Enable 'Enable Reading' and 'Enable Spot & Margin Trading'")
        print("  4. IMPORTANT: Restrict to 'Restrict access to trusted IPs only'")
        print("  5. Copy the API Key and Secret Key")
    elif exchange_name == "coinbase":
        print("  1. Go to https://www.coinbase.com/settings/api")
        print("  2. Create a new API key")
        print("  3. Copy the API Key, Secret Key, and Passphrase")
        print("  4. IMPORTANT: Use minimum required permissions")
    elif exchange_name == "kraken":
        print("  1. Go to https://www.kraken.com/u/security/api")
        print("  2. Create a new API key")
        print("  3. Copy the API Key and Secret Key")
        print("  4. IMPORTANT: Use minimum required permissions")
    
    print("\n" + "-" * 60)
    
    use_exchange = input(f"\nDo you want to configure {exchange_name}? (y/n): ").lower().strip()
    if use_exchange != 'y':
        return None
    
    api_key = getpass(f"Enter your {exchange_name} API Key: ").strip()
    if not api_key:
        return None
    
    secret = getpass(f"Enter your {exchange_name} Secret Key: ").strip()
    if not secret:
        return None
    
    passphrase = None
    if exchange_name == "coinbase":
        passphrase = getpass("Enter your Coinbase Passphrase: ").strip()
    
    use_sandbox = input(f"\nUse {exchange_name} sandbox/testnet? (y/n, RECOMMENDED: y): ").lower().strip()
    sandbox = use_sandbox != 'n'
    
    if not sandbox:
        print_warning("You are configuring for LIVE TRADING with REAL MONEY!")
        confirm = input("Type 'YES' to confirm: ").strip()
        if confirm != 'YES':
            print("Keeping sandbox mode enabled for safety.")
            sandbox = True
    
    config = {
        "api_key": api_key,
        "secret": secret,
        "sandbox": sandbox,
        "rate_limit": 100,
        "enable_rate_limit": True
    }
    
    if passphrase:
        config["passphrase"] = passphrase
    
    return config

def main():
    """Main setup function"""
    print_header("Crypto Trading Tool - API Key Setup")
    
    print("This script will help you configure API keys for your exchanges.")
    print("Your keys will be saved to: config/config.yaml")
    print("\n⚠️  IMPORTANT SECURITY REMINDERS:")
    print("   - NEVER share your API keys")
    print("   - NEVER commit config.yaml to version control")
    print("   - ALWAYS use sandbox mode for testing")
    print("   - Use minimum required permissions on exchanges")
    print("   - Enable IP whitelisting when possible")
    
    confirm = input("\nDo you understand and agree? (y/n): ").lower().strip()
    if confirm != 'y':
        print("Setup cancelled.")
        return
    
    # Create config directory if it doesn't exist
    config_dir = Path("config")
    config_dir.mkdir(exist_ok=True)
    
    config_path = config_dir / "config.yaml"
    
    # Load existing config or create new one
    if config_path.exists():
        print(f"\n⚠️  Found existing config at {config_path}")
        overwrite = input("Do you want to update it? (y/n): ").lower().strip()
        if overwrite != 'y':
            print("Setup cancelled.")
            return
        try:
            config = load_config(str(config_path))
            exchanges = config.exchanges
        except:
            exchanges = {}
    else:
        # Create default config structure
        exchanges = {}
    
    # Configure exchanges
    print("\n" + "=" * 60)
    print("  Exchange Configuration")
    print("=" * 60)
    print("\nYou can configure one or more exchanges:")
    print("  1. Binance")
    print("  2. Coinbase")
    print("  3. Kraken")
    print("  4. Skip (use default template)")
    
    choice = input("\nWhich exchange would you like to configure? (1-4): ").strip()
    
    if choice == "1":
        binance_config = get_exchange_config("binance")
        if binance_config:
            exchanges["binance"] = binance_config
    elif choice == "2":
        coinbase_config = get_exchange_config("coinbase")
        if coinbase_config:
            exchanges["coinbase"] = coinbase_config
    elif choice == "3":
        kraken_config = get_exchange_config("kraken")
        if kraken_config:
            exchanges["kraken"] = coinbase_config
    elif choice == "4":
        print("\nUsing default template. You can edit config/config.yaml manually.")
        default_config = create_default_config()
        save_config(default_config, str(config_path))
        print(f"\n✅ Default configuration saved to {config_path}")
        print("   Edit the file manually to add your API keys.")
        return
    else:
        print("Invalid choice. Using default template.")
        default_config = create_default_config()
        save_config(default_config, str(config_path))
        print(f"\n✅ Default configuration saved to {config_path}")
        return
    
    # If we have at least one exchange, create full config
    if exchanges:
        from crypto_trading.utils.config import Config, ExchangeConfig, TradingConfig, MonitoringConfig
        
        # Convert dict to ExchangeConfig objects
        exchange_configs = {}
        for name, cfg in exchanges.items():
            exchange_configs[name] = ExchangeConfig(**cfg)
        
        # Create full config
        full_config = Config(
            exchanges=exchange_configs,
            trading=TradingConfig(),
            monitoring=MonitoringConfig(),
            enable_live_trading=False,
            log_level="INFO"
        )
        
        save_config(full_config, str(config_path))
        print(f"\n✅ Configuration saved to {config_path}")
        print(f"   Configured {len(exchanges)} exchange(s)")
    else:
        print("\n⚠️  No exchanges configured. Using default template.")
        default_config = create_default_config()
        save_config(default_config, str(config_path))
        print(f"✅ Default configuration saved to {config_path}")
    
    print("\n" + "=" * 60)
    print("  Next Steps")
    print("=" * 60)
    print("\n1. Review your configuration:")
    print(f"   - Open: {config_path}")
    print("   - Verify your API keys are correct")
    print("   - Ensure sandbox mode is enabled for testing")
    print("\n2. Validate your configuration:")
    print("   $env:PYTHONPATH='src'")
    print("   python -c \"from src.crypto_trading.utils.config import load_config; load_config('config/config.yaml'); print('✅ Config valid!')\"")
    print("\n3. Test your API keys:")
    print("   (You'll need to implement connection testing)")
    print("\n4. Start the tool:")
    print("   python start_demo.py")
    print("\n⚠️  REMEMBER: Keep your API keys secure and never share them!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSetup cancelled by user.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

