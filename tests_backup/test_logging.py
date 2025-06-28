from typing import Dict, List, Tuple, Optional, Any
#!/usr/bin/env python3
"""Test script to verify logging is working correctly"""


def test_logging() -> None:
    """Test that logging works to both console and file"""

    print("🔍 Testing logging configuration...")

    try:
        from rust_crate_pipeline.main import configure_logging

        configure_logging("INFO")

        import logging
        import os

        # Test messages
        logging.info("✅ INFO message - logging is working!")
        logging.warning("⚠️  WARNING message test")
        logging.error("❌ ERROR message test")
        logging.debug("🐛 DEBUG message (may not appear in console)")

        # Check if log file was created
        log_files = [
            f
            for f in os.listdir(".")
            if f.startswith("crate_enrichment_") and f.endswith(".log")
        ]

        assert log_files, "No log file found - logging setup failed"

        latest_log = max(log_files, key=lambda x: os.path.getctime(x))
        file_size = os.path.getsize(latest_log)

        print(f"📄 Log file created: {latest_log}")
        print(f"📏 Log file size: {file_size} bytes")

        assert file_size > 0, "Log file is empty - there's still an issue"

        print("✅ Log file has content - logging is working!")

        # Show last few lines of log file
        print("\n📖 Last few lines of log file:")
        with open(latest_log, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in lines[-5:]:
                print(f"   {line.strip()}")
    except ImportError as e:
        print(f"❌ Required module missing: {e}")
        assert False, f"Required module missing: {e}"
    except FileNotFoundError as e:
        print(f"❌ Required file missing: {e}")
        assert False, f"Required file missing: {e}"
    except Exception as e:
        print(f"❌ Logging test failed: {e}")
        assert False, f"Unexpected error: {e}"


if __name__ == "__main__":
    test_logging()
