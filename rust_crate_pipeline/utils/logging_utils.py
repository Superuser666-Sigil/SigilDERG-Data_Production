# rust_crate_pipeline/utils/logging_utils.py
import os
import time
import psutil
import logging
from functools import wraps


def configure_logging(
    log_dir: str | None = None, log_level: int = logging.INFO
) -> logging.Logger:
    """
    Configure global logging with file and console handlers

    Args:
        log_dir: Directory for log files (defaults to current directory)
        log_level: Logging level (default: INFO)

    Returns:
        Root logger instance
    """
    logger = logging.getLogger()
    logger.setLevel(log_level)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_format = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s"
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # File handler
    if log_dir:
        log_file = os.path.join(
            log_dir,
            f"pipeline_{
                time.strftime('%Y%m%d-%H%M%S')}.log",
        )
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)
        file_format = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)

    return logger


def log_execution_time(func):
    """Decorator to log function execution time"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        logging.info(
            f"{func.__name__} executed in {end_time - start_time:.2f} seconds"
        )
        return result

    return wrapper


def log_resource_usage():
    """Log current resource utilization (CPU, memory, disk)"""
    cpu_percent = psutil.cpu_percent()
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage(".")

    logging.info(
        f"Resource Usage - CPU: {cpu_percent}%, Memory: {
            mem.percent}%, Disk: {
            disk.percent}%"
    )

    return {
        "cpu_percent": cpu_percent,
        "memory_percent": mem.percent,
        "disk_percent": disk.percent,
        "memory_available": mem.available,
        "disk_free": disk.free,
    }
