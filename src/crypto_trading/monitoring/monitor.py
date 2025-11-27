"""
Monitoring and Alerting Module
==============================

Real-time monitoring, alerting i reporting sistem.
"""

import asyncio
import logging
from typing import Dict, List, Any, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import aiohttp
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.layout import Layout
import plotly.graph_objects as go
from plotly.subplots import make_subplots

logger = logging.getLogger(__name__)
console = Console()


class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Alert:
    """Alert struktura"""

    level: AlertLevel
    title: str
    message: str
    timestamp: datetime
    source: str
    metadata: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level.value,
            "title": self.title,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "metadata": self.metadata or {},
        }


class MetricsCollector:
    """Collector za metrike"""

    def __init__(self):
        self.metrics: Dict[str, List[Dict[str, Any]]] = {}
        self.start_time = datetime.now()

    def record_metric(self, name: str, value: float, tags: Dict[str, str] = None):
        """Beleži metriku"""
        if name not in self.metrics:
            self.metrics[name] = []

        metric = {"timestamp": datetime.now(), "value": value, "tags": tags or {}}

        self.metrics[name].append(metric)

        # Čuva samo poslednje 1000 merenja
        if len(self.metrics[name]) > 1000:
            self.metrics[name] = self.metrics[name][-1000:]

    def get_metric_history(self, name: str, hours: int = 24) -> List[Dict[str, Any]]:
        """Vraća istoriju metrike"""
        if name not in self.metrics:
            return []

        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [m for m in self.metrics[name] if m["timestamp"] > cutoff_time]

    def get_metric_stats(self, name: str, hours: int = 24) -> Dict[str, float]:
        """Vraća statistike za metriku"""
        history = self.get_metric_history(name, hours)
        if not history:
            return {}

        values = [m["value"] for m in history]
        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "current": values[-1] if values else 0,
        }


class AlertManager:
    """Manager za alerting"""

    def __init__(self):
        self.alerts: List[Alert] = []
        self.handlers: List[Callable[[Alert], None]] = []
        self.alert_rules: List[Dict[str, Any]] = []

    def add_handler(self, handler: Callable[[Alert], None]):
        """Dodaje alert handler"""
        self.handlers.append(handler)

    def add_alert_rule(
        self, metric_name: str, condition: str, threshold: float, level: AlertLevel, message: str
    ):
        """Dodaje alert rule"""
        rule = {
            "metric_name": metric_name,
            "condition": condition,  # 'gt', 'lt', 'eq'
            "threshold": threshold,
            "level": level,
            "message": message,
            "last_triggered": None,
        }
        self.alert_rules.append(rule)

    async def send_alert(self, alert: Alert):
        """Šalje alert"""
        self.alerts.append(alert)

        # Čuva samo poslednje 1000 alertova
        if len(self.alerts) > 1000:
            self.alerts = self.alerts[-1000:]

        logger.log(
            (
                logging.INFO
                if alert.level == AlertLevel.INFO
                else (
                    logging.WARNING
                    if alert.level == AlertLevel.WARNING
                    else logging.ERROR if alert.level == AlertLevel.ERROR else logging.CRITICAL
                )
            ),
            f"ALERT [{alert.level.value.upper()}] {alert.title}: {alert.message}",
        )

        # Pozovi sve handlere
        for handler in self.handlers:
            try:
                await handler(alert) if asyncio.iscoroutinefunction(handler) else handler(alert)
            except Exception as e:
                logger.error(f"Alert handler error: {e}")

    def check_rules(self, metrics: MetricsCollector):
        """Proverava alert rules"""
        for rule in self.alert_rules:
            metric_name = rule["metric_name"]
            stats = metrics.get_metric_stats(metric_name, hours=1)

            if not stats:
                continue

            current_value = stats["current"]
            threshold = rule["threshold"]
            condition = rule["condition"]

            triggered = False
            if condition == "gt" and current_value > threshold:
                triggered = True
            elif condition == "lt" and current_value < threshold:
                triggered = True
            elif condition == "eq" and abs(current_value - threshold) < 0.001:
                triggered = True

            if triggered:
                # Proveri da li je već triggerovan u poslednji sat
                now = datetime.now()
                if rule["last_triggered"] is None or now - rule["last_triggered"] > timedelta(
                    hours=1
                ):

                    alert = Alert(
                        level=rule["level"],
                        title=f"Metric Alert: {metric_name}",
                        message=rule["message"].format(
                            metric=metric_name, value=current_value, threshold=threshold
                        ),
                        timestamp=now,
                        source="AlertManager",
                        metadata={"metric": metric_name, "value": current_value},
                    )

                    asyncio.create_task(self.send_alert(alert))
                    rule["last_triggered"] = now


