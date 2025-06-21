#!/usr/bin/env python3
"""
Production launcher for the Rust Crate Pipeline with optimized settings.
This script runs the pipeline with settings designed to minimize runtime warnings.
"""

import os
import sys
import subprocess


def main():
    """Launch the pipeline with production optimizations"""

    print("🚀 Starting Rust Crate Pipeline in Production Mode")
    print("   - Reduced logging verbosity")
    print("   - Optimized retry counts")
    print("   - Enhanced error handling")
    print("   - GitHub token verification")
    print()

    # Set production environment variables
    env = os.environ.copy()
    env["PRODUCTION"] = "true"
    env["PYTHONWARNINGS"] = "ignore::UserWarning"

    # Quick check for GitHub token before launching
    if not env.get("GITHUB_TOKEN"):
        print("⚠️  GITHUB_TOKEN not found in environment")
        print("   The pipeline will check and prompt for setup if needed.")
        print()

    # Build the command - use python3 for Linux
    cmd = ["python3", "-m", "rust_crate_pipeline"] + sys.argv[1:]

    try:
        # Run the pipeline
        result = subprocess.run(cmd, env=env, check=True)
        print("\n✅ Pipeline completed successfully!")
        return result.returncode

    except subprocess.CalledProcessError as e:
        print(f"\n❌ Pipeline failed with exit code {e.returncode}")
        return e.returncode
    except KeyboardInterrupt:
        print("\n🛑 Pipeline interrupted by user")
        return 130
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
