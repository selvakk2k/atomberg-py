"""Tests for authentication handlers."""

import pytest
from pyatomberg.auth.cognito import CognitoOAuthHandler, generate_pkce_pair
from pyatomberg.auth.developer import DeveloperTokenHandler
from pyatomberg.exceptions import AtombergAuthError


def test_developer_token_validation():
    """Verify empty developer refresh token raises AtombergAuthError."""
    with pytest.raises(AtombergAuthError, match="cannot be empty"):
        DeveloperTokenHandler("")

    handler = DeveloperTokenHandler("sample_refresh_token_123")
    assert handler.refresh_token == "sample_refresh_token_123"
    assert handler.has_valid_access_token is False


def test_pkce_generation():
    """Verify PKCE code_verifier and code_challenge format."""
    verifier, challenge = generate_pkce_pair()
    assert len(verifier) >= 43
    assert len(challenge) >= 43
    # Check urlsafe base64
    assert not any(c in verifier for c in "+/=")
    assert not any(c in challenge for c in "+/=")


def test_cognito_authorization_url():
    """Verify Cognito authorization URL generation with PKCE and state."""
    handler = CognitoOAuthHandler(
        client_id="test_client_id",
        redirect_uri="http://localhost:8080/callback",
    )
    url, state, verifier = handler.get_authorization_url(identity_provider="Google")

    assert "https://auth.atomberg-iot.com/oauth2/authorize" in url
    assert "client_id=test_client_id" in url
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A8080%2Fcallback" in url
    assert "response_type=code" in url
    assert "code_challenge_method=S256" in url
    assert "identity_provider=Google" in url
    assert f"state={state}" in url
    assert len(verifier) >= 43