class EmailNotifier:
    """Email notifikacije"""

    def __init__(
        self,
        smtp_server: str,
        smtp_port: int,
        username: str,
        password: str,
        from_email: str,
        to_emails: List[str],
    ):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_email = from_email
        self.to_emails = to_emails

    async def send_alert(self, alert: Alert):
        """Šalje alert email"""
        if alert.level in [AlertLevel.ERROR, AlertLevel.CRITICAL]:
            try:
                msg = MIMEMultipart()
                msg["From"] = self.from_email
                msg["To"] = ", ".join(self.to_emails)
                msg["Subject"] = f"[{alert.level.value.upper()}] {alert.title}"

                body = f"""
                Alert Level: {alert.level.value.upper()}
                Time: {alert.timestamp}
                Source: {alert.source}

                Message: {alert.message}

                Metadata: {json.dumps(alert.metadata, indent=2) if alert.metadata else 'None'}
                """

                msg.attach(MIMEText(body, "plain"))

                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
                server.quit()

                logger.info(f"Email alert sent: {alert.title}")

            except Exception as e:
                logger.error(f"Failed to send email alert: {e}")


class TelegramNotifier:
    """Telegram notifikacije"""

    def __init__(self, bot_token: str, chat_ids: List[str]):
        self.bot_token = bot_token
        self.chat_ids = chat_ids
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

    async def send_alert(self, alert: Alert):
        """Šalje alert na Telegram"""
        if alert.level in [AlertLevel.WARNING, AlertLevel.ERROR, AlertLevel.CRITICAL]:
            emoji = {AlertLevel.WARNING: "⚠️", AlertLevel.ERROR: "❌", AlertLevel.CRITICAL: "🚨"}

            message = f"{emoji.get(alert.level, '📢')} *{alert.title}*\n\n"
            message += f"*Level:* {alert.level.value.upper()}\n"
            message += f"*Time:* {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
            message += f"*Source:* {alert.source}\n\n"
            message += f"*Message:* {alert.message}"

            for chat_id in self.chat_ids:
                try:
                    async with aiohttp.ClientSession() as session:
                        url = f"{self.base_url}/sendMessage"
                        data = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}

                        async with session.post(url, data=data) as response:
                            if response.status == 200:
                                logger.info(f"Telegram alert sent to {chat_id}")
                            else:
                                logger.error(f"Failed to send Telegram alert: {response.status}")

                except Exception as e:
                    logger.error(f"Telegram notification error: {e}")


class WebhookNotifier:
    """Webhook notifikacije"""

    def __init__(self, webhook_urls: List[str]):
        self.webhook_urls = webhook_urls

    async def send_alert(self, alert: Alert):
        """Šalje alert na webhook"""
        payload = alert.to_dict()

        for url in self.webhook_urls:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=payload) as response:
                        if response.status == 200:
                            logger.info(f"Webhook alert sent to {url}")
                        else:
                            logger.error(f"Webhook alert failed: {response.status}")

            except Exception as e:
                logger.error(f"Webhook notification error: {e}")


