import os
import sys
import subprocess


def main() -> None:
    print("🚀 Starting Rust Crate Pipeline in Production Mode")
    print("   - Reduced logging verbosity")
    print("   - Optimized retry counts")
    print("   - Enhanced error handling")
    print("   - GitHub token verification")
    print()

    env = os.environ.copy()
    env["PRODUCTION"] = "true"
    env["PYTHONWARNINGS"] = "ignore::UserWarning"

    if not env.get("GITHUB_TOKEN"):
        print("⚠️  GITHUB_TOKEN not found in environment")
        print("   The pipeline will check and prompt for setup if needed.")
        print()

    # Use the unified LLM pipeline with intelligent routing
    cmd = [
        "python", "run_pipeline_with_llm.py",
        "--llm-provider", "azure",
        "--llm-model", "gpt-4o",
        "--crates-file", "rust_crate_pipeline/crate_list.txt",
        "--batch-size", "3",
        "--verbose"
    ] + sys.argv[1:]

    try:
        result = subprocess.run(cmd, env=env, check=True)
        print("\n✅ Pipeline completed successfully!")
        sys.exit(result.returncode)

    except subprocess.CalledProcessError as e:
        print(f"\n❌ Pipeline failed with exit code {e.returncode}")
        sys.exit(e.returncode)
    except KeyboardInterrupt:
        print("\n🛑 Pipeline interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
