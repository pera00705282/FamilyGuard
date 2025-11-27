#!/usr/bin/env python3
"""



Security Validator for Crypto Trading Automation Tool
=====================================================

Validira sigurnosne aspekte konfiguracije i API ključeva.
"""

from typing import List

console = Console()
logger = logging.getLogger(__name__)


@dataclass


class SecurityCheck:
    """Rezultat sigurnosne provere"""

    name: str
    passed: bool
    message: str
    severity: str  # 'low', 'medium', 'high', 'critical'
    recommendation: str = ""


class SecurityValidator:
    """Validator za sigurnosne aspekte"""

    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.config = None
        self.checks: List[SecurityCheck] = []

    async def load_config(self) -> bool:
        """Učitava konfiguraciju"""
        try:
            with open(self.config_path, "r") as f:
                self.config = yaml.safe_load(f)
            return True
        except Exception as e:
            console.print(f"[bold red]❌ Greška pri učitavanju konfiguracije: {e}[/bold red]")
            return False

    def add_check(self, check: SecurityCheck):
        """Dodaje sigurnosnu proveru"""
        self.checks.append(check)

    def _is_placeholder(self, value: str) -> bool:
        """Proverava da li je vrednost placeholder"""
        return value.startswith("YOUR_") or value == ""

    def _validate_binance_api_key(self, api_key: str) -> SecurityCheck:
        """Validira format Binance API ključa"""
        if len(api_key) != 64 or not re.match(r"^[A-Za-z0-9]+$", api_key):
            return SecurityCheck(
                name="binance_api_key_format",
                passed=False,
                message="Binance API ključ ima neispravnu format",
                severity="high",
                recommendation="Binance API ključ treba da bude 64 karaktera, samo slova i brojevi",
            )
        return SecurityCheck(
            name="binance_api_key_format",
            passed=True,
            message="Binance API ključ ima ispravnu format",
            severity="low",
        )

    def _validate_coinbase_api_key(self, api_key: str) -> SecurityCheck:
        """Validira format Coinbase API ključa"""
        if not re.match(r"^[a-f0-9-]+$", api_key):
            return SecurityCheck(
                name="coinbase_api_key_format",
                passed=False,
                message="Coinbase API ključ ima neispravnu format",
                severity="high",
                recommendation="Coinbase API ključ treba da bude UUID format",
            )
        return SecurityCheck(
            name="coinbase_api_key_format",
            passed=True,
            message="Coinbase API ključ ima ispravnu format",
            severity="low",
        )

    def _validate_kraken_api_key(self, api_key: str) -> SecurityCheck:
        """Validira format Kraken API ključa"""
        if len(api_key) < 50 or not re.match(r"^[A-Za-z0-9+/=]+$", api_key):
            return SecurityCheck(
                name="kraken_api_key_format",
                passed=False,
                message="Kraken API ključ ima neispravnu format",
                severity="high",
                recommendation="Kraken API ključ treba da bude base64 enkodovan",
            )
        return SecurityCheck(
            name="kraken_api_key_format",
            passed=True,
            message="Kraken API ključ ima ispravnu format",
            severity="low",
        )

    def _validate_api_key_format(self, exchange_name: str, api_key: str) -> SecurityCheck:
        """Validira format API ključa za određenu berzu"""
        validators = {
            "binance": self._validate_binance_api_key,
            "coinbase": self._validate_coinbase_api_key,
            "kraken": self._validate_kraken_api_key,
        }
        validator = validators.get(exchange_name)
        if validator:
            return validator(api_key)
        return SecurityCheck(
            name=f"{exchange_name}_api_key_format",
            passed=True,
            message=f"API ključ format za {exchange_name} nije validiran",
            severity="low",
        )

    def check_api_key_format(self) -> List[SecurityCheck]:
        """Proverava format API ključeva"""
        checks = []

        if not self.config or "exchanges" not in self.config:
            return checks

        for exchange_name, exchange_config in self.config["exchanges"].items():
            api_key = exchange_config.get("api_key", "")
            secret = exchange_config.get("secret", "")

            # Proveri da li su placeholder vrednosti
            if self._is_placeholder(api_key):
                checks.append(
                    SecurityCheck(
                        name=f"{exchange_name}_api_key_placeholder",
                        passed=False,
                        message=f"API ključ za {exchange_name} je placeholder vrednost",
                        severity="critical",
                        recommendation=f"Zameniti sa stvarnim API ključem za {exchange_name}",
                    )
                )
            else:
                checks.append(self._validate_api_key_format(exchange_name, api_key))

            # Proveri secret
            if self._is_placeholder(secret):
                checks.append(
                    SecurityCheck(
                        name=f"{exchange_name}_secret_placeholder",
                        passed=False,
                        message=f"Secret za {exchange_name} je placeholder vrednost",
                        severity="critical",
                        recommendation=f"Zameniti sa stvarnim secret-om za {exchange_name}",
                    )
                )
            else:
                checks.append(
                    SecurityCheck(
                        name=f"{exchange_name}_secret_present",
                        passed=True,
                        message=f"Secret za {exchange_name} je postavljen",
                        severity="low",
                    )
                )

        return checks

    def check_sandbox_mode(self) -> List[SecurityCheck]:
        """Proverava da li je sandbox mode uključen"""
        checks = []

        if not self.config or "exchanges" not in self.config:
            return checks

        live_trading_enabled = self.config.get("enable_live_trading", False)

        for exchange_name, exchange_config in self.config["exchanges"].items():
            sandbox = exchange_config.get("sandbox", True)

            if not sandbox and not live_trading_enabled:
                checks.append(
                    SecurityCheck(
                        name=f"{exchange_name}_sandbox_disabled",
                        passed=False,
                        message=f"Sandbox mode je isključen za {exchange_name} ali live trading nije eksplicitno omogućen",
                        severity="high",
                        recommendation="Uključiti sandbox mode ili eksplicitno omogućiti live trading",
                    )
                )
            elif not sandbox and live_trading_enabled:
                checks.append(
                    SecurityCheck(
                        name=f"{exchange_name}_live_trading",
                        passed=True,
                        message=f"Live trading je eksplicitno omogućen za {exchange_name}",
                        severity="medium",
                        recommendation="Pažljivo testiraj pre pokretanja sa pravim novcem",
                    )
                )
            else:
                checks.append(
                    SecurityCheck(
                        name=f"{exchange_name}_sandbox_enabled",
                        passed=True,
                        message=f"Sandbox mode je uključen za {exchange_name}",
                        severity="low",
                    )
                )

        return checks

    def check_risk_parameters(self) -> List[SecurityCheck]:
        """Proverava risk management parametre"""
        checks = []

        if not self.config:
            return checks

        trading_config = self.config.get("trading", {})
        risk_config = trading_config.get("risk_management", {})

        # Proveri max_position_size
        max_position_size = risk_config.get("max_position_size", 1.0)
        if max_position_size > 0.2:  # Više od 20%
            checks.append(
                SecurityCheck(
                    name="max_position_size_high",
                    passed=False,
                    message=f"Maksimalna veličina pozicije je visoka: {max_position_size * 100:.1f}%",
                    severity="medium",
                    recommendation="Preporučuje se maksimalno 20% portfolia po poziciji",
                )
            )
        else:
            checks.append(
                SecurityCheck(
                    name="max_position_size_safe",
                    passed=True,
                    message=f"Maksimalna veličina pozicije je sigurna: {max_position_size * 100:.1f}%",
                    severity="low",
                )
            )

        # Proveri stop_loss_pct
        stop_loss_pct = risk_config.get("stop_loss_pct", 0.0)
        if stop_loss_pct == 0.0:
            checks.append(
                SecurityCheck(
                    name="no_stop_loss",
                    passed=False,
                    message="Stop loss nije postavljen",
                    severity="high",
                    recommendation="Postaviti stop loss na najmanje 1-2%",
                )
            )
        elif stop_loss_pct > 0.1:  # Više od 10%
            checks.append(
                SecurityCheck(
                    name="stop_loss_too_high",
                    passed=False,
                    message=f"Stop loss je previsok: {stop_loss_pct * 100:.1f}%",
                    severity="medium",
                    recommendation="Preporučuje se stop loss između 1-5%",
                )
            )
        else:
            checks.append(
                SecurityCheck(
                    name="stop_loss_reasonable",
                    passed=True,
                    message=f"Stop loss je razuman: {stop_loss_pct * 100:.1f}%",
                    severity="low",
                )
            )

        # Proveri max_daily_trades
        max_daily_trades = risk_config.get("max_daily_trades", 100)
        if max_daily_trades > 50:
            checks.append(
                SecurityCheck(
                    name="max_daily_trades_high",
                    passed=False,
                    message=f"Maksimalan broj dnevnih trade-ova je visok: {max_daily_trades}",
                    severity="medium",
                    recommendation="Preporučuje se maksimalno 20-30 trade-ova dnevno",
                )
            )
        else:
            checks.append(
                SecurityCheck(
                    name="max_daily_trades_reasonable",
                    passed=True,
                    message=f"Maksimalan broj dnevnih trade-ova je razuman: {max_daily_trades}",
                    severity="low",
                )
            )

        return checks

    def check_rate_limits(self) -> List[SecurityCheck]:
        """Proverava rate limit konfiguraciju"""
        checks = []

        if not self.config or "exchanges" not in self.config:
            return checks

        recommended_limits = {
            "binance": 1200,  # requests per minute
            "coinbase": 10,  # requests per second
            "kraken": 15,  # calls per minute
        }

        for exchange_name, exchange_config in self.config["exchanges"].items():
            rate_limit = exchange_config.get("rate_limit", 0)
            enable_rate_limit = exchange_config.get("enable_rate_limit", False)

            if not enable_rate_limit:
                checks.append(
                    SecurityCheck(
                        name=f"{exchange_name}_rate_limit_disabled",
                        passed=False,
                        message=f"Rate limiting je isključen za {exchange_name}",
                        severity="high",
                        recommendation="Uključiti rate limiting da se izbegnu ban-ovi",
                    )
                )
            else:
                recommended = recommended_limits.get(exchange_name, 100)
                if rate_limit > recommended * 1.5:  # 50% više od preporučenog
                    checks.append(
                        SecurityCheck(
                            name=f"{exchange_name}_rate_limit_high",
                            passed=False,
                            message=f"Rate limit za {exchange_name} je previsok: {rate_limit}",
                            severity="medium",
                            recommendation=f"Preporučuje se maksimalno {recommended}",
                        )
                    )
                else:
                    checks.append(
                        SecurityCheck(
                            name=f"{exchange_name}_rate_limit_safe",
                            passed=True,
                            message=f"Rate limit za {exchange_name} je siguran: {rate_limit}",
                            severity="low",
                        )
                    )

        return checks

    async def test_api_connections(self) -> List[SecurityCheck]:
        """Testira API konekcije"""
        checks = []

        if not self.config or "exchanges" not in self.config:
            return checks

        for exchange_name, exchange_config in self.config["exchanges"].items():
            try:
                # Kreiranje exchange instance
                exchange_class = getattr(ccxt, exchange_name.lower())
                exchange = exchange_class(
                    {
                        "apiKey": exchange_config["api_key"],
                        "secret": exchange_config["secret"],
                        "password": exchange_config.get("passphrase"),
                        "sandbox": exchange_config.get("sandbox", True),
                        "enableRateLimit": True,
                        "timeout": 10000,
                    }
                )

                # Test osnovne konekcije
                await exchange.load_markets()

                # Test autentifikacije
                await exchange.fetch_balance()

                await exchange.close()

                checks.append(
                    SecurityCheck(
                        name=f"{exchange_name}_connection_success",
                        passed=True,
                        message=f"Uspešna konekcija sa {exchange_name}",
                        severity="low",
                    )
                )

            except ccxt.AuthenticationError as e:
                checks.append(
                    SecurityCheck(
                        name=f"{exchange_name}_auth_failed",
                        passed=False,
                        message=f"Autentifikacija neuspešna za {exchange_name}: {str(e)}",
                        severity="critical",
                        recommendation="Proveriti API ključeve i permisije",
                    )
                )

            except ccxt.NetworkError as e:
                checks.append(
                    SecurityCheck(
                        name=f"{exchange_name}_network_error",
                        passed=False,
                        message=f"Mrežna greška za {exchange_name}: {str(e)}",
                        severity="medium",
                        recommendation="Proveriti internet konekciju i firewall",
                    )
                )

            except Exception as e:
                checks.append(
                    SecurityCheck(
                        name=f"{exchange_name}_unknown_error",
                        passed=False,
                        message=f"Nepoznata greška za {exchange_name}: {str(e)}",
                        severity="high",
                        recommendation="Proveriti konfiguraciju i dokumentaciju",
                    )
                )

        return checks

    def check_file_permissions(self) -> List[SecurityCheck]:
        """Proverava permisije fajlova"""
        checks = []

        # Proveri permisije config fajla
        try:
            stat_info = os.stat(self.config_path)
            permissions = oct(stat_info.st_mode)[-3:]

            if permissions != "600":  # Samo owner read/write
                checks.append(
                    SecurityCheck(
                        name="config_file_permissions",
                        passed=False,
                        message=f"Config fajl ima nesigurne permisije: {permissions}",
                        severity="medium",
                        recommendation="Postaviti permisije na 600 (chmod 600 config.yaml)",
                    )
                )
            else:
                checks.append(
                    SecurityCheck(
                        name="config_file_permissions",
                        passed=True,
                        message="Config fajl ima sigurne permisije",
                        severity="low",
                    )
                )

        except Exception as e:
            checks.append(
                SecurityCheck(
                    name="config_file_permissions_check",
                    passed=False,
                    message=f"Greška pri proveri permisija: {e}",
                    severity="low",
                )
            )

        return checks

    async def run_all_checks(self) -> List[SecurityCheck]:
        """Pokreće sve sigurnosne provere"""
        all_checks = []

        console.print("[bold blue]🔒 Pokretanje sigurnosnih provera...[/bold blue]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:

            # API key format
            task1 = progress.add_task("Proverava format API ključeva...", total=None)
            all_checks.extend(self.check_api_key_format())
            progress.update(task1, completed=True)

            # Sandbox mode
            task2 = progress.add_task("Proverava sandbox mode...", total=None)
            all_checks.extend(self.check_sandbox_mode())
            progress.update(task2, completed=True)

            # Risk parameters
            task3 = progress.add_task("Proverava risk parametre...", total=None)
            all_checks.extend(self.check_risk_parameters())
            progress.update(task3, completed=True)

            # Rate limits
            task4 = progress.add_task("Proverava rate limits...", total=None)
            all_checks.extend(self.check_rate_limits())
            progress.update(task4, completed=True)

            # File permissions
            task5 = progress.add_task("Proverava permisije fajlova...", total=None)
            all_checks.extend(self.check_file_permissions())
            progress.update(task5, completed=True)

            # API connections
            task6 = progress.add_task("Testira API konekcije...", total=None)
            api_checks = await self.test_api_connections()
            all_checks.extend(api_checks)
            progress.update(task6, completed=True)

        return all_checks

    def generate_report(self, checks: List[SecurityCheck]) -> str:
        """Generiše sigurnosni izveštaj"""
        # Grupiši po severity
        critical = [c for c in checks if c.severity == "critical"]
        high = [c for c in checks if c.severity == "high"]
        medium = [c for c in checks if c.severity == "medium"]
        low = [c for c in checks if c.severity == "low"]

        # Grupiši po rezultatu
        passed = [c for c in checks if c.passed]
        failed = [c for c in checks if not c.passed]

        report = f"""
SIGURNOSNI IZVEŠTAJ
==================

Ukupno provera: {len(checks)}
Prošle: {len(passed)}
Neuspešne: {len(failed)}

SEVERITY BREAKDOWN:
- Critical: {len(critical)}
- High: {len(high)}
- Medium: {len(medium)}
- Low: {len(low)}

NEUSPEŠNE PROVERE:
"""

        for check in failed:
            report += f"\n[{check.severity.upper()}] {check.name}:\n"
            report += f"  Poruka: {check.message}\n"
            if check.recommendation:
                report += f"  Preporuka: {check.recommendation}\n"

        return report


async def main():
    """Glavna funkcija"""
    console.print(
        Panel.fit(
            "[bold red]🔒 SECURITY VALIDATOR 🔒[/bold red]\n"
            "[yellow]Validacija sigurnosnih aspekata konfiguracije[/yellow]",
            title="SIGURNOST",
        )
    )

    validator = SecurityValidator()

    # Učitaj konfiguraciju
    if not await validator.load_config():
        return

    # Pokreni sve provere
    checks = await validator.run_all_checks()

    # Prikaži rezultate
    console.print("\n[bold green]📊 REZULTATI SIGURNOSNIH PROVERA[/bold green]")

    # Tabela rezultata
    table = Table(title="Sigurnosne Provere")
    table.add_column("Prover", style="cyan")
    table.add_column("Status", style="white")
    table.add_column("Severity", style="yellow")
    table.add_column("Poruka", style="white")

    for check in checks:
        status_color = "green" if check.passed else "red"
        status_text = "✅ PROŠLA" if check.passed else "❌ NEUSPEŠNA"

        severity_color = {
            "low": "green",
            "medium": "yellow",
            "high": "orange",
            "critical": "red",
        }.get(check.severity, "white")

        table.add_row(
            check.name,
            f"[{status_color}]{status_text}[/{status_color}]",
            f"[{severity_color}]{check.severity.upper()}[/{severity_color}]",
            check.message[:80] + "..." if len(check.message) > 80 else check.message,
        )

    console.print(table)

    # Sažetak
    passed = len([c for c in checks if c.passed])
    failed = len([c for c in checks if not c.passed])
    critical = len([c for c in checks if c.severity == "critical" and not c.passed])

    if critical > 0:
        console.print(f"\n[bold red]🚨 KRITIČNE GREŠKE: {critical}[/bold red]")
        console.print("[red]Alat NIJE SIGURAN za pokretanje![/red]")
    elif failed > 0:
        console.print(f"\n[bold yellow]⚠️ UPOZORENJA: {failed}[/bold yellow]")
        console.print("[yellow]Preporučuje se rešavanje problema pre pokretanja[/yellow]")
    else:
        console.print(f"\n[bold green]✅ SVE PROVERE PROŠLE: {passed}[/bold green]")
        console.print("[green]Alat je siguran za pokretanje![/green]")

    # Preporuke
    failed_checks = [c for c in checks if not c.passed and c.recommendation]
    if failed_checks:
        console.print("\n[bold blue]💡 PREPORUKE:[/bold blue]")
        for i, check in enumerate(failed_checks[:5], 1):  # Prikaži prvih 5
            console.print(f"{i}. {check.recommendation}")

    # Generiši detaljni izveštaj
    report = validator.generate_report(checks)
    with open("security_report.txt", "w") as f:
        f.write(report)

    console.print("\n[blue]📄 Detaljni izveštaj sačuvan u: security_report.txt[/blue]")


if __name__ == "__main__":
    asyncio.run(main())