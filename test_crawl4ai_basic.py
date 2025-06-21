#!/usr/bin/env python3
"""Simple Crawl4AI test"""

try:
    import crawl4ai

    print("✅ Crawl4AI imported successfully")
    print(f"Version: {crawl4ai.__version__}")


    print("✅ AsyncWebCrawler imported successfully")

    print("✅ All basic imports successful")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback

    traceback.print_exc()
