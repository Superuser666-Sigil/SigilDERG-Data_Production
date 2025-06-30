import os
import subprocess
from typing import Any, Dict

import toml


class CrateAnalyzer:
    def __init__(self, crate_source_path: str):
        self.crate_source_path = crate_source_path

    def run_cargo_cmd(self, cmd, timeout=600) -> Dict[str, Any]:
        try:
            result = subprocess.run(
                cmd,
                cwd=self.crate_source_path,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return {
                "cmd": " ".join(cmd),
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except Exception as e:
            return {"cmd": " ".join(cmd), "error": str(e)}

    def analyze(self) -> Dict[str, Any]:
        results = {}
        # Build & test
        results["build"] = self.run_cargo_cmd(
            ["cargo", "+stable", "build", "--all-features"])
        results["test"] = self.run_cargo_cmd(
            ["cargo", "+stable", "test", "--all-features"])
        # Lint & format
        results["clippy"] = self.run_cargo_cmd(
            ["cargo", "+stable", "clippy", "--all-features", "--", "-D", "warnings"])
        results["fmt"] = self.run_cargo_cmd(["cargo", "+stable", "fmt", "--", "--check"])
        # Security
        results["audit"] = self.run_cargo_cmd(["cargo", "+stable", "audit"])
        # Dependency graph
        results["tree"] = self.run_cargo_cmd(["cargo", "+stable", "tree"])
        # Documentation
        results["doc"] = self.run_cargo_cmd(["cargo", "+stable", "doc", "--no-deps"])
        # Provenance
        vcs_info_path = os.path.join(
            self.crate_source_path,
            ".cargo_vcs_info.json")
        if os.path.exists(vcs_info_path):
            with open(vcs_info_path) as f:
                results["vcs_info"] = f.read()
        # Metadata
        cargo_toml = os.path.join(self.crate_source_path, "Cargo.toml")
        if os.path.exists(cargo_toml):
            with open(cargo_toml) as f:
                results["metadata"] = toml.load(f)
        return results
