import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from prometheus_client import Counter, Histogram

request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
session_id: ContextVar[str | None] = ContextVar("session_id", default=None)
API_LATENCY = Histogram("shoppilot_api_seconds", "API latency", ["method", "route", "status"])
AI_LATENCY = Histogram("shoppilot_ai_seconds", "AI request latency", ["operation", "model"])
AI_ERRORS = Counter("shoppilot_ai_errors_total", "AI upstream failures", ["status"])
SEARCH_LATENCY = Histogram("shoppilot_search_seconds", "Search latency")
SEARCH_RESULTS = Histogram(
    "shoppilot_search_results", "Search result count", buckets=(0, 1, 2, 3, 4, 5)
)
TOOL_LATENCY = Histogram("shoppilot_tool_seconds", "Tool latency", ["tool"])
TOOL_ERRORS = Counter("shoppilot_tool_errors_total", "Tool errors", ["tool"])
COMMERCE_ACTIONS = Counter("shoppilot_commerce_actions_total", "Commerce actions", ["action"])


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        fields: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "event": record.getMessage(),
            "request_id": request_id.get(),
            "session_id": session_id.get(),
        }
        fields.update(getattr(record, "safe_fields", {}))
        return json.dumps(fields, default=str)


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.getLogger().handlers = [handler]
    logging.getLogger().setLevel(logging.INFO)
    # URLs and raw response bodies are not logged by transports.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
