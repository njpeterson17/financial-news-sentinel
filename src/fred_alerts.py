"""
FRED Economic Data Alerts for Nickberg Terminal.

Monitors economic indicators from FRED and generates alerts when
significant changes are detected.
"""

import sys
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Any
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from logging_config import get_logger

logger = get_logger(__name__)

# Try to import OpenBB
try:
    from openbb import obb
    OPENBB_AVAILABLE = True
except ImportError:
    OPENBB_AVAILABLE = False
    logger.warning("OpenBB not installed. FRED alerts will be disabled.")


@dataclass
class EconomicAlert:
    """Alert for significant economic indicator changes."""
    indicator: str
    name: str
    current_value: float
    previous_value: float
    change_pct: float
    change_abs: float
    severity: str  # "high", "medium", "low"
    message: str
    timestamp: datetime


class FREDEconomicMonitor:
    """
    Monitor economic indicators from FRED and generate alerts.
    
    Tracks key indicators like:
    - Interest rates (10Y Treasury, Fed Funds)
    - Employment (Unemployment rate)
    - Inflation (CPI)
    - Economic growth (GDP)
    - Market indicators (S&P 500)
    """

    # Default indicators to monitor
    DEFAULT_INDICATORS = {
        "treasury_10y": {
            "symbol": "DGS10",
            "name": "10-Year Treasury Rate",
            "threshold_pct": 5.0,  # Alert on 5% change
            "threshold_abs": 0.1,  # Or 0.1 percentage point change
        },
        "treasury_2y": {
            "symbol": "DGS2",
            "name": "2-Year Treasury Rate",
            "threshold_pct": 5.0,
            "threshold_abs": 0.1,
        },
        "fed_funds": {
            "symbol": "FEDFUNDS",
            "name": "Federal Funds Rate",
            "threshold_pct": 10.0,
            "threshold_abs": 0.25,
        },
        "unemployment": {
            "symbol": "UNRATE",
            "name": "Unemployment Rate",
            "threshold_pct": 5.0,
            "threshold_abs": 0.2,
        },
        "cpi": {
            "symbol": "CPIAUCSL",
            "name": "Consumer Price Index",
            "threshold_pct": 1.0,
            "threshold_abs": None,
        },
        "sp500": {
            "symbol": "SP500",
            "name": "S&P 500 Index",
            "threshold_pct": 2.0,
            "threshold_abs": None,
        },
    }

    def __init__(self, config: dict[str, Any] | None = None):
        """
        Initialize the FRED economic monitor.

        Args:
            config: Optional configuration with keys:
                - enabled: bool (default True)
                - indicators: Dict of indicator configs
                - check_interval_hours: int (default 24)
        """
        self.config = config or {}
        self.enabled = self.config.get("enabled", True) and OPENBB_AVAILABLE
        self.indicators = self.config.get("indicators", self.DEFAULT_INDICATORS)
        self.check_interval_hours = self.config.get("check_interval_hours", 24)
        
        # Store last known values to detect changes
        self._last_values: dict[str, dict[str, Any]] = {}

        if not self.enabled:
            logger.warning("FREDEconomicMonitor initialized but OpenBB not available")
        else:
            logger.info(
                f"FRED Economic Monitor initialized with {len(self.indicators)} indicators"
            )

    def get_indicator_value(self, symbol: str) -> tuple[float, datetime] | None:
        """
        Fetch current value for an indicator.

        Args:
            symbol: FRED series symbol

        Returns:
            Tuple of (value, date) or None if unavailable
        """
        if not self.enabled:
            return None

        try:
            result = obb.economy.fred_series(symbol=symbol, limit=2)
            df = result.to_df()

            if df.empty:
                return None

            latest_value = float(df.iloc[-1].iloc[0])
            latest_date = df.index[-1]
            
            if isinstance(latest_date, str):
                latest_date = datetime.fromisoformat(latest_date)

            return latest_value, latest_date

        except Exception as e:
            logger.warning(f"Failed to get indicator {symbol}: {e}")
            return None

    def check_indicator(self, key: str, config: dict) -> EconomicAlert | None:
        """
        Check a single indicator for significant changes.

        Args:
            key: Indicator key
            config: Indicator configuration

        Returns:
            EconomicAlert if significant change detected, None otherwise
        """
        symbol = config["symbol"]
        name = config["name"]
        threshold_pct = config.get("threshold_pct", 5.0)
        threshold_abs = config.get("threshold_abs")

        current = self.get_indicator_value(symbol)
        if not current:
            return None

        current_value, current_date = current

        # Check if we have a previous value
        if key in self._last_values:
            prev_value = self._last_values[key]["value"]
            prev_date = self._last_values[key]["date"]
            
            # Calculate changes
            change_abs = current_value - prev_value
            change_pct = ((current_value - prev_value) / prev_value * 100) if prev_value != 0 else 0

            # Determine if change is significant
            is_significant = False
            if threshold_pct and abs(change_pct) >= threshold_pct:
                is_significant = True
            if threshold_abs and abs(change_abs) >= threshold_abs:
                is_significant = True

            if is_significant:
                # Determine severity
                severity = "low"
                if abs(change_pct) >= threshold_pct * 2 if threshold_pct else False:
                    severity = "high"
                elif abs(change_pct) >= threshold_pct if threshold_pct else False:
                    severity = "medium"

                # Create message
                direction = "increased" if change_abs > 0 else "decreased"
                message = (
                    f"{name} {direction} to {current_value:.2f} "
                    f"({change_abs:+.2f}, {change_pct:+.2f}% from previous)"
                )

                alert = EconomicAlert(
                    indicator=key,
                    name=name,
                    current_value=current_value,
                    previous_value=prev_value,
                    change_pct=round(change_pct, 2),
                    change_abs=round(change_abs, 2),
                    severity=severity,
                    message=message,
                    timestamp=current_date,
                )

                logger.info(
                    f"Economic alert generated: {key}",
                    extra={
                        "indicator": key,
                        "change_pct": change_pct,
                        "severity": severity
                    }
                )

                return alert

        # Update stored value
        self._last_values[key] = {
            "value": current_value,
            "date": current_date,
            "checked_at": datetime.now(),
        }

        return None

    def check_all_indicators(self) -> list[EconomicAlert]:
        """
        Check all configured indicators.

        Returns:
            List of EconomicAlert objects for significant changes
        """
        if not self.enabled:
            logger.debug("FRED monitor disabled, skipping check")
            return []

        alerts = []
        for key, config in self.indicators.items():
            try:
                alert = self.check_indicator(key, config)
                if alert:
                    alerts.append(alert)
            except Exception as e:
                logger.error(f"Error checking indicator {key}: {e}")
                continue

        if alerts:
            logger.info(f"Generated {len(alerts)} economic alerts")
        else:
            logger.debug("No significant economic changes detected")

        return alerts

    def get_indicator_summary(self) -> dict[str, dict[str, Any]]:
        """
        Get current summary of all indicators.

        Returns:
            Dict mapping indicator key to current values
        """
        if not self.enabled:
            return {}

        summary = {}
        for key, config in self.indicators.items():
            try:
                value_date = self.get_indicator_value(config["symbol"])
                if value_date:
                    value, date = value_date
                    summary[key] = {
                        "name": config["name"],
                        "value": value,
                        "date": date.isoformat() if isinstance(date, datetime) else str(date),
                    }
            except Exception as e:
                logger.warning(f"Error getting summary for {key}: {e}")

        return summary

    def format_alert_for_telegram(self, alert: EconomicAlert) -> str:
        """
        Format an economic alert for Telegram notification.

        Args:
            alert: EconomicAlert to format

        Returns:
            Formatted string
        """
        emoji_map = {
            "high": "🚨",
            "medium": "⚠️",
            "low": "ℹ️"
        }
        emoji = emoji_map.get(alert.severity, "📊")

        return (
            f"{emoji} *Economic Alert: {alert.name}*\n"
            f"Current: {alert.current_value:.2f}\n"
            f"Change: {alert.change_abs:+.2f} ({alert.change_pct:+.2f}%)\n"
            f"Severity: {alert.severity.upper()}"
        )


