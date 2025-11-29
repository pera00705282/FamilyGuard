"""
Alerting system for the trading platform.
"""
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, field
from enum import Enum, auto
import asyncio
import logging
from datetime import datetime, timedelta
from collections import defaultdict, deque
import json

import aiohttp
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from .metrics import metrics

logger = logging.getLogger(__name__)

class AlertSeverity(Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"

class AlertType(Enum):
    # System alerts
    SYSTEM_STARTUP = "system_startup"
    SYSTEM_SHUTDOWN = "system_shutdown"
    HIGH_CPU_USAGE = "high_cpu_usage"
    HIGH_MEMORY_USAGE = "high_memory_usage"
    DISK_SPACE_LOW = "disk_space_low"
    
    # Trading alerts
    TRADE_EXECUTED = "trade_executed"
    TRADE_FAILED = "trade_failed"
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    STOP_LOSS_TRIGGERED = "stop_loss_triggered"
    TAKE_PROFIT_TRIGGERED = "take_profit_triggered"
    
    # Risk alerts
    DAILY_LOSS_LIMIT = "daily_loss_limit"
    POSITION_RISK_HIGH = "position_risk_high"
    DRAWDOWN_HIGH = "drawdown_high"
    LEVERAGE_HIGH = "leverage_high"
    
    # Exchange alerts
    EXCHANGE_API_ERROR = "exchange_api_error"
    RATE_LIMIT_REACHED = "rate_limit_reached"
    WEBSOCKET_DISCONNECTED = "websocket_disconnected"
    
    # Strategy alerts
    STRATEGY_SIGNAL = "strategy_signal"
    STRATEGY_ERROR = "strategy_error"
    
    # Custom alerts
    CUSTOM = "custom"

@dataclass
class Alert:
    """Represents an alert that can be sent to various notification channels."""
    alert_type: AlertType
    severity: AlertSeverity
    message: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to a dictionary."""
        return {
            "alert_type": self.alert_type.value,
            "severity": self.severity.value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }
    
    def to_json(self) -> str:
        """Convert alert to a JSON string."""
        return json.dumps(self.to_dict(), indent=2)
    
    def __str__(self) -> str:
        return f"[{self.timestamp.isoformat()}] [{self.severity.value}] {self.alert_type.value}: {self.message}"

class NotificationChannel(Enum):
    """Supported notification channels."""
    CONSOLE = "console"
    EMAIL = "email"
    SLACK = "slack"
    TELEGRAM = "telegram"
    DISCORD = "discord"
    PAGERDUTY = "pagerduty"
    
class NotificationConfig:
    """Configuration for a notification channel."""
    
    def __init__(
        self,
        channel: NotificationChannel,
        enabled: bool = True,
        min_severity: AlertSeverity = AlertSeverity.INFO,
        **kwargs
    ):
        """
        Initialize notification configuration.
        
        Args:
            channel: Notification channel
            enabled: Whether the channel is enabled
            min_severity: Minimum severity level to send notifications for
            **kwargs: Channel-specific configuration
        """
        self.channel = channel
        self.enabled = enabled
        self.min_severity = min_severity
        self.config = kwargs
    
    def should_send(self, alert: Alert) -> bool:
        """Check if an alert should be sent through this channel."""
        if not self.enabled:
            return False
            
        # Check minimum severity
        if self.min_severity == AlertSeverity.CRITICAL and alert.severity != AlertSeverity.CRITICAL:
            return False
        elif self.min_severity == AlertSeverity.WARNING and alert.severity == AlertSeverity.INFO:
            return False
            
        return True

class NotificationManager:
    """Manages sending alerts to various notification channels."""
    
    def __init__(self):
        self.channels: Dict[NotificationChannel, NotificationConfig] = {}
        self.alert_history: deque[Alert] = deque(maxlen=1000)  # Keep last 1000 alerts
        self.rate_limits: Dict[NotificationChannel, Dict[str, Any]] = defaultdict(dict)
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def initialize(self) -> None:
        """Initialize the notification manager."""
        self.session = aiohttp.ClientSession()
        logger.info("Notification manager initialized")
    
    async def shutdown(self) -> None:
        """Shutdown the notification manager."""
        if self.session:
            await self.session.close()
        logger.info("Notification manager shut down")
    
    def add_channel(self, config: NotificationConfig) -> None:
        """Add a notification channel."""
        self.channels[config.channel] = config
        logger.info(f"Added notification channel: {config.channel.value}")
    
    def remove_channel(self, channel: NotificationChannel) -> None:
        """Remove a notification channel."""
        if channel in self.channels:
            del self.channels[channel]
            logger.info(f"Removed notification channel: {channel.value}")
    
    async def send_alert(self, alert: Alert) -> None:
        """
        Send an alert through all configured channels.
        
        Args:
            alert: Alert to send
        """
        self.alert_history.append(alert)
        
        # Update metrics
        metrics.metrics["alerts_total"].labels(
            type=alert.alert_type.value,
            severity=alert.severity.value
        ).inc()
        
        # Send to all channels that should receive this alert
        for channel, config in self.channels.items():
            if not config.should_send(alert):
                continue
                
            try:
                if channel == NotificationChannel.CONSOLE:
                    await self._send_console_alert(alert, config)
                elif channel == NotificationChannel.EMAIL:
                    await self._send_email_alert(alert, config)
                elif channel == NotificationChannel.SLACK:
                    await self._send_slack_alert(alert, config)
                elif channel == NotificationChannel.TELEGRAM:
                    await self._send_telegram_alert(alert, config)
                elif channel == NotificationChannel.DISCORD:
                    await self._send_discord_alert(alert, config)
                elif channel == NotificationChannel.PAGERDUTY:
                    await self._send_pagerduty_alert(alert, config)
            except Exception as e:
                logger.error(f"Failed to send {channel.value} alert: {e}")
    
    async def _send_console_alert(self, alert: Alert, config: NotificationConfig) -> None:
        """Send alert to console."""
        if alert.severity == AlertSeverity.CRITICAL:
            # Use stderr for critical errors
            import sys
            print(str(alert), file=sys.stderr)
        else:
            print(str(alert))
    
    async def _send_email_alert(self, alert: Alert, config: NotificationConfig) -> None:
        """Send alert via email."""
        smtp_config = config.config.get("smtp", {})
        if not smtp_config:
            logger.warning("SMTP configuration not provided for email alerts")
            return
            
        msg = MIMEMultipart()
        msg['From'] = smtp_config.get("from_addr")
        msg['To'] = ", ".join(smtp_config.get("to_addrs", []))
        msg['Subject'] = f"[{alert.severity.value}] {alert.alert_type.value}"
        
        # Create email body
        body = f"""
        Alert: {alert.alert_type.value}
        Severity: {alert.severity.value}
        Time: {alert.timestamp.isoformat()}
        
        Message:
        {alert.message}
        
        Metadata:
        {json.dumps(alert.metadata, indent=2)}
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Send email
        with smtplib.SMTP(
            host=smtp_config.get("host"),
            port=smtp_config.get("port", 587)
        ) as server:
            if smtp_config.get("use_tls", True):
                server.starttls()
            
            if smtp_config.get("username") and smtp_config.get("password"):
                server.login(
                    smtp_config["username"],
                    smtp_config["password"]
                )
            
            server.send_message(msg)
    
    async def _send_slack_alert(self, alert: Alert, config: NotificationConfig) -> None:
        """Send alert to Slack."""
        webhook_url = config.config.get("webhook_url")
        if not webhook_url:
            logger.warning("Webhook URL not provided for Slack alerts")
            return
            
        # Apply rate limiting
        if not self._check_rate_limit(NotificationChannel.SLACK, "webhook", limit=10, window=60):
            logger.warning("Slack rate limit reached, skipping alert")
            return
            
        # Format message for Slack
        color = {
            AlertSeverity.INFO: "#36a64f",     # Green
            AlertSeverity.WARNING: "#ffcc00",   # Yellow
            AlertSeverity.CRITICAL: "#ff0000"   # Red
        }.get(alert.severity, "#757575")       # Default gray
        
        payload = {
            "attachments": [{
                "fallback": str(alert),
                "color": color,
                "title": f"{alert.alert_type.value} - {alert.severity.value}",
                "text": alert.message,
                "fields": [
                    {
                        "title": "Timestamp",
                        "value": alert.timestamp.isoformat(),
                        "short": True
                    },
                    {
                        "title": "Severity",
                        "value": alert.severity.value,
                        "short": True
                    }
                ],
                "footer": "Crypto Trading Bot",
                "ts": alert.timestamp.timestamp()
            }]
        }
        
        # Add metadata as fields
        for key, value in alert.metadata.items():
            if isinstance(value, (str, int, float, bool)):
                payload["attachments"][0]["fields"].append({
                    "title": key.replace("_", " ").title(),
                    "value": str(value),
                    "short": len(str(value)) < 20  # Short if value is not too long
                })
        
        # Send request to Slack webhook
        if not self.session:
            self.session = aiohttp.ClientSession()
            
        async with self.session.post(webhook_url, json=payload) as response:
            if response.status != 200:
                logger.error(f"Failed to send Slack alert: {await response.text()}")
    
    async def _send_telegram_alert(self, alert: Alert, config: NotificationConfig) -> None:
        """Send alert to Telegram."""
        bot_token = config.config.get("bot_token")
        chat_id = config.config.get("chat_id")
        
        if not bot_token or not chat_id:
            logger.warning("Bot token or chat ID not provided for Telegram alerts")
            return
            
        # Apply rate limiting
        if not self._check_rate_limit(NotificationChannel.TELEGRAM, "bot", limit=20, window=60):
            logger.warning("Telegram rate limit reached, skipping alert")
            return
            
        # Format message for Telegram
        message = (
            f"*{alert.alert_type.value} - {alert.severity.value}*\n\n"
            f"{alert.message}\n\n"
            f"*Time:* {alert.timestamp.isoformat()}\n"
        )
        
        # Add metadata
        for key, value in alert.metadata.items():
            if isinstance(value, (str, int, float, bool)):
                message += f"*{key.replace('_', ' ').title()}:* {value}\n"
        
        # Send message via Telegram Bot API
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        params = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }
        
        if not self.session:
            self.session = aiohttp.ClientSession()
            
        async with self.session.post(url, json=params) as response:
            if response.status != 200:
                error = await response.text()
                logger.error(f"Failed to send Telegram alert: {error}")
    
    async def _send_discord_alert(self, alert: Alert, config: NotificationConfig) -> None:
        """Send alert to Discord."""
        webhook_url = config.config.get("webhook_url")
        if not webhook_url:
            logger.warning("Webhook URL not provided for Discord alerts")
            return
            
        # Apply rate limiting
        if not self._check_rate_limit(NotificationChannel.DISCORD, "webhook", limit=10, window=60):
            logger.warning("Discord rate limit reached, skipping alert")
            return
            
        # Format message for Discord
        color = {
            AlertSeverity.INFO: 0x36a64f,     # Green
            AlertSeverity.WARNING: 0xffcc00,   # Yellow
            AlertSeverity.CRITICAL: 0xff0000   # Red
        }.get(alert.severity, 0x757575)       # Default gray
        
        # Create embed
        embed = {
            "title": f"{alert.alert_type.value} - {alert.severity.value}",
            "description": alert.message,
            "color": color,
            "timestamp": alert.timestamp.isoformat(),
            "footer": {
                "text": "Crypto Trading Bot"
            },
            "fields": []
        }
        
        # Add metadata as fields
        for key, value in alert.metadata.items():
            if isinstance(value, (str, int, float, bool)):
                embed["fields"].append({
                    "name": key.replace("_", " ").title(),
                    "value": str(value),
                    "inline": True
                })
        
        payload = {
            "embeds": [embed]
        }
        
        # Send request to Discord webhook
        if not self.session:
            self.session = aiohttp.ClientSession()
            
        async with self.session.post(webhook_url, json=payload) as response:
            if response.status != 204:  # Discord returns 204 on success
                error = await response.text()
                logger.error(f"Failed to send Discord alert: {error}")
    
    async def _send_pagerduty_alert(self, alert: Alert, config: NotificationConfig) -> None:
        """Send alert to PagerDuty."""
        routing_key = config.config.get("routing_key")
        if not routing_key:
            logger.warning("Routing key not provided for PagerDuty alerts")
            return
            
        # Only send critical alerts to PagerDuty by default
        if alert.severity != AlertSeverity.CRITICAL:
            return
            
        # Apply rate limiting
        if not self._check_rate_limit(NotificationChannel.PAGERDUTY, "events", limit=5, window=60):
            logger.warning("PagerDuty rate limit reached, skipping alert")
            return
            
        # Create PagerDuty event
        payload = {
            "routing_key": routing_key,
            "event_action": "trigger",
            "dedup_key": f"{alert.alert_type.value}-{alert.timestamp.timestamp()}",
            "payload": {
                "summary": f"{alert.alert_type.value}: {alert.message[:1024]}",
                "source": "crypto-trading-bot",
                "severity": alert.severity.value.lower(),
                "timestamp": alert.timestamp.isoformat(),
                "custom_details": alert.metadata
            }
        }
        
        # Send request to PagerDuty Events API v2
        if not self.session:
            self.session = aiohttp.ClientSession()
            
        async with self.session.post(
            "https://events.pagerduty.com/v2/enqueue",
            json=payload
        ) as response:
            if response.status != 202:
                error = await response.text()
                logger.error(f"Failed to send PagerDuty alert: {error}")
    
    def _check_rate_limit(
        self, 
        channel: NotificationChannel, 
        endpoint: str, 
        limit: int, 
        window: int = 60
    ) -> bool:
        """
        Check if a rate limit has been reached for a channel and endpoint.
        
        Args:
            channel: Notification channel
            endpoint: Endpoint or operation being rate limited
            limit: Maximum number of requests allowed in the time window
            window: Time window in seconds
            
        Returns:
            bool: True if the request is allowed, False if rate limited
        """
        now = datetime.utcnow()
        key = f"{channel.value}:{endpoint}"
        
        # Initialize rate limit tracking for this key
        if key not in self.rate_limits:
            self.rate_limits[key] = {
                "timestamps": deque(),
                "limit": limit,
                "window": window
            }
        
        # Get the rate limit info
        rl = self.rate_limits[key]
        
        # Remove timestamps outside the current window
        while rl["timestamps"] and (now - rl["timestamps"][0]).total_seconds() > window:
            rl["timestamps"].popleft()
        
        # Check if we've exceeded the limit
        if len(rl["timestamps[]"]
