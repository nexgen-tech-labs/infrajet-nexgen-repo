from loguru import logger
import sys
import os
from pathlib import Path
import contextvars
import asyncio
from dotenv import load_dotenv

load_dotenv() 
# ----------------------------------------------------
# Environment & Paths
# ----------------------------------------------------
ENV = os.getenv("APP_ENV", "development")
APP_NAME = "Infrajet"
LOG_LEVEL = "DEBUG" if ENV == "development" else "INFO"

LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ----------------------------------------------------
# Context Management (Async + Threads safe)
# ----------------------------------------------------
env_var = contextvars.ContextVar("env", default=ENV)
app_name_var = contextvars.ContextVar("app_name", default=APP_NAME)
extra_context_var = contextvars.ContextVar("extra", default={})

class ContextFilter:
    """Inject environment, app name, and custom context into logs."""
    def set_context(self, **kwargs):
        extra_context_var.set(kwargs)

    def __call__(self, record):
        record["extra"]["env"] = env_var.get()
        record["extra"]["app_name"] = app_name_var.get()
        record["extra"].update(extra_context_var.get())
        return record

context_filter = ContextFilter()
logger.configure(patcher=context_filter)

# ----------------------------------------------------
# Formats
# ----------------------------------------------------
CONSOLE_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "<magenta>{extra[env]}</magenta> | <blue>{extra[app_name]}</blue> | "
    "<level>{message}</level>"
)

FILE_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
    "{name}:{function}:{line} | env={extra[env]} | app={extra[app_name]} | {message}"
)

# ----------------------------------------------------
# Handlers
# ----------------------------------------------------
logger.remove()

# Console logging
logger.add(
    sys.stdout,
    colorize=True,
    format=CONSOLE_FORMAT,
    level=LOG_LEVEL,
    backtrace=True,
    diagnose=True,
    enqueue=True
)

# Application log
logger.add(
    LOG_DIR / "app.log",
    format=FILE_FORMAT,
    level="INFO",
    rotation="10 MB",
    retention="30 days",
    compression="zip",
    enqueue=True
)

# Error log
logger.add(
    LOG_DIR / "error.log",
    format=FILE_FORMAT,
    level="ERROR",
    rotation="5 MB",
    retention="60 days",
    compression="zip",
    enqueue=True
)

# Debug log (only in development)
if ENV == "development":
    logger.add(
        LOG_DIR / "debug.log",
        format=FILE_FORMAT,
        level="DEBUG",
        rotation="5 MB",
        retention="7 days",
        enqueue=True
    )

# Structured JSON logs
try:
    logger.add(
        LOG_DIR / "structured.json",
        serialize=True,  # ✅ Let Loguru handle JSON serialization
        level="DEBUG",
        rotation="10 MB",  # Increased rotation size to reduce frequency
        retention="15 days",
        compression="gz",
        enqueue=True,
        delay=True  # Delay file opening until first log message
    )
except Exception as e:
    # Fallback: log to console only if file logging fails
    logger.warning(f"Failed to setup structured JSON logging: {e}. Using console only.")
    pass

# ----------------------------------------------------
# Exception Handling
# ----------------------------------------------------
def log_exceptions(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.opt(exception=(exc_type, exc_value, exc_traceback)).error("Unhandled exception")

sys.excepthook = log_exceptions

def asyncio_exception_handler(loop, context):
    msg = context.get("exception", context["message"])
    logger.error(f"Unhandled async exception: {msg}")

asyncio.get_event_loop().set_exception_handler(asyncio_exception_handler)

# ----------------------------------------------------
# Export
# ----------------------------------------------------
def get_logger():
    return logger

def get_context_filter():
    return context_filter
