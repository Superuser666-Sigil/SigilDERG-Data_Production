import subprocess
from pathlib import Path

log_path = Path("rule_zero_validation.log")

commands = [
    ["black", "tests/"],
    ["isort", "tests/"],
    ["ruff", "check", "tests/", "--fix"],
    ["autopep8", "--in-place", "--recursive", "tests/"],
    ["pyupgrade", "--py38-plus", "tests/**/*.py"],
    ["flake8", "tests/"],
    ["pylint", "tests/"],
    ["python", "dev-scripts/dmypy_manager_v3.py"],
    ["pytest", "--cov=."]
]

def run_and_log(cmd):
    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"\nRunning: {' '.join(cmd)}\n")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, shell=False)
            log.write(result.stdout)
            log.write(result.stderr)
            log.write("\n---\n")
        except Exception as e:
            log.write(f"ERROR: {e}\n---\n")

# Clear previous log
if log_path.exists():
    log_path.unlink()

for cmd in commands:
    run_and_log(cmd)

with log_path.open("a", encoding="utf-8") as log:
    log.write("Rule Zero validation complete.\n")
