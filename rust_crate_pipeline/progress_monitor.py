# progress_monitor.py
"""
Real-time progress monitoring for the Rust Crate Pipeline (CLI-only).

This module provides:
- Live progress bars with ETA
- Real-time statistics and metrics
- Status printouts
- Performance monitoring
- Error tracking and reporting
- Status JSON file for external tools/scripts
"""

import json
import logging
import os
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


@dataclass
class PipelineMetrics:
    """Real-time pipeline metrics and statistics."""
    total_crates: int = 0
    processed_crates: int = 0
    successful_crates: int = 0
    failed_crates: int = 0
    skipped_crates: int = 0
    current_batch: int = 0
    total_batches: int = 0
    start_time: Optional[datetime] = None
    current_operation: str = "Initializing"
    errors: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[Dict[str, Any]] = field(default_factory=list)
    performance_stats: Dict[str, Any] = field(default_factory=dict)

    @property
    def progress_percentage(self) -> float:
        """Calculate progress percentage."""
        if self.total_crates == 0:
            return 0.0
        return (self.processed_crates / self.total_crates) * 100

    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.processed_crates == 0:
            return 0.0
        return (self.successful_crates / self.processed_crates) * 100

    @property
    def elapsed_time(self) -> timedelta:
        """Calculate elapsed time."""
        if not self.start_time:
            return timedelta(0)
        return datetime.now() - self.start_time

    @property
    def estimated_completion(self) -> Optional[datetime]:
        """Estimate completion time."""
        if self.processed_crates == 0 or not self.start_time:
            return None

        avg_time_per_crate = self.elapsed_time / self.processed_crates
        remaining_crates = self.total_crates - self.processed_crates
        estimated_remaining = avg_time_per_crate * remaining_crates

        return datetime.now() + estimated_remaining


