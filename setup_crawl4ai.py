#!/usr/bin/env python3
"""
Quick setup and test script for Crawl4AI integration
Run this to install Crawl4AI and test basic functionality
"""

import subprocess
import sys


def install_crawl4ai():
    """Install Crawl4AI and its dependencies"""
    print("🔧 Installing Crawl4AI...")

    try:
        # Install Crawl4AI
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-U", "crawl4ai"]
        )

        # Post-installation setup (browser setup)
        subprocess.check_call(["crawl4ai-setup"])

        print("[SUCCESS] Crawl4AI installed successfully!")
        return True

    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Installation failed: {e}")
        return False


def test_basic_crawling():
    """Test basic Crawl4AI functionality"""
    print("\n🧪 Testing basic Crawl4AI functionality...")

    test_code = """
import asyncio
from crawl4ai import AsyncWebCrawler

async def test_crawl():
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url="https://crates.io/crates/serde")

        if result.success:
            print("[SUCCESS] Basic crawling works!")
            print(f"Page title: {result.metadata.get('title', 'N/A')}")
            print(f"Content length: {len(result.markdown)} characters")
            return True
        else:
            print("[ERROR] Basic crawling failed")
            return False

if __name__ == "__main__":
    success = asyncio.run(test_crawl())
    sys.exit(0 if success else 1)
"""

    try:
        # Write test to temporary file and execute
        with open("temp_crawl_test.py", "w") as f:
            f.write(test_code)

        result = subprocess.run(
            [sys.executable, "temp_crawl_test.py"],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode == 0:
            print(result.stdout)
            return True
        else:
            print(f"[ERROR] Test failed: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        print("[ERROR] Test timed out")
        return False
    except Exception as e:
        print(f"[ERROR] Test error: {e}")
        return False
    finally:
        # Cleanup
        try:
            import os

            os.remove("temp_crawl_test.py")
        except BaseException:
            pass


def test_ollama_connection():
    """Test connection to local Ollama instance"""
    print("\n🔗 Testing Ollama connection...")

    try:
        import requests

        response = requests.get("http://localhost:11434/api/tags", timeout=5)

        if response.ok:
            models = response.json().get("models", [])
            print(f"[SUCCESS] Ollama connected! Found {len(models)} models:")
            for model in models[:3]:  # Show first 3 models
                print(f"   - {model.get('name', 'unknown')}")
            return True
        else:
            print("[ERROR] Ollama not responding properly")
            return False

    except requests.exceptions.ConnectionError:
        print("[ERROR] Ollama not running or not accessible at localhost:11434")
        print("   Make sure Ollama is installed and running:")
        print("   1. Install Ollama from https://ollama.ai/")
        print("   2. Run: ollama serve")
        print("   3. Pull your model: ollama pull deepseek-coder:6.7b")
        return False
    except Exception as e:
        print(f"[ERROR] Ollama connection error: {e}")
        return False


def create_requirements_file():
    """Create requirements file for Crawl4AI integration"""
    print("\n📝 Creating requirements file...")

    requirements = """# Crawl4AI Integration Requirements
crawl4ai>=0.6.0
asyncio
aiohttp
beautifulsoup4
lxml
selenium
playwright
requests
"""

    try:
        with open("requirements-crawl4ai.txt", "w") as f:
            f.write(requirements)
        print("[SUCCESS] Created requirements-crawl4ai.txt")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to create requirements file: {e}")
        return False


def main():
    """Main setup and test function"""
    print("[SETUP] Crawl4AI Integration Setup for Rust Crate Pipeline")
    print("=" * 60)

    success_count = 0
    total_tests = 4

    # Step 1: Install Crawl4AI
    if install_crawl4ai():
        success_count += 1

    # Step 2: Test basic functionality
    if test_basic_crawling():
        success_count += 1

    # Step 3: Test Ollama connection
    if test_ollama_connection():
        success_count += 1

    # Step 4: Create requirements file
    if create_requirements_file():
        success_count += 1

    print(f"\n📊 Setup Results: {success_count}/{total_tests} successful")

    if success_count == total_tests:
        print("\n[SUCCESS] All setup steps completed successfully!")
        print("\nNext steps:")
        print("1. Review the integration plan: CRAWL4AI_INTEGRATION_PLAN.md")
        print("2. Test the starter script: python crawl4ai_integration_starter.py")
        print("3. Begin integrating with your existing pipeline")
    else:
        print("\n⚠️  Some setup steps failed. Please review the errors above.")
        print("Common issues:")
        print("- Browser setup: Run 'python -m playwright install chromium'")
        print("- Ollama setup: Make sure Ollama is running locally")
        print("- Network access: Check firewall and proxy settings")


if __name__ == "__main__":
    main()
