import pytest
from rust_crate_pipeline.utils.sanitization import Sanitizer

@pytest.fixture(scope="module")
def sanitizer():
    """Provides a Sanitizer instance for the tests."""
    return Sanitizer()

def test_sanitize_text_pii(sanitizer):
    """Tests that PII is correctly identified and redacted from text."""
    text = "My name is John Doe and my email is john.doe@example.com. Call me at 123-456-7890."
    sanitized_text = sanitizer.sanitize_text(text)
    print("Sanitized PII text:", sanitized_text)
    assert "John Doe" not in sanitized_text
    assert "john.doe@example.com" not in sanitized_text
    assert "123-456-7890" not in sanitized_text

def test_sanitize_text_secrets(sanitizer):
    """Tests that secrets and API keys are redacted."""
    text = "Here is my api_key = 'supersecretkey123' and my aws key is AKIAIOSFODNN7EXAMPLE"
    sanitized_text = sanitizer.sanitize_text(text)
    print("Sanitized secrets text:", sanitized_text)
    assert "supersecretkey123" not in sanitized_text
    assert "AKIAIOSFODNN7EXAMPLE" not in sanitized_text

def test_sanitize_data_recursive(sanitizer):
    """Tests recursive sanitization of nested data structures."""
    data = {
        "user": {
            "name": "Jane Smith",
            "contact": "jane.smith@email.com"
        },
        "config": {
            "github_token": "ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ1234567890"
        },
        "logs": [
            "User Jane Smith accessed the system.",
            "API Key: a_very_secret_key_string"
        ]
    }
    sanitized_data = sanitizer.sanitize_data(data)
    print("Sanitized recursive data:", sanitized_data)
    
    # Check that original PII/secrets are gone
    assert "Jane Smith" not in sanitized_data["user"]["name"]
    assert "jane.smith@email.com" not in sanitized_data["user"]["contact"]
    assert "ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ1234567890" not in sanitized_data["config"]["github_token"]
    assert "Jane Smith" not in sanitized_data["logs"][0]
    assert "a_very_secret_key_string" not in sanitized_data["logs"][1] 