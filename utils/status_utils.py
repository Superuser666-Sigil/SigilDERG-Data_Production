#!/usr/bin/env python3
"""
Cross-platform status indicators and retry mechanisms for SigilDERG-Data_Production

This module provides Rule Zero-aligned status reporting with:
- Platform-agnostic visual indicators
- Retry mechanisms with exponential backoff
- Clear success/failure feedback
- Performance timing
"""

import sys
import time
import platform
from typing import Any

from collections.abc import Callable
from functools import wraps
import logging


class StatusIndicator:
    """Cross-platform status indicator with fallback symbols."""
    
    def __init__(self):
        self.platform = platform.system().lower()
        self.supports_unicode = self._check_unicode_support()
        
    def _check_unicode_support(self) -> bool:
        """Check if terminal supports Unicode characters."""
        try:
            # Test Unicode output
            if self.platform == "windows":
                # Windows Terminal/PowerShell 7+ usually support Unicode
                return sys.stdout.encoding.lower() in ['utf-8', 'utf-16']
            else:
                # Linux/Unix typically support Unicode
                return True
        except:
            return False
    
    @property
    def success(self) -> str:
        """Success indicator."""
        if self.supports_unicode:
            return "✅"
        return "[OK]" if self.platform == "windows" else "✓"
    
    @property
    def error(self) -> str:
        """Error indicator."""
        if self.supports_unicode:
            return "❌"
        return "[ERROR]" if self.platform == "windows" else "✗"
    
    @property
    def warning(self) -> str:
        """Warning indicator."""
        if self.supports_unicode:
            return "⚠️"
        return "[WARN]" if self.platform == "windows" else "!"
    
    @property
    def info(self) -> str:
        """Info indicator."""
        if self.supports_unicode:
            return "ℹ️"
        return "[INFO]" if self.platform == "windows" else "i"
    
    @property
    def running(self) -> str:
        """Running/in-progress indicator."""
        if self.supports_unicode:
            return "🔄"
        return "[RUNNING]" if self.platform == "windows" else ">"
    
    @property
    def timer(self) -> str:
        """Timer indicator."""
        if self.supports_unicode:
            return "⏱️"
        return "[TIME]" if self.platform == "windows" else "⧗"


# Global status indicator instance
status = StatusIndicator()


def with_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple[type[BaseException], ...] = (Exception,)
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator for adding retry logic with exponential backoff.
    
    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries (seconds)
        backoff_factor: Multiplier for delay on each retry
        exceptions: Tuple of exceptions to catch and retry on
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: BaseException | None = None
            current_delay = delay
            for attempt in range(max_attempts):
                try:
                    if attempt > 0:
                        print(f"{status.running} Retry attempt {attempt}/{max_attempts-1} for {func.__name__}")
                        time.sleep(current_delay)
                        current_delay *= backoff_factor
                    result = func(*args, **kwargs)
                    if attempt > 0:
                        print(f"{status.success} {func.__name__} succeeded on retry {attempt}")
                    return result
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        print(f"{status.warning} {func.__name__} failed (attempt {attempt+1}/{max_attempts}): {str(e)}")
                    else:
                        print(f"{status.error} {func.__name__} failed after {max_attempts} attempts: {str(e)}")
            # If we get here, all attempts failed
            if last_exception is not None:
                raise last_exception
            raise Exception("Unknown error in with_retry")
        return wrapper
    return decorator


def timed_operation(operation_name: str = "") -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator for timing operations with clear status indicators.
    
    Args:
        operation_name: Human-readable name for the operation
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            name = operation_name or func.__name__
            print(f"{status.running} Starting {name}...")
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                end_time = time.time()
                duration = end_time - start_time
                print(f"{status.success} {name} completed in {duration:.2f}s")
                return result
            except Exception as e:
                end_time = time.time()
                duration = end_time - start_time
                print(f"{status.error} {name} failed after {duration:.2f}s: {str(e)}")
                raise
        return wrapper
    return decorator


