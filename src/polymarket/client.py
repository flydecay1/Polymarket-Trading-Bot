"""Polymarket CLOB API client for trading."""
import time
from typing import Dict, Any, List, Optional
from decimal import Decimal
import structlog
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType
from py_clob_client.constants import POLYGON

logger = structlog.get_logger(__name__)


class PolymarketClient:
    """Client for Polymarket CLOB API."""

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        api_passphrase: str,
        private_key: str,
        chain_id: int = 137
    ):
        """Initialize Polymarket client.

        Args:
            api_key: API key
            api_secret: API secret
            api_passphrase: API passphrase
            private_key: Wallet private key
            chain_id: Blockchain chain ID (137 for Polygon)
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_passphrase = api_passphrase
        self.private_key = private_key
        self.chain_id = chain_id

        # Initialize CLOB client
        try:
            self.client = ClobClient(
                host="https://clob.polymarket.com",
                key=api_key,
                secret=api_secret,
                passphrase=api_passphrase,
                chain_id=POLYGON,
                private_key=private_key
            )
            logger.info("polymarket_client_initialized")
        except Exception as e:
            logger.error("failed_to_initialize_client", error=str(e))
            raise

    def get_markets(self, search: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get available markets.

        Args:
            search: Optional search term

        Returns:
            List of markets
        """
        try:
            # Use the gamma API to search markets
            markets = self.client.get_markets()

            if search:
                search_lower = search.lower()
                markets = [
                    m for m in markets
                    if search_lower in m.get('question', '').lower() or
                       search_lower in m.get('description', '').lower()
                ]

            logger.info("fetched_markets", count=len(markets), search=search)
            return markets

        except Exception as e:
            logger.error("failed_to_fetch_markets", error=str(e))
            return []

    def get_esports_markets(self) -> List[Dict[str, Any]]:
        """Get esports-related markets.

        Returns:
            List of esports markets
        """
        # Search for League of Legends and esports markets
        keywords = ["league of legends", "lol", "esports", "lck", "lpl", "lec", "lcs"]

        all_markets = []
        for keyword in keywords:
            markets = self.get_markets(search=keyword)
            all_markets.extend(markets)

        # Deduplicate by market ID
        seen = set()
        unique_markets = []
        for market in all_markets:
            market_id = market.get('condition_id')
            if market_id and market_id not in seen:
                seen.add(market_id)
                unique_markets.append(market)

        logger.info("fetched_esports_markets", count=len(unique_markets))
        return unique_markets

    def get_orderbook(self, token_id: str) -> Dict[str, Any]:
        """Get orderbook for a token.

        Args:
            token_id: Token ID

        Returns:
            Orderbook data with bids and asks
        """
        try:
            orderbook = self.client.get_order_book(token_id)
            return orderbook

        except Exception as e:
            logger.error("failed_to_fetch_orderbook", token_id=token_id, error=str(e))
            return {'bids': [], 'asks': []}

    def get_market_price(self, token_id: str) -> Optional[float]:
        """Get current market price (midpoint).

        Args:
            token_id: Token ID

        Returns:
            Market price or None
        """
        try:
            orderbook = self.get_orderbook(token_id)

            bids = orderbook.get('bids', [])
            asks = orderbook.get('asks', [])

            if not bids or not asks:
                return None

            best_bid = float(bids[0]['price']) if bids else 0
            best_ask = float(asks[0]['price']) if asks else 0

            if best_bid > 0 and best_ask > 0:
                midpoint = (best_bid + best_ask) / 2
                return midpoint

            return None

        except Exception as e:
            logger.error("failed_to_get_market_price", token_id=token_id, error=str(e))
            return None

    def place_order(
        self,
        token_id: str,
        side: str,
        size: float,
        price: float,
        order_type: str = "GTC"
    ) -> Optional[Dict[str, Any]]:
        """Place an order.

        Args:
            token_id: Token ID
            side: "BUY" or "SELL"
            size: Order size
            price: Limit price
            order_type: Order type (GTC, FOK, etc.)

        Returns:
            Order response or None
        """
        try:
            # Create order args
            order_args = OrderArgs(
                token_id=token_id,
                price=price,
                size=size,
                side=side,
                orderType=OrderType.GTC if order_type == "GTC" else OrderType.FOK
            )

            # Place order
            response = self.client.create_order(order_args)

            logger.info(
                "placed_order",
                token_id=token_id,
                side=side,
                size=size,
                price=price,
                order_id=response.get('orderID')
            )

            return response

        except Exception as e:
            logger.error(
                "failed_to_place_order",
                token_id=token_id,
                side=side,
                error=str(e)
            )
            return None

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order.

        Args:
            order_id: Order ID to cancel

        Returns:
            True if successful
        """
        try:
            self.client.cancel_order(order_id)
            logger.info("cancelled_order", order_id=order_id)
            return True

        except Exception as e:
            logger.error("failed_to_cancel_order", order_id=order_id, error=str(e))
            return False

    def get_positions(self) -> List[Dict[str, Any]]:
        """Get current positions.

        Returns:
            List of positions
        """
        try:
            # Get balance for all tokens
            positions = self.client.get_positions()
            logger.info("fetched_positions", count=len(positions))
            return positions

        except Exception as e:
            logger.error("failed_to_fetch_positions", error=str(e))
            return []

    def get_balance(self) -> float:
        """Get USDC balance.

        Returns:
            Balance in USDC
        """
        try:
            balance = self.client.get_balance()
            logger.info("fetched_balance", balance=balance)
            return float(balance)

        except Exception as e:
            logger.error("failed_to_fetch_balance", error=str(e))
            return 0.0

    def get_open_orders(self) -> List[Dict[str, Any]]:
        """Get open orders.

        Returns:
            List of open orders
        """
        try:
            orders = self.client.get_orders()
            logger.info("fetched_open_orders", count=len(orders))
            return orders

        except Exception as e:
            logger.error("failed_to_fetch_open_orders", error=str(e))
            return []
