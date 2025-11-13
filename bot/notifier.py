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

    def __init__(self, webhook_url: Optional[str] = None, user_id: Optional[str] = None):
        """
        Initialize Discord notifier

        Args:
            webhook_url: Discord webhook URL (if None, notifications are disabled)
            user_id: Discord user ID to mention in alerts (e.g., '0xnec0' or numeric ID)
        """
        self.webhook_url = webhook_url or os.getenv('DISCORD_WEBHOOK_URL')
        self.user_id = user_id or os.getenv('DISCORD_USER_ID', '0xnec0')
        self.enabled = bool(self.webhook_url and self.webhook_url != 'https://discord.com/api/webhooks/...')
        self.balance_alert_threshold = float(os.getenv('BALANCE_ALERT_THRESHOLD', '50'))
        self.balance_alert_sent = False  # Track if alert was already sent

        if not self.enabled:
            print("⚠️  Discord notifications disabled (no webhook URL configured)")

    async def send_notification(self, message: str, color: int = 0x3498db, title: str = None, mention: bool = False) -> bool:
        """
        Send a notification to Discord

        Args:
            message: Message content
            color: Embed color (hex)
            title: Optional title for the embed
            mention: Whether to mention the user (default: False)

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False

        try:
            # Format mention
            mention_text = ""
            if mention and self.user_id:
                # Check if user_id is numeric (actual Discord ID) or username
                if self.user_id.isdigit():
                    mention_text = f"<@{self.user_id}> "
                else:
                    mention_text = f"@{self.user_id} "

            embed = {
                "description": message,
                "color": color,
                "timestamp": datetime.utcnow().isoformat()
            }

            if title:
                embed["title"] = title

            payload = {
                "content": mention_text if mention_text else None,
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
        paradex_balance = position_data.get('paradex_balance', 0)
        lighter_balance = position_data.get('lighter_balance', 0)

        message = f"""
**🎯 Delta Neutral Position Opened**

**Size:** {size} units
**Paradex (LONG):** ${paradex_price:.4f}
**Lighter (SHORT):** ${lighter_price:.4f}
**Avg Price:** ${(paradex_price + lighter_price) / 2:.4f}

**💰 Current Balances:**
**Paradex:** ${paradex_balance:.2f}
**Lighter:** ${lighter_balance:.2f}
**Total:** ${paradex_balance + lighter_balance:.2f}

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
        paradex_balance = trade_data.get('paradex_balance', 0)
        lighter_balance = trade_data.get('lighter_balance', 0)

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

**💰 Current Balances:**
**Paradex:** ${paradex_balance:.2f}
**Lighter:** ${lighter_balance:.2f}
**Total:** ${paradex_balance + lighter_balance:.2f}

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
            title="🚨 Bot Error",
            mention=True  # Mention user for error alerts
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
            title="⚠️  Partial Failure",
            mention=True  # Mention user for partial failures
        )

    async def send_loop_started(self, leverage: int = None, capital_pct: float = None, usd_amount: float = None, max_cycles: int = None) -> bool:
        """
        Send loop started notification

        Args:
            leverage: Leverage multiplier (optional)
            capital_pct: Capital percentage (optional)
            usd_amount: Fixed USD amount per position (optional)
            max_cycles: Maximum cycles (None = unlimited)

        Returns:
            True if successful
        """
        if usd_amount:
            # Fixed USD amount mode
            message = f"""
**🔁 Delta Neutral Loop Started**

**Position Size:** ${usd_amount:.2f} (fixed)
**Max Cycles:** {"∞ (unlimited)" if not max_cycles else max_cycles}

Bot is now running in auto-loop mode! 🚀
            """
        else:
            # Percentage/leverage mode
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

    async def check_and_alert_low_balance(self, lighter_balance: float, paradex_balance: float) -> bool:
        """
        Check balances and send alert if EITHER exchange is below threshold

        Args:
            lighter_balance: Lighter balance in USD
            paradex_balance: Paradex balance in USD

        Returns:
            True if alert was sent, False otherwise
        """
        lighter_low = lighter_balance < self.balance_alert_threshold
        paradex_low = paradex_balance < self.balance_alert_threshold
        total_balance = lighter_balance + paradex_balance

        # Check if either exchange is below threshold
        if lighter_low or paradex_low:
            # Only send alert once until both balances go above threshold again
            if not self.balance_alert_sent:
                # Determine which exchanges are low
                low_exchanges = []
                if lighter_low:
                    low_exchanges.append(f"🔴 **Lighter**: ${lighter_balance:.2f} < ${self.balance_alert_threshold:.2f}")
                if paradex_low:
                    low_exchanges.append(f"🔴 **Paradex**: ${paradex_balance:.2f} < ${self.balance_alert_threshold:.2f}")

                low_exchanges_text = "\n".join(low_exchanges)

                message = f"""
**⚠️  残高アラート: 資金が不足しています！**

**閾値:** ${self.balance_alert_threshold:.2f}

{low_exchanges_text}

**現在の残高:**
**Lighter:** ${lighter_balance:.2f} {"❌" if lighter_low else "✅"}
**Paradex:** ${paradex_balance:.2f} {"❌" if paradex_low else "✅"}
**合計:** ${total_balance:.2f}

⚠️  資金を追加してください！
                """

                result = await self.send_notification(
                    message=message.strip(),
                    color=0xe74c3c,  # Red
                    title="🚨 残高不足アラート",
                    mention=True  # Mention user for critical alerts
                )

                if result:
                    self.balance_alert_sent = True
                    exchanges_str = " & ".join(["Lighter" if lighter_low else "", "Paradex" if paradex_low else ""]).strip(" & ")
                    print(f"🚨 残高アラート送信: {exchanges_str} が閾値${self.balance_alert_threshold:.2f}を下回っています")

                return result
        else:
            # Reset alert flag when BOTH balances go back above threshold
            if self.balance_alert_sent:
                print(f"✅ 両取引所の残高が閾値を上回りました: Lighter ${lighter_balance:.2f}, Paradex ${paradex_balance:.2f}")
                self.balance_alert_sent = False

        return False
