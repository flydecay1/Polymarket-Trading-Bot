"""Alert and notification system."""
import asyncio
from typing import Optional
import structlog

logger = structlog.get_logger(__name__)


class TelegramAlerter:
    """Send alerts via Telegram."""

    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        """Initialize Telegram alerter.

        Args:
            bot_token: Telegram bot token
            chat_id: Telegram chat ID
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = bool(bot_token and chat_id)

        if self.enabled:
            logger.info("telegram_alerts_enabled")
        else:
            logger.info("telegram_alerts_disabled")

    async def send_message(self, message: str, parse_mode: str = "HTML") -> bool:
        """Send a message via Telegram.

        Args:
            message: Message text
            parse_mode: Parse mode (HTML or Markdown)

        Returns:
            True if successful
        """
        if not self.enabled:
            logger.debug("telegram_disabled_skipping_message")
            return False

        try:
            import aiohttp

            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": parse_mode
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data) as response:
                    if response.status == 200:
                        logger.debug("telegram_message_sent")
                        return True
                    else:
                        logger.error("telegram_send_failed", status=response.status)
                        return False

        except Exception as e:
            logger.error("telegram_error", error=str(e))
            return False

    async def send_trade_alert(
        self,
        side: str,
        size: float,
        price: float,
        edge: float,
        match: str
    ) -> None:
        """Send trade execution alert.

        Args:
            side: BUY or SELL
            size: Position size
            price: Entry price
            edge: Calculated edge
            match: Match description
        """
        emoji = "🟢" if side == "BUY" else "🔴"
        message = f"""
{emoji} <b>Trade Executed</b>

<b>Match:</b> {match}
<b>Side:</b> {side}
<b>Size:</b> ${size:.2f}
<b>Price:</b> {price:.3f}
<b>Edge:</b> {edge:+.2%}
"""
        await self.send_message(message)

    async def send_pnl_alert(self, pnl: float, total_pnl: float, win_rate: float) -> None:
        """Send P&L update alert.

        Args:
            pnl: Trade P&L
            total_pnl: Total P&L
            win_rate: Overall win rate
        """
        emoji = "✅" if pnl > 0 else "❌"
        message = f"""
{emoji} <b>Position Closed</b>

<b>P&L:</b> ${pnl:+.2f}
<b>Total P&L:</b> ${total_pnl:+.2f}
<b>Win Rate:</b> {win_rate:.1%}
"""
        await self.send_message(message)

    async def send_error_alert(self, error: str) -> None:
        """Send error alert.

        Args:
            error: Error message
        """
        message = f"""
⚠️ <b>Error Alert</b>

{error}
"""
        await self.send_message(message)

    async def send_startup_alert(self) -> None:
        """Send bot startup notification."""
        message = """
🚀 <b>Bot Started</b>

Polymarket LoL Arbitrage Bot is now running.
Monitoring for opportunities...
"""
        await self.send_message(message)

    async def send_shutdown_alert(self, total_pnl: float, total_trades: int) -> None:
        """Send bot shutdown notification.

        Args:
            total_pnl: Total P&L
            total_trades: Total trades executed
        """
        message = f"""
🛑 <b>Bot Stopped</b>

Session Summary:
<b>Total Trades:</b> {total_trades}
<b>Total P&L:</b> ${total_pnl:+.2f}
"""
        await self.send_message(message)


class DiscordAlerter:
    """Send alerts via Discord webhook."""

    def __init__(self, webhook_url: Optional[str] = None):
        """Initialize Discord alerter.

        Args:
            webhook_url: Discord webhook URL
        """
        self.webhook_url = webhook_url
        self.enabled = bool(webhook_url)

        if self.enabled:
            logger.info("discord_alerts_enabled")
        else:
            logger.info("discord_alerts_disabled")

    async def send_message(self, message: str, color: int = 0x00FF00) -> bool:
        """Send a message via Discord webhook.

        Args:
            message: Message text
            color: Embed color (hex)

        Returns:
            True if successful
        """
        if not self.enabled:
            logger.debug("discord_disabled_skipping_message")
            return False

        try:
            import aiohttp

            data = {
                "embeds": [{
                    "description": message,
                    "color": color
                }]
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, json=data) as response:
                    if response.status == 204:
                        logger.debug("discord_message_sent")
                        return True
                    else:
                        logger.error("discord_send_failed", status=response.status)
                        return False

        except Exception as e:
            logger.error("discord_error", error=str(e))
            return False

    async def send_trade_alert(self, side: str, size: float, edge: float, match: str) -> None:
        """Send trade alert."""
        color = 0x00FF00 if side == "BUY" else 0xFF0000
        message = f"**Trade: {side}** ${size:.2f} @ {edge:+.2%} edge\n{match}"
        await self.send_message(message, color)


class MultiAlerter:
    """Send alerts to multiple channels."""

    def __init__(
        self,
        telegram_token: Optional[str] = None,
        telegram_chat_id: Optional[str] = None,
        discord_webhook: Optional[str] = None
    ):
        """Initialize multi-channel alerter.

        Args:
            telegram_token: Telegram bot token
            telegram_chat_id: Telegram chat ID
            discord_webhook: Discord webhook URL
        """
        self.telegram = TelegramAlerter(telegram_token, telegram_chat_id)
        self.discord = DiscordAlerter(discord_webhook)

    async def send_trade_alert(self, **kwargs) -> None:
        """Send trade alert to all enabled channels."""
        await asyncio.gather(
            self.telegram.send_trade_alert(**kwargs),
            self.discord.send_trade_alert(**kwargs),
            return_exceptions=True
        )

    async def send_pnl_alert(self, **kwargs) -> None:
        """Send P&L alert to all enabled channels."""
        await self.telegram.send_pnl_alert(**kwargs)

    async def send_error_alert(self, error: str) -> None:
        """Send error alert to all enabled channels."""
        await self.telegram.send_error_alert(error)

    async def send_startup_alert(self) -> None:
        """Send startup alert to all enabled channels."""
        await self.telegram.send_startup_alert()

    async def send_shutdown_alert(self, total_pnl: float, total_trades: int) -> None:
        """Send shutdown alert to all enabled channels."""
        await self.telegram.send_shutdown_alert(total_pnl, total_trades)
