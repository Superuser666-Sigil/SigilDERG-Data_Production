"""
Test for Rule Zero lookup table generation and rigor compliance.
Ensures environment metadata and policies are present and valid in the lookup table.
"""

import json
import os
import subprocess

import pytest

LOOKUP_PATH = os.path.abspath("rule_zero_lookup.json")
SCRIPT_PATH = os.path.abspath(os.path.join("scripts", "generate_rule_zero_lookup.py"))


@pytest.mark.order(1)
def test_generate_rule_zero_lookup_runs():
    """Script runs without error and produces a JSON file."""
    result = subprocess.run(["python", SCRIPT_PATH], capture_output=True, text=True)
    assert result.returncode == 0, f"Script failed: {result.stdout}\n{result.stderr}"
    assert os.path.exists(LOOKUP_PATH), "Lookup table was not generated."


@pytest.mark.order(2)
def test_lookup_table_json_valid():
    """Lookup table is valid JSON and has required keys."""
    with open(LOOKUP_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert (
        "environment_metadata" in data
    ), "Missing environment_metadata in lookup table."
    assert isinstance(
        data["environment_metadata"], list
    ), "environment_metadata should be a list."
    assert "rule_zero_policies" in data, "Missing rule_zero_policies in lookup table."
    assert isinstance(
        data["rule_zero_policies"], list
    ), "rule_zero_policies should be a list."


@pytest.mark.order(3)
def test_environment_metadata_content():
    """At least one environment metadata entry is present and well-formed."""
    with open(LOOKUP_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["environment_metadata"], "No environment metadata found."
    entry = data["environment_metadata"][0]
    required_fields = [
        "label",
        "os_name",
        "os_version",
        "system_type",
        "enforcement_rank",
        "timestamp",
    ]
    for field in required_fields:
        assert field in entry, f"Missing field in environment metadata: {field}"


@pytest.mark.order(4)
def test_rule_zero_policy_content():
    """If any policies exist, they must have required fields and valid JSON."""
    with open(LOOKUP_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    for policy in data["rule_zero_policies"]:
        for field in [
            "policy_name",
            "policy_type",
            "description",
            "policy_json",
            "enforcement_rank",
            "last_updated",
        ]:
            assert field in policy, f"Missing field in policy: {field}"
        # policy_json must be valid JSON
        try:
            json.loads(policy["policy_json"])
        except Exception as e:
            pytest.fail(f"policy_json is not valid JSON: {e}")
