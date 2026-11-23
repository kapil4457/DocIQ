import json
import logging
import logging.config
import uuid
from datetime import datetime, date, timezone
from enum import Enum
from pathlib import Path

def _json_default(obj):
    if isinstance(obj, (uuid.UUID,)):
        return str(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    return str(obj)

class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_record = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        if hasattr(record, "extra_data"):
            log_record["extra"] = record.extra_data

        return json.dumps(log_record, default=_json_default)

class ExcludeHealthCheckFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return "/health" not in record.getMessage()

def setup_logging(log_dir: str = "logs") -> None:
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "no_health_checks": {
                "()": ExcludeHealthCheckFilter,
            }
        },
        "formatters": {
            "console_fmt": {
                "format": "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "json_fmt": {
                "()": JSONFormatter,
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "DEBUG",
                "formatter": "console_fmt",
                "filters": ["no_health_checks"],
                "stream": "ext://sys.stdout",
            },
            "rotating_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "INFO",
                "formatter": "json_fmt",
                "filename": f"{log_dir}/app.jsonl",
                "maxBytes": 10_485_760,  # 10 MB per file
                "backupCount": 10,         # Keep 5 historical files
                "encoding": "utf-8",
            },
            "error_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "ERROR",
                "formatter": "json_fmt",
                "filename": f"{log_dir}/errors.jsonl",
                "maxBytes": 10_485_760,
                "backupCount": 10,
                "encoding": "utf-8",
            },
        },
        "loggers": {
            "app": {
                "level": "DEBUG",
                "handlers": ["console", "rotating_file", "error_file"],
                "propagate": False,
            },
             "uvicorn.access": {
                "level": "INFO",
                "filters": ["no_health_checks"],
            },
        },
    }

    logging.config.dictConfig(logging_config)