def status_report(
    task: str,
    success: bool,
    duration: float | None = None,
    details: str | None = None,
    level: str = "INFO"
) -> None:
    """
    Generate a standardized status report.
    
    Args:
        task: Name of the task
        success: Whether the task succeeded
        duration: Optional duration in seconds
        details: Optional additional details
        level: Log level (INFO, WARNING, ERROR)
    """
    if success:
        indicator = status.success
        status_text = "COMPLETED"
    else:
        indicator = status.error
        status_text = "FAILED"
    
    message = f"{indicator} {task} {status_text}"
    
    if duration is not None:
        message += f" ({duration:.2f}s)"
    
    if details:
        message += f" - {details}"
    
    # Log and print
    print(message)
    if level == "ERROR":
        logging.error(message)
    elif level == "WARNING":
        logging.warning(message)
    else:
        logging.info(message)


class ProgressTracker:
    """Track progress of multi-step operations."""
    
    def __init__(self, total_steps: int, operation_name: str = "Operation"):
        self.total_steps = total_steps
        self.current_step = 0
        self.operation_name = operation_name
        self.start_time = time.time()
        self.step_times: list[float] = []
    
    def step(self, step_name: str = "") -> None:
        """Mark completion of a step."""
        self.current_step += 1
        step_time = time.time()
        self.step_times.append(step_time)
        
        if step_name:
            step_display = f": {step_name}"
        else:
            step_display = ""
        
        percentage = (self.current_step / self.total_steps) * 100
        elapsed = step_time - self.start_time
        
        if self.current_step > 1:
            avg_step_time = elapsed / self.current_step
            eta = avg_step_time * (self.total_steps - self.current_step)
            eta_text = f", ETA: {eta:.1f}s"
        else:
            eta_text = ""
        
        print(f"{status.running} {self.operation_name} [{self.current_step}/{self.total_steps}] "
              f"({percentage:.1f}%){step_display} - {elapsed:.1f}s elapsed{eta_text}")
    
    def complete(self) -> None:
        """Mark operation as complete."""
        total_time = time.time() - self.start_time
        print(f"{status.success} {self.operation_name} completed! "
              f"({self.total_steps} steps in {total_time:.2f}s)")


def safe_execute(
    func: Callable[..., Any],
    error_message: str = "Operation failed",
    success_message: str = "Operation completed",
    **kwargs: Any
) -> tuple[bool, Any]:
    """
    Safely execute a function with error handling and status reporting.
    
    Returns:
        Tuple of (success: bool, result: Any)
    """
    try:
        result = func(**kwargs)
        status_report(success_message, True)
        return True, result
    except Exception as e:
        status_report(error_message, False, details=str(e), level="ERROR")
        return False, None


def platform_info() -> dict[str, str]:
    """Get platform information for debugging."""
    return {
        "platform": platform.system(),
        "platform_version": platform.version(),
        "python_version": platform.python_version(),
        "encoding": sys.stdout.encoding if hasattr(sys.stdout, 'encoding') else 'unknown',
        "unicode_support": str(StatusIndicator().supports_unicode),
    }


if __name__ == "__main__":
    # Demo the status indicators
    print("🔍 Testing cross-platform status indicators...")
    print()
    
    info = platform_info()
    print("Platform Information:")
    for key, value in info.items():
        print(f"  {key}: {value}")
    print()
    
    print("Status Indicators:")
    print(f"  Success: {status.success}")
    print(f"  Error: {status.error}")
    print(f"  Warning: {status.warning}")
    print(f"  Info: {status.info}")
    print(f"  Running: {status.running}")
    print(f"  Timer: {status.timer}")
    print()
    
    # Demo progress tracker
    tracker = ProgressTracker(3, "Demo Operation")
    time.sleep(0.5)
    tracker.step("Step 1")
    time.sleep(0.3)
    tracker.step("Step 2")
    time.sleep(0.2)
    tracker.step("Step 3")
    tracker.complete()
    print()
    
    # Demo retry mechanism
    @with_retry(max_attempts=2, delay=0.1)
    def flaky_function(should_fail: bool = False):
        if should_fail:
            raise ValueError("Simulated failure")
        return "Success!"
    
    print("Testing retry mechanism:")
    result = flaky_function(False)
    print(f"{status.success} Result: {result}")
    
    try:
        flaky_function(True)
    except ValueError:
        print(f"{status.info} Retry demo completed")