class EconomicAlertManager:
    """
    Manager for economic alerts that integrates with the main alert system.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """
        Initialize the economic alert manager.

        Args:
            config: Configuration for FRED monitor and alerts
        """
        self.config = config or {}
        self.monitor = FREDEconomicMonitor(self.config.get("fred", {}))
        self.enabled = self.monitor.enabled

    def check_and_generate_alerts(self) -> list[dict[str, Any]]:
        """
        Check indicators and generate alerts in the standard format.

        Returns:
            List of alert dicts compatible with AlertManager
        """
        economic_alerts = self.monitor.check_all_indicators()
        
        formatted_alerts = []
        for alert in economic_alerts:
            formatted_alert = {
                "type": "economic_indicator",
                "indicator": alert.indicator,
                "name": alert.name,
                "severity": alert.severity,
                "message": alert.message,
                "current_value": alert.current_value,
                "change_pct": alert.change_pct,
                "timestamp": alert.timestamp.isoformat(),
            }
            formatted_alerts.append(formatted_alert)

        return formatted_alerts


def create_economic_alert_manager(config: dict | None = None) -> EconomicAlertManager:
    """
    Factory function to create an economic alert manager.

    Args:
        config: Configuration dict

    Returns:
        Configured EconomicAlertManager
    """
    return EconomicAlertManager(config)