class ProgressMonitor:
    """Real-time progress monitoring with live dashboard."""

    def __init__(self, total_crates: int, output_dir: str = "output"):
        self.metrics = PipelineMetrics(total_crates=total_crates)
        self.output_dir = output_dir
        self.logger = logging.getLogger(__name__)

        # Performance tracking
        # Last 100 crate processing times
        self.crate_times: deque = deque(maxlen=100)
        self.batch_times: deque = deque(
            maxlen=50)   # Last 50 batch processing times

        # Status tracking
        self.current_crate: Optional[str] = None
        self.current_operation: str = "Initializing"
        self.status_file = os.path.join(output_dir, "pipeline_status.json")

        # Thread safety
        self._lock = threading.Lock()

        # Initialize
        self.metrics.start_time = datetime.now()
        self._save_status()

        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

    def start_crate(self, crate_name: str) -> None:
        """Mark the start of processing a crate."""
        with self._lock:
            self.current_crate = crate_name
            self.current_operation = f"Processing {crate_name}"
            self.metrics.current_operation = self.current_operation
            self._save_status()

    def complete_crate(self, crate_name: str, success: bool = True,
                       processing_time: Optional[float] = None) -> None:
        """Mark the completion of processing a crate."""
        with self._lock:
            self.metrics.processed_crates += 1

            if success:
                self.metrics.successful_crates += 1
            else:
                self.metrics.failed_crates += 1

            if processing_time:
                self.crate_times.append(processing_time)

            self.current_crate = None
            self.current_operation = "Waiting for next crate"
            self.metrics.current_operation = self.current_operation

            # Update performance stats
            self._update_performance_stats()
            self._save_status()

    def skip_crate(self, crate_name: str, reason: str = "Unknown") -> None:
        """Mark a crate as skipped."""
        with self._lock:
            self.metrics.processed_crates += 1
            self.metrics.skipped_crates += 1

            self.metrics.warnings.append({
                "crate": crate_name,
                "reason": reason,
                "timestamp": datetime.now().isoformat()
            })

            self._save_status()

    def start_batch(self, batch_num: int, batch_size: int) -> None:
        """Mark the start of processing a batch."""
        with self._lock:
            self.metrics.current_batch = batch_num
            self.current_operation = f"Processing batch {batch_num}"
            self.metrics.current_operation = self.current_operation
            self._save_status()

    def complete_batch(
            self,
            batch_num: int,
            processing_time: Optional[float] = None) -> None:
        """Mark the completion of processing a batch."""
        with self._lock:
            if processing_time:
                self.batch_times.append(processing_time)

            self.current_operation = "Batch completed, preparing next batch"
            self.metrics.current_operation = self.current_operation
            self._save_status()

    def add_error(self, crate_name: str, error: str,
                  error_type: str = "Processing") -> None:
        """Add an error to the metrics."""
        with self._lock:
            self.metrics.errors.append({
                "crate": crate_name,
                "error": error,
                "type": error_type,
                "timestamp": datetime.now().isoformat()
            })
            self._save_status()

    def add_warning(self, crate_name: str, warning: str) -> None:
        """Add a warning to the metrics."""
        with self._lock:
            self.metrics.warnings.append({
                "crate": crate_name,
                "warning": warning,
                "timestamp": datetime.now().isoformat()
            })
            self._save_status()

    def update_operation(self, operation: str) -> None:
        """Update the current operation description."""
        with self._lock:
            self.current_operation = operation
            self.metrics.current_operation = operation
            self._save_status()

    def _update_performance_stats(self) -> None:
        """Update performance statistics."""
        if self.crate_times:
            self.metrics.performance_stats.update({
                "avg_crate_time": sum(self.crate_times) / len(self.crate_times),
                "min_crate_time": min(self.crate_times),
                "max_crate_time": max(self.crate_times),
                "crates_per_minute": len(self.crate_times) / (sum(self.crate_times) / 60)
            })

        if self.batch_times:
            self.metrics.performance_stats.update({
                "avg_batch_time": sum(self.batch_times) / len(self.batch_times),
                "min_batch_time": min(self.batch_times),
                "max_batch_time": max(self.batch_times)
            })

        # System stats if available
        if PSUTIL_AVAILABLE:
            try:
                cpu_percent = psutil.cpu_percent()
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage(self.output_dir)

                self.metrics.performance_stats.update({
                    "system_cpu_percent": cpu_percent,
                    "system_memory_percent": memory.percent,
                    "system_disk_percent": disk.percent,
                    "system_memory_available": memory.available,
                    "system_disk_free": disk.free
                })
            except Exception as e:
                self.logger.warning(f"Failed to get system stats: {e}")

    def _save_status(self) -> None:
        """Save current status to file."""
        try:
            status_data = {
                "metrics": {
                    "total_crates": self.metrics.total_crates,
                    "processed_crates": self.metrics.processed_crates,
                    "successful_crates": self.metrics.successful_crates,
                    "failed_crates": self.metrics.failed_crates,
                    "skipped_crates": self.metrics.skipped_crates,
                    "progress_percentage": self.metrics.progress_percentage,
                    "success_rate": self.metrics.success_rate,
                    "current_batch": self.metrics.current_batch,
                    "total_batches": self.metrics.total_batches,
                    "start_time": self.metrics.start_time.isoformat() if self.metrics.start_time else None,
                    "elapsed_time": str(self.metrics.elapsed_time),
                    "estimated_completion": self.metrics.estimated_completion.isoformat() if self.metrics.estimated_completion else None,
                    "current_operation": self.metrics.current_operation
                },
                "current_crate": self.current_crate,
                "performance_stats": self.metrics.performance_stats,
                "errors": self.metrics.errors[-10:],  # Last 10 errors
                "warnings": self.metrics.warnings[-10:],  # Last 10 warnings
                "last_updated": datetime.now().isoformat()
            }

            with open(self.status_file, 'w') as f:
                json.dump(status_data, f, indent=2)

        except Exception as e:
            self.logger.error(f"Failed to save status: {e}")

    def get_status_summary(self) -> Dict[str, Any]:
        """Get a summary of current status."""
        with self._lock:
            return {
                "progress": f"{self.metrics.progress_percentage:.1f}%",
                "processed": f"{self.metrics.processed_crates}/{self.metrics.total_crates}",
                "success_rate": f"{self.metrics.success_rate:.1f}%",
                "elapsed_time": str(self.metrics.elapsed_time),
                "estimated_completion": self.metrics.estimated_completion.isoformat() if self.metrics.estimated_completion else None,
                "current_operation": self.current_operation,
                "current_crate": self.current_crate,
                "errors_count": len(self.metrics.errors),
                "warnings_count": len(self.metrics.warnings)
            }

    def print_status(self) -> None:
        """Print current status to console."""
        summary = self.get_status_summary()

        print("\n" + "=" * 80)
        print("🚀 RUST CRATE PIPELINE - REAL-TIME STATUS")
        print("=" * 80)
        print(
            f"📊 Progress: {
                summary['progress']} ({
                summary['processed']} crates)")
        print(f"✅ Success Rate: {summary['success_rate']}")
        print(f"⏱️  Elapsed Time: {summary['elapsed_time']}")
        if summary['estimated_completion']:
            print(f"🎯 Estimated Completion: {summary['estimated_completion']}")
        print(f"🔄 Current Operation: {summary['current_operation']}")
        if summary['current_crate']:
            print(f"📦 Current Crate: {summary['current_crate']}")
        print(f"❌ Errors: {summary['errors_count']}")
        print(f"⚠️  Warnings: {summary['warnings_count']}")

        # Performance stats
        if self.metrics.performance_stats:
            stats = self.metrics.performance_stats
            if 'avg_crate_time' in stats:
                print(f"⚡ Avg Crate Time: {stats['avg_crate_time']:.2f}s")
            if 'crates_per_minute' in stats:
                print(
                    f"🚀 Processing Rate: {
                        stats['crates_per_minute']:.1f} crates/min")
            if 'system_cpu_percent' in stats:
                print(f"💻 System CPU: {stats['system_cpu_percent']:.1f}%")
            if 'system_memory_percent' in stats:
                print(
                    f"🧠 System Memory: {
                        stats['system_memory_percent']:.1f}%")

        print("=" * 80)

    def create_progress_bar(
            self,
            desc: str = "Processing crates") -> Optional[Any]:
        """Create a progress bar if tqdm is available."""
        if not TQDM_AVAILABLE:
            return None

        return tqdm(
            total=self.metrics.total_crates,
            desc=desc,
            unit="crate",
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]"
        )


def create_monitor(
        total_crates: int,
        output_dir: str = "output") -> ProgressMonitor:
    """Create and configure a CLI-only progress monitor."""
    monitor = ProgressMonitor(total_crates, output_dir)
    print("✅ Real-time CLI progress monitoring enabled")
    return monitor
