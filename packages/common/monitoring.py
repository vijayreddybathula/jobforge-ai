"""Monitoring and metrics utilities."""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from packages.common.redis_cache import get_redis_cache
from packages.common.logging import get_logger

logger = get_logger(__name__)


class MetricsCollector:
    """Collect and track system metrics."""

    def __init__(self):
        """Initialize metrics collector."""
        self.cache = get_redis_cache()
        self.metrics_prefix = "metrics:"

    def _get_key(self, metric_name: str, timestamp: Optional[datetime] = None) -> str:
        """Generate metric key."""
        if timestamp:
            date_str = timestamp.strftime("%Y-%m-%d")
            return f"{self.metrics_prefix}{metric_name}:{date_str}"
        return f"{self.metrics_prefix}{metric_name}"

    def increment_counter(
        self, metric_name: str, value: int = 1, tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Increment counter metric."""
        if not self.cache._is_available():
            return

        try:
            key = self._get_key(metric_name)
            self.cache.increment(key, value)

            # Also track daily counter
            daily_key = self._get_key(metric_name, datetime.utcnow())
            self.cache.increment(daily_key, value)
            self.cache.client.expire(daily_key, 86400 * 7)  # Keep for 7 days
        except Exception as e:
            logger.warning(f"Failed to increment metric {metric_name}: {e}")

    def set_gauge(self, metric_name: str, value: float) -> None:
        """Set gauge metric."""
        if not self.cache._is_available():
            return

        try:
            key = self._get_key(metric_name)
            self.cache.set(key, value, ttl=3600)
        except Exception as e:
            logger.warning(f"Failed to set gauge {metric_name}: {e}")

    def record_timing(self, metric_name: str, duration_ms: float) -> None:
        """Record timing metric."""
        if not self.cache._is_available():
            return

        try:
            # Store timing in a sorted set
            key = f"{self.metrics_prefix}timing:{metric_name}"
            timestamp = datetime.utcnow().timestamp()
            self.cache.client.zadd(key, {str(timestamp): duration_ms})
            self.cache.client.expire(key, 3600)  # Keep for 1 hour
        except Exception as e:
            logger.warning(f"Failed to record timing {metric_name}: {e}")

    def get_counter(self, metric_name: str) -> int:
        """Get counter value."""
        if not self.cache._is_available():
            return 0

        try:
            key = self._get_key(metric_name)
            value = self.cache.client.get(key)
            return int(value) if value else 0
        except Exception:
            return 0

    def get_daily_counter(self, metric_name: str, date: Optional[datetime] = None) -> int:
        """Get daily counter value."""
        if not self.cache._is_available():
            return 0

        try:
            date = date or datetime.utcnow()
            key = self._get_key(metric_name, date)
            value = self.cache.client.get(key)
            return int(value) if value else 0
        except Exception:
            return 0


# Global metrics collector instance
metrics_collector = MetricsCollector()


def track_llm_call(model: str, tokens: int, cost: float) -> None:
    """Track LLM API call."""
    metrics_collector.increment_counter(f"llm.calls.{model}")
    metrics_collector.increment_counter("llm.tokens.total", tokens)
    metrics_collector.increment_counter("llm.cost.total", int(cost * 1000))  # Store in cents


def track_scraping_result(source: str, success: bool) -> None:
    """Track scraping result."""
    if success:
        metrics_collector.increment_counter(f"scraping.success.{source}")
    else:
        metrics_collector.increment_counter(f"scraping.failure.{source}")


def track_parse_result(success: bool) -> None:
    """Track JD parse result."""
    if success:
        metrics_collector.increment_counter("parsing.success")
    else:
        metrics_collector.increment_counter("parsing.failure")


def track_application_result(mode: str, success: bool) -> None:
    """Track application result."""
    if success:
        metrics_collector.increment_counter(f"application.success.{mode}")
    else:
        metrics_collector.increment_counter(f"application.failure.{mode}")
