#!/usr/bin/env python3
"""
Comprehensive tests for rust_crate_pipeline.github_token_checker to achieve 100% coverage

This test suite covers all functions and edge cases in the github_token_checker module
to demonstrate Rule Zero validation principles.
"""

import os
import subprocess
import sys
from unittest.mock import Mock, patch

import pytest
import requests

from rust_crate_pipeline.github_token_checker import (
    check_and_setup_github_token,
    check_github_token_quick,
    prompt_for_token_setup,
)


class TestCheckGithubTokenQuick:
    """Test check_github_token_quick function comprehensively"""

    @patch.dict(os.environ, {}, clear=True)
    def test_no_token_set(self):
        """Test when GITHUB_TOKEN environment variable is not set"""
        is_valid, message = check_github_token_quick()
        assert is_valid is False
        assert message == "GITHUB_TOKEN environment variable not set"

    @patch.dict(os.environ, {"GITHUB_TOKEN": "short"})
    def test_token_too_short(self):
        """Test when GITHUB_TOKEN is too short (< 20 chars)"""
        is_valid, message = check_github_token_quick()
        assert is_valid is False
        assert message == "GITHUB_TOKEN seems too short - may be invalid"

    @patch.dict(
        os.environ,
        {"GITHUB_TOKEN": "ghp_1234567890123456789012345678901234567890"},
    )
    @patch("requests.get")
    def test_valid_token_success(self, mock_get):
        """Test successful token validation"""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "resources": {"core": {"remaining": 4500}}
        }
        mock_get.return_value = mock_response

        is_valid, message = check_github_token_quick()
        assert is_valid is True
        assert "Token valid, 4500 API calls remaining" in message

    @patch.dict(
        os.environ,
        {"GITHUB_TOKEN": "ghp_invalid_token_1234567890123456789012345"},
    )
    @patch("requests.get")
    def test_invalid_token_401(self, mock_get):
        """Test invalid token (401 response)"""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        is_valid, message = check_github_token_quick()
        assert is_valid is False
        assert message == "GitHub token is invalid or expired"

    @patch.dict(
        os.environ,
        {"GITHUB_TOKEN": "ghp_1234567890123456789012345678901234567890"},
    )
    @patch("requests.get")
    def test_api_error_other_status(self, mock_get):
        """Test API returning other error status codes"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        is_valid, message = check_github_token_quick()
        assert is_valid is False
        assert "GitHub API returned status code: 500" in message

    @patch.dict(
        os.environ,
        {"GITHUB_TOKEN": "ghp_1234567890123456789012345678901234567890"},
    )
    @patch("requests.get")
    def test_requests_exception(self, mock_get):
        """Test RequestException during API call"""
        mock_get.side_effect = requests.RequestException("Network error")

        is_valid, message = check_github_token_quick()
        assert is_valid is False
        assert "API request failed: Network error" in message

    @patch.dict(
        os.environ,
        {"GITHUB_TOKEN": "ghp_1234567890123456789012345678901234567890"},
    )
    @patch("requests.get")
    def test_general_exception(self, mock_get):
        """Test general Exception during processing"""
        mock_get.side_effect = Exception("Unexpected error")

        is_valid, message = check_github_token_quick()
        assert is_valid is False
        assert "Error checking token: Unexpected error" in message


class TestPromptForTokenSetup:
    """Test prompt_for_token_setup function comprehensively"""

    @patch("builtins.input", return_value="y")
    @patch("builtins.print")
    def test_user_continues_with_y(self, mock_print, mock_input):
        """Test user chooses to continue with 'y'"""
        result = prompt_for_token_setup()
        assert result is True

        # Verify the prompt was displayed
        mock_print.assert_called()
        print_calls = [call[0][0] for call in mock_print.call_args_list]
        assert any(
            "[KEY] GitHub Token Required" in call for call in print_calls
        )
        assert any(
            "[WARNING] Running with limited GitHub API access" in call
            for call in print_calls
        )

    @patch("builtins.input", return_value="yes")
    @patch("builtins.print")
    def test_user_continues_with_yes(self, mock_print, mock_input):
        """Test user chooses to continue with 'yes'"""
        result = prompt_for_token_setup()
        assert result is True

    @patch("builtins.input", return_value="n")
    @patch("builtins.print")
    def test_user_declines_with_n(self, mock_print, mock_input):
        """Test user chooses not to continue with 'n'"""
        result = prompt_for_token_setup()
        assert result is False

        # Verify the stop message was displayed
        print_calls = [call[0][0] for call in mock_print.call_args_list]
        assert any(
            "[STOP] Please set up your GitHub token" in call
            for call in print_calls
        )

    @patch("builtins.input", return_value="no")
    @patch("builtins.print")
    def test_user_declines_with_no(self, mock_print, mock_input):
        """Test user chooses not to continue with 'no'"""
        result = prompt_for_token_setup()
        assert result is False

    @patch("builtins.input", return_value="")
    @patch("builtins.print")
    def test_user_default_response(self, mock_print, mock_input):
        """Test user gives empty response (default to no)"""
        result = prompt_for_token_setup()
        assert result is False

    @patch("builtins.input", return_value="random")
    @patch("builtins.print")
    def test_user_random_response(self, mock_print, mock_input):
        """Test user gives random response (default to no)"""
        result = prompt_for_token_setup()
        assert result is False


class TestCheckAndSetupGithubToken:
    """Test check_and_setup_github_token function comprehensively"""

    @patch("rust_crate_pipeline.github_token_checker.check_github_token_quick")
    @patch("logging.debug")
    def test_valid_token_already_set(self, mock_debug, mock_check):
        """Test when token is already valid"""
        mock_check.return_value = (
            True,
            "Token valid, 5000 API calls remaining",
        )

        result = check_and_setup_github_token()
        assert result is True
        mock_debug.assert_called_once_with(
            "GitHub token check: Token valid, 5000 API calls remaining"
        )

    @patch("rust_crate_pipeline.github_token_checker.check_github_token_quick")
    @patch("rust_crate_pipeline.github_token_checker.prompt_for_token_setup")
    @patch("logging.warning")
    @patch("sys.stdin.isatty", return_value=True)  # Interactive environment
    def test_invalid_token_interactive_setup(
        self, mock_isatty, mock_warning, mock_prompt, mock_check
    ):
        """Test invalid token in interactive environment"""
        mock_check.return_value = (False, "Token is invalid")
        mock_prompt.return_value = True

        result = check_and_setup_github_token()
        assert result is True
        mock_warning.assert_called_once_with(
            "GitHub token issue: Token is invalid"
        )
        mock_prompt.assert_called_once()

    @patch("rust_crate_pipeline.github_token_checker.check_github_token_quick")
    @patch("rust_crate_pipeline.github_token_checker.prompt_for_token_setup")
    @patch("logging.warning")
    @patch("sys.stdin.isatty", return_value=True)
    def test_invalid_token_user_declines_setup(
        self, mock_isatty, mock_warning, mock_prompt, mock_check
    ):
        """Test invalid token when user declines setup"""
        mock_check.return_value = (False, "Token is invalid")
        mock_prompt.return_value = False

        result = check_and_setup_github_token()
        assert result is False
        mock_prompt.assert_called_once()

    @patch("rust_crate_pipeline.github_token_checker.check_github_token_quick")
    @patch("logging.warning")
    @patch("logging.error")
    @patch(
        "sys.stdin.isatty", return_value=False
    )  # Non-interactive environment
    def test_invalid_token_non_interactive(
        self, mock_isatty, mock_error, mock_warning, mock_check
    ):
        """Test invalid token in non-interactive environment"""
        mock_check.return_value = (
            False,
            "GITHUB_TOKEN environment variable not set",
        )

        result = check_and_setup_github_token()
        assert result is False

        mock_warning.assert_called_once_with(
            "GitHub token issue: GITHUB_TOKEN environment variable not set"
        )
        mock_error.assert_any_call(
            "GitHub token not configured and running in non-interactive mode"
        )
        mock_error.assert_any_call(
            "Set GITHUB_TOKEN environment variable before running"
        )


class TestMainModuleExecution:
    """Test the __main__ execution block to achieve 100% coverage"""

    def test_main_execution_valid_token(self):
        """Test __main__ execution with valid token"""
        # Create environment with a valid length token
        env = os.environ.copy()
        env["GITHUB_TOKEN"] = (
            "ghp_abcdef1234567890123456789012345678901234"  # Valid format/length
        )

        # Execute the module directly to trigger __main__ block
        result = subprocess.run(
            [sys.executable, "-m", "rust_crate_pipeline.github_token_checker"],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )

        # Should execute successfully (may be OK or FAIL depending on token validity, but no crashes)
        assert result.returncode == 0 or "Token check:" in result.stdout

    def test_main_execution_invalid_token_interactive(self):
        """Test __main__ execution with invalid token and user interaction"""
        # Create environment without GitHub token
        env = os.environ.copy()
        if "GITHUB_TOKEN" in env:
            del env["GITHUB_TOKEN"]

        # Execute the module directly to trigger __main__ block with input
        result = subprocess.run(
            [sys.executable, "-m", "rust_crate_pipeline.github_token_checker"],
            capture_output=True,
            text=True,
            input="n\n",
            timeout=30,
            env=env,
        )

        # Should execute without error even if setup is declined
        assert result.returncode == 0
        assert "Token check:" in result.stdout


if __name__ == "__main__":
    # Allow running this test directly
    pytest.main([__file__, "-v"])