class PerformanceMonitor:
    """Performance monitoring"""

    def __init__(self, portfolio_manager, exchange_manager):
        self.portfolio_manager = portfolio_manager
        self.exchange_manager = exchange_manager
        self.metrics = MetricsCollector()
        self.alert_manager = AlertManager()
        self.running = False

        # Setup default alert rules
        self._setup_default_alerts()

    def _setup_default_alerts(self):
        """Setup osnovnih alert rules"""
        # Drawdown alerts
        self.alert_manager.add_alert_rule(
            "drawdown_pct",
            "gt",
            10.0,
            AlertLevel.WARNING,
            "Portfolio drawdown exceeded 10%: {value:.2f}%",
        )

        self.alert_manager.add_alert_rule(
            "drawdown_pct",
            "gt",
            20.0,
            AlertLevel.CRITICAL,
            "Portfolio drawdown exceeded 20%: {value:.2f}%",
        )

        # PnL alerts
        self.alert_manager.add_alert_rule(
            "daily_pnl_pct", "lt", -5.0, AlertLevel.WARNING, "Daily PnL below -5%: {value:.2f}%"
        )

        # API error rate
        self.alert_manager.add_alert_rule(
            "api_error_rate", "gt", 0.1, AlertLevel.ERROR, "API error rate too high: {value:.2%}"
        )

    async def start_monitoring(self):
        """Pokretanje monitoring-a"""
        self.running = True
        console.print("[bold green]📊 Performance monitoring started[/bold green]")

        # Pokretanje monitoring task-ova
        tasks = [
            asyncio.create_task(self._monitor_portfolio()),
            asyncio.create_task(self._monitor_api_health()),
            asyncio.create_task(self._monitor_system_resources()),
            asyncio.create_task(self._check_alerts()),
        ]

        await asyncio.gather(*tasks, return_exceptions=True)

    async def _monitor_portfolio(self):
        """Monitoring portfolia"""
        while self.running:
            try:
                summary = self.portfolio_manager.get_portfolio_summary()

                # Beleži metrike
                self.metrics.record_metric("total_balance", summary["total_balance"])
                self.metrics.record_metric("total_pnl", summary["total_pnl"])
                self.metrics.record_metric("unrealized_pnl", summary["unrealized_pnl"])
                self.metrics.record_metric("drawdown_pct", summary["current_drawdown"])
                self.metrics.record_metric("open_positions", summary["open_positions"])

                # Daily PnL
                if summary["initial_balance"] > 0:
                    daily_pnl_pct = (summary["total_pnl"] / summary["initial_balance"]) * 100
                    self.metrics.record_metric("daily_pnl_pct", daily_pnl_pct)

                await asyncio.sleep(30)  # Svake 30 sekundi

            except Exception as e:
                logger.error(f"Portfolio monitoring error: {e}")
                await asyncio.sleep(60)

    async def _monitor_api_health(self):
        """Monitoring API health-a"""
        while self.running:
            try:
                total_calls = 0
                failed_calls = 0

                for exchange_name, exchange in self.exchange_manager.exchanges.items():
                    try:
                        # Test API call
                        await exchange.fetch_ticker("BTC/USDT")
                        total_calls += 1

                        # Beleži latency
                        start_time = asyncio.get_event_loop().time()
                        await exchange.fetch_balance()
                        latency = (asyncio.get_event_loop().time() - start_time) * 1000

                        self.metrics.record_metric(
                            "api_latency", latency, {"exchange": exchange_name}
                        )

                    except Exception as e:
                        failed_calls += 1
                        logger.warning(f"API health check failed for {exchange_name}: {e}")

                        self.metrics.record_metric(
                            "api_errors", 1, {"exchange": exchange_name, "error": str(e)[:100]}
                        )

                # Error rate
                if total_calls > 0:
                    error_rate = failed_calls / total_calls
                    self.metrics.record_metric("api_error_rate", error_rate)

                await asyncio.sleep(60)  # Svaki minut

            except Exception as e:
                logger.error(f"API health monitoring error: {e}")
                await asyncio.sleep(120)

    async def _monitor_system_resources(self):
        """Monitoring system resursa"""
        try:
            import psutil
        except ImportError:
            logger.warning("psutil not installed, skipping system monitoring")
            return

        while self.running:
            try:
                # CPU usage
                cpu_percent = psutil.cpu_percent(interval=1)
                self.metrics.record_metric("cpu_usage_pct", cpu_percent)

                # Memory usage
                memory = psutil.virtual_memory()
                self.metrics.record_metric("memory_usage_pct", memory.percent)
                self.metrics.record_metric("memory_available_mb", memory.available / 1024 / 1024)

                # Disk usage
                disk = psutil.disk_usage("/")
                disk_percent = (disk.used / disk.total) * 100
                self.metrics.record_metric("disk_usage_pct", disk_percent)

                await asyncio.sleep(30)

            except Exception as e:
                logger.error(f"System monitoring error: {e}")
                await asyncio.sleep(60)

    async def _check_alerts(self):
        """Proverava alert rules"""
        while self.running:
            try:
                self.alert_manager.check_rules(self.metrics)
                await asyncio.sleep(60)  # Svaki minut

            except Exception as e:
                logger.error(f"Alert checking error: {e}")
                await asyncio.sleep(120)

    def stop_monitoring(self):
        """Zaustavlja monitoring"""
        self.running = False
        console.print("[bold yellow]📊 Performance monitoring stopped[/bold yellow]")


