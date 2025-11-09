"""
Discord Notification Module
Sends notifications to Discord via webhook
"""

import os
import aiohttp
from typing import Optional, Dict, Any
from datetime import datetime


class DiscordNotifier:
    """Discord notification handler using webhooks"""

    def __init__(self, webhook_url: Optional[str] = None):
        """
        Initialize Discord notifier

        Args:
            webhook_url: Discord webhook URL (if None, notifications are disabled)
        """
        self.webhook_url = webhook_url or os.getenv('DISCORD_WEBHOOK_URL')
        self.enabled = bool(self.webhook_url)

        if not self.enabled:
            print("⚠️  Discord notifications disabled (no webhook URL configured)")

    async def send_notification(self, message: str, color: int = 0x3498db, title: str = None) -> bool:
        """
        Send a notification to Discord

        Args:
            message: Message content
            color: Embed color (hex)
            title: Optional title for the embed

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False

        try:
            embed = {
                "description": message,
                "color": color,
                "timestamp": datetime.utcnow().isoformat()
            }

            if title:
                embed["title"] = title

            payload = {
                "embeds": [embed]
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, json=payload) as response:
                    if response.status == 204:
                        return True
                    else:
                        print(f"⚠️  Discord notification failed: HTTP {response.status}")
                        return False

        except Exception as e:
            print(f"⚠️  Failed to send Discord notification: {e}")
            return False

    async def send_position_opened(self, position_data: Dict[str, Any]) -> bool:
        """
        Send position opened notification

        Args:
            position_data: Position information

        Returns:
            True if successful
        """
        size = position_data.get('size', 0)
        paradex_price = position_data.get('paradex_price', 0)
        lighter_price = position_data.get('lighter_price', 0)

        message = f"""
**🎯 Delta Neutral Position Opened**

**Size:** {size} units
**Paradex (LONG):** ${paradex_price:.4f}
**Lighter (SHORT):** ${lighter_price:.4f}
**Avg Price:** ${(paradex_price + lighter_price) / 2:.4f}

Position opened successfully! ✅
        """

        return await self.send_notification(
            message=message.strip(),
            color=0x2ecc71,  # Green
            title="📈 Position Opened"
        )

    async def send_position_closed(self, trade_data: Dict[str, Any]) -> bool:
        """
        Send position closed notification

        Args:
            trade_data: Trade information including PnL

        Returns:
            True if successful
        """
        size = trade_data.get('size', 0)
        paradex_pnl = trade_data.get('paradex_pnl', 0)
        lighter_pnl = trade_data.get('lighter_pnl', 0)
        total_pnl = trade_data.get('total_pnl', 0)
        entry_time = trade_data.get('entry_time', 'Unknown')
        exit_time = trade_data.get('exit_time', 'Unknown')

        # Determine color based on PnL
        if total_pnl > 0:
            color = 0x2ecc71  # Green (profit)
            emoji = "💰"
        elif total_pnl < 0:
            color = 0xe74c3c  # Red (loss)
            emoji = "📉"
        else:
            color = 0x95a5a6  # Gray (breakeven)
            emoji = "➖"

        message = f"""
**{emoji} Delta Neutral Position Closed**

**Size:** {size} units
**Paradex P&L:** ${paradex_pnl:.2f}
**Lighter P&L:** ${lighter_pnl:.2f}
**Total P&L:** ${total_pnl:.2f}

**Entry:** {entry_time}
**Exit:** {exit_time}

Position closed successfully! ✅
        """

        return await self.send_notification(
            message=message.strip(),
            color=color,
            title=f"{emoji} Position Closed"
        )

    async def send_error(self, error_message: str, context: str = None) -> bool:
        """
        Send error notification

        Args:
            error_message: Error description
            context: Optional context information

        Returns:
            True if successful
        """
        message = f"""
**❌ Error Occurred**

**Error:** {error_message}
"""

        if context:
            message += f"\n**Context:** {context}"

        message += "\n\n⚠️  Please check the bot immediately!"

        return await self.send_notification(
            message=message.strip(),
            color=0xe74c3c,  # Red
            title="🚨 Bot Error"
        )

    async def send_partial_failure(self, exchange: str, size: float) -> bool:
        """
        Send partial failure notification

        Args:
            exchange: Which exchange succeeded
            size: Position size

        Returns:
            True if successful
        """
        message = f"""
**⚠️  Partial Failure Detected**

**Succeeded:** {exchange}
**Size:** {size} units

Automatically closing {exchange} position to maintain safety.

The bot will retry opening a new position shortly.
        """

        return await self.send_notification(
            message=message.strip(),
            color=0xf39c12,  # Orange
            title="⚠️  Partial Failure"
        )

    async def send_loop_started(self, leverage: int, capital_pct: float, max_cycles: int = None) -> bool:
        """
        Send loop started notification

        Args:
            leverage: Leverage multiplier
            capital_pct: Capital percentage
            max_cycles: Maximum cycles (None = unlimited)

        Returns:
            True if successful
        """
        message = f"""
**🔁 Delta Neutral Loop Started**

**Leverage:** {leverage}x
**Capital:** {capital_pct * 100}%
**Max Cycles:** {"∞ (unlimited)" if not max_cycles else max_cycles}

Bot is now running in auto-loop mode! 🚀
        """

        return await self.send_notification(
            message=message.strip(),
            color=0x3498db,  # Blue
            title="🚀 Bot Started"
        )

    async def send_loop_stopped(self, reason: str = "Completed") -> bool:
        """
        Send loop stopped notification

        Args:
            reason: Reason for stopping

        Returns:
            True if successful
        """
        message = f"""
**🛑 Delta Neutral Loop Stopped**

**Reason:** {reason}

Bot has stopped running.
        """

        return await self.send_notification(
            message=message.strip(),
            color=0x95a5a6,  # Gray
            title="🛑 Bot Stopped"
        )
