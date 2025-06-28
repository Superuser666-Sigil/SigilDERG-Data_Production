"""Tests for the GitHub token checker module."""

import pytest
import os
from unittest.mock import Mock, patch, call
import builtins

from rust_crate_pipeline.github_token_checker import (
    check_github_token_quick,
    prompt_for_token_setup,
    check_and_setup_github_token
)


class TestCheckGithubTokenQuick:
    """Test quick GitHub token checking."""
    
    def test_no_token_set(self):
        """Test when no token is set."""
        with patch.dict(os.environ, {}, clear=True):
            result = check_github_token_quick()
            assert result[0] is False
            assert "not set" in result[1]
    
    def test_token_too_short(self):
        """Test when token is too short."""
        with patch.dict(os.environ, {'GITHUB_TOKEN': 'short'}):
            result = check_github_token_quick()
            assert result[0] is False
            assert "too short" in result[1]
    
    @patch('requests.get')
    def test_valid_token_success(self, mock_get):
        """Test valid token with successful API call."""
        with patch.dict(os.environ, {'GITHUB_TOKEN': 'valid_token_123456789'}):
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "resources": {"core": {"remaining": 5000}}
            }
            mock_get.return_value = mock_response
            
            result = check_github_token_quick()
            assert result[0] is True
            assert "remaining" in result[1]
            mock_get.assert_called_once()
    
    @patch('requests.get')
    def test_invalid_token_401(self, mock_get):
        """Test invalid token with 401 response."""
        with patch.dict(os.environ, {'GITHUB_TOKEN': 'invalid_token_123456789'}):
            mock_response = Mock()
            mock_response.status_code = 401
            mock_get.return_value = mock_response
            
            result = check_github_token_quick()
            assert result[0] is False
            assert "invalid" in result[1]
    
    @patch('requests.get')
    def test_api_error_other_status(self, mock_get):
        """Test API error with other status code."""
        with patch.dict(os.environ, {'GITHUB_TOKEN': 'valid_token_123456789'}):
            mock_response = Mock()
            mock_response.status_code = 500
            mock_get.return_value = mock_response
            
            result = check_github_token_quick()
            assert result[0] is False
            assert "status code" in result[1]
    
    @patch('requests.get')
    def test_requests_exception(self, mock_get):
        """Test requests exception."""
        with patch.dict(os.environ, {'GITHUB_TOKEN': 'valid_token_123456789'}):
            mock_get.side_effect = Exception("Network error")
            
            result = check_github_token_quick()
            assert result[0] is False
            assert "Error checking token" in result[1]
    
    @patch('requests.get')
    def test_general_exception(self, mock_get):
        """Test general exception."""
        with patch.dict(os.environ, {'GITHUB_TOKEN': 'valid_token_123456789'}):
            mock_get.side_effect = ValueError("Unexpected error")
            
            result = check_github_token_quick()
            assert result[0] is False
            assert "Error checking token" in result[1]


class TestPromptForTokenSetup:
    """Test token setup prompting."""
    
    @patch('builtins.input', return_value='y')
    @patch('builtins.print')
    def test_user_continues_with_y(self, mock_print, mock_input):
        """Test user continues with 'y'."""
        result = prompt_for_token_setup()
        assert result is True
        mock_input.assert_called_once()
        mock_print.assert_called()
    
    @patch('builtins.input', return_value='yes')
    @patch('builtins.print')
    def test_user_continues_with_yes(self, mock_print, mock_input):
        """Test user continues with 'yes'."""
        result = prompt_for_token_setup()
        assert result is True
    
    @patch('builtins.input', return_value='n')
    @patch('builtins.print')
    def test_user_declines_with_n(self, mock_print, mock_input):
        """Test user declines with 'n'."""
        result = prompt_for_token_setup()
        assert result is False
    
    @patch('builtins.input', return_value='no')
    @patch('builtins.print')
    def test_user_declines_with_no(self, mock_print, mock_input):
        """Test user declines with 'no'."""
        result = prompt_for_token_setup()
        assert result is False
    
    @patch('builtins.input', return_value='')
    @patch('builtins.print')
    def test_user_default_response(self, mock_print, mock_input):
        """Test user provides empty response (defaults to no)."""
        result = prompt_for_token_setup()
        assert result is False
    
    @patch('builtins.input', return_value='maybe')
    @patch('builtins.print')
    def test_user_random_response(self, mock_print, mock_input):
        """Test user provides random response (defaults to no)."""
        result = prompt_for_token_setup()
        assert result is False


class TestCheckAndSetupGithubToken:
    """Test token checking and setup."""
    
    @patch('rust_crate_pipeline.github_token_checker.check_github_token_quick')
    def test_valid_token_already_set(self, mock_check):
        """Test when valid token is already set."""
        mock_check.return_value = (True, "Token valid")
        
        result = check_and_setup_github_token()
        assert result is True
        mock_check.assert_called_once()
    
    @patch('rust_crate_pipeline.github_token_checker.check_github_token_quick')
    @patch('rust_crate_pipeline.github_token_checker.prompt_for_token_setup')
    @patch('builtins.print')
    @patch('sys.stdin.isatty', return_value=True)
    def test_invalid_token_interactive_setup(self, mock_isatty, mock_print, mock_prompt, mock_check):
        """Test invalid token with interactive setup."""
        mock_check.return_value = (False, "Token invalid")
        mock_prompt.return_value = True
        
        result = check_and_setup_github_token()
        assert result is True
        mock_check.assert_called()
        mock_prompt.assert_called_once()
    
    @patch('rust_crate_pipeline.github_token_checker.check_github_token_quick')
    @patch('rust_crate_pipeline.github_token_checker.prompt_for_token_setup')
    @patch('builtins.print')
    def test_invalid_token_user_declines_setup(self, mock_print, mock_prompt, mock_check):
        """Test invalid token when user declines setup."""
        mock_check.return_value = (False, "Token invalid")
        mock_prompt.return_value = False
        
        result = check_and_setup_github_token()
        assert result is False
    
    @patch('rust_crate_pipeline.github_token_checker.check_github_token_quick')
    @patch('builtins.print')
    def test_invalid_token_non_interactive(self, mock_print, mock_check):
        """Test invalid token in non-interactive mode."""
        mock_check.return_value = (False, "Token invalid")
        
        # Test in non-interactive environment
        with patch('sys.stdin.isatty', return_value=False):
            result = check_and_setup_github_token()
            assert result is False
            mock_print.assert_not_called()  # No print in non-interactive mode 