class DashboardGenerator:
    """Generator za dashboard"""

    def __init__(self, metrics: MetricsCollector, portfolio_manager):
        self.metrics = metrics
        self.portfolio_manager = portfolio_manager

    def generate_portfolio_chart(self, hours: int = 24) -> go.Figure:
        """Generiše portfolio chart"""
        balance_history = self.metrics.get_metric_history("total_balance", hours)
        pnl_history = self.metrics.get_metric_history("total_pnl", hours)

        fig = make_subplots(
            rows=2, cols=1, subplot_titles=("Portfolio Balance", "PnL"), vertical_spacing=0.1
        )

        if balance_history:
            timestamps = [m["timestamp"] for m in balance_history]
            balances = [m["value"] for m in balance_history]

            fig.add_trace(
                go.Scatter(x=timestamps, y=balances, name="Balance", line=dict(color="blue")),
                row=1,
                col=1,
            )

        if pnl_history:
            timestamps = [m["timestamp"] for m in pnl_history]
            pnls = [m["value"] for m in pnl_history]

            fig.add_trace(
                go.Scatter(
                    x=timestamps, y=pnls, name="PnL", line=dict(color="green"), fill="tonexty"
                ),
                row=2,
                col=1,
            )

        fig.update_layout(title="Portfolio Performance", height=600, showlegend=True)

        return fig

    def generate_metrics_dashboard(self) -> str:
        """Generiše HTML dashboard"""
        portfolio_chart = self.generate_portfolio_chart()

        # API latency chart
        api_latency = self.metrics.get_metric_history("api_latency", 24)
        latency_fig = go.Figure()

        if api_latency:
            timestamps = [m["timestamp"] for m in api_latency]
            latencies = [m["value"] for m in api_latency]

            latency_fig.add_trace(go.Scatter(x=timestamps, y=latencies, name="API Latency (ms)"))

        latency_fig.update_layout(title="API Latency", height=400)

        # System resources
        cpu_history = self.metrics.get_metric_history("cpu_usage_pct", 24)
        memory_history = self.metrics.get_metric_history("memory_usage_pct", 24)

        resources_fig = make_subplots(rows=1, cols=2, subplot_titles=("CPU Usage", "Memory Usage"))

        if cpu_history:
            timestamps = [m["timestamp"] for m in cpu_history]
            cpu_values = [m["value"] for m in cpu_history]

            resources_fig.add_trace(
                go.Scatter(x=timestamps, y=cpu_values, name="CPU %"), row=1, col=1
            )

        if memory_history:
            timestamps = [m["timestamp"] for m in memory_history]
            memory_values = [m["value"] for m in memory_history]

            resources_fig.add_trace(
                go.Scatter(x=timestamps, y=memory_values, name="Memory %"), row=1, col=2
            )

        resources_fig.update_layout(title="System Resources", height=400)

        # Kombinuj sve u HTML
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Crypto Trading Dashboard</title>
            <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .chart-container {{ margin: 20px 0; }}
                .metrics-table {{ border-collapse: collapse; width: 100%; }}
                .metrics-table th, .metrics-table td {{ border: 1px solid #ddd; padding: 8px; }}
                .metrics-table th {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            <h1>Crypto Trading Dashboard</h1>
            <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

            <div class="chart-container">
                <div id="portfolio-chart"></div>
            </div>

            <div class="chart-container">
                <div id="latency-chart"></div>
            </div>

            <div class="chart-container">
                <div id="resources-chart"></div>
            </div>

            <script>
                Plotly.newPlot('portfolio-chart', {portfolio_chart.to_json()});
                Plotly.newPlot('latency-chart', {latency_fig.to_json()});
                Plotly.newPlot('resources-chart', {resources_fig.to_json()});
            </script>
        </body>
        </html>
        """

        return html_content

    def save_dashboard(self, filename: str = "dashboard.html"):
        """Čuva dashboard u HTML fajl"""
        html_content = self.generate_metrics_dashboard()

        with open(filename, "w") as f:
            f.write(html_content)

        logger.info(f"Dashboard saved to {filename}")


class LiveConsoleMonitor:
    """Live console monitoring"""

    def __init__(self, portfolio_manager, metrics: MetricsCollector):
        self.portfolio_manager = portfolio_manager
        self.metrics = metrics
        self.console = Console()

    def create_layout(self) -> Layout:
        """Kreira layout za live monitoring"""
        layout = Layout()

        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=3),
        )

        layout["main"].split_row(Layout(name="left"), Layout(name="right"))

        return layout

    def update_layout(self, layout: Layout):
        """Ažurira layout sa trenutnim podacima"""
        # Header
        layout["header"].update(
            Panel(
                f"[bold green]🚀 CRYPTO TRADING MONITOR 🚀[/bold green]\n"
                f"[yellow]Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/yellow]",
                title="Status",
            )
        )

        # Portfolio summary
        summary = self.portfolio_manager.get_portfolio_summary()

        portfolio_table = Table(title="Portfolio Summary")
        portfolio_table.add_column("Metric", style="cyan")
        portfolio_table.add_column("Value", style="green")

        portfolio_table.add_row("Total Balance", f"${summary['total_balance']:.2f}")
        portfolio_table.add_row("Total PnL", f"${summary['total_pnl']:.2f}")
        portfolio_table.add_row("Unrealized PnL", f"${summary['unrealized_pnl']:.2f}")
        portfolio_table.add_row("Return %", f"{summary['total_return_pct']:.2f}%")
        portfolio_table.add_row("Drawdown %", f"{summary['current_drawdown']:.2f}%")
        portfolio_table.add_row("Open Positions", str(summary["open_positions"]))

        layout["left"].update(portfolio_table)

        # Positions
        positions_table = Table(title="Open Positions")
        positions_table.add_column("Symbol", style="cyan")
        positions_table.add_column("Side", style="yellow")
        positions_table.add_column("Size", style="blue")
        positions_table.add_column("Entry", style="white")
        positions_table.add_column("Current", style="white")
        positions_table.add_column("PnL", style="green")
        positions_table.add_column("PnL %", style="green")

        for pos in summary["positions"]:
            pnl_color = "green" if pos["unrealized_pnl"] >= 0 else "red"
            positions_table.add_row(
                pos["symbol"],
                pos["side"],
                f"{pos['size']:.4f}",
                f"${pos['entry_price']:.2f}",
                f"${pos['current_price']:.2f}",
                f"[{pnl_color}]${pos['unrealized_pnl']:.2f}[/{pnl_color}]",
                f"[{pnl_color}]{pos['pnl_percentage']:.2f}%[/{pnl_color}]",
            )

        layout["right"].update(positions_table)

        # Footer - System metrics
        cpu_stats = self.metrics.get_metric_stats("cpu_usage_pct", 1)
        memory_stats = self.metrics.get_metric_stats("memory_usage_pct", 1)
        api_error_stats = self.metrics.get_metric_stats("api_error_rate", 1)

        footer_text = f"CPU: {cpu_stats.get('current', 0):.1f}% | "
        footer_text += f"Memory: {memory_stats.get('current', 0):.1f}% | "
        footer_text += f"API Errors: {api_error_stats.get('current', 0):.2%}"

        layout["footer"].update(Panel(footer_text, title="System Metrics"))

    async def start_live_monitor(self):
        """Pokretanje live monitoring-a"""
        layout = self.create_layout()

        with Live(layout, refresh_per_second=1, screen=True):
            while True:
                try:
                    self.update_layout(layout)
                    await asyncio.sleep(1)
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    logger.error(f"Live monitor error: {e}")
                    await asyncio.sleep(5)
