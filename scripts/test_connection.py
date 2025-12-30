#!/usr/bin/env python3
"""Test API connections and configuration."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import Config, setup_logger
from src.data_ingestion import PandaScoreClient
from src.polymarket import PolymarketClient


def test_pandascore(config: Config) -> bool:
    """Test PandaScore API connection."""
    print("\n🔍 Testing PandaScore API...")

    if not config.pandascore_api_key:
        print("   ❌ PANDASCORE_API_KEY not set")
        return False

    try:
        client = PandaScoreClient(api_key=config.pandascore_api_key)
        matches = client.get_live_matches()

        print(f"   ✅ Connected! Found {len(matches)} live matches")
        return True

    except Exception as e:
        print(f"   ❌ Connection failed: {e}")
        return False


def test_polymarket(config: Config) -> bool:
    """Test Polymarket API connection."""
    print("\n🔍 Testing Polymarket API...")

    if not config.polymarket_api_key or not config.wallet_private_key:
        print("   ❌ Polymarket credentials not set")
        return False

    try:
        client = PolymarketClient(
            api_key=config.polymarket_api_key,
            api_secret=config.polymarket_secret,
            api_passphrase=config.polymarket_passphrase,
            private_key=config.wallet_private_key,
            chain_id=config.chain_id
        )

        markets = client.get_esports_markets()
        balance = client.get_balance()

        print(f"   ✅ Connected! Found {len(markets)} esports markets")
        print(f"   💰 Balance: ${balance:.2f} USDC")
        return True

    except Exception as e:
        print(f"   ❌ Connection failed: {e}")
        return False


def main():
    """Test all connections."""
    config = Config()
    logger = setup_logger("connection_test", level="INFO", console=False)

    print("="*60)
    print("🔧 Testing API Connections")
    print("="*60)

    pandascore_ok = test_pandascore(config)
    polymarket_ok = test_polymarket(config)

    print("\n" + "="*60)
    print("📊 Test Results")
    print("="*60)
    print(f"PandaScore API: {'✅ OK' if pandascore_ok else '❌ FAILED'}")
    print(f"Polymarket API: {'✅ OK' if polymarket_ok else '❌ FAILED'}")
    print("="*60)

    if pandascore_ok and polymarket_ok:
        print("\n✅ All tests passed! Ready to run the bot.")
        return 0
    else:
        print("\n❌ Some tests failed. Please check your configuration.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
