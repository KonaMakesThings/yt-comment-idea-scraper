import json
from unittest.mock import Mock, patch

import pytest

from yt_idea_collector.auth import (
    SCOPES,
    SHEETS_SCOPES,
    access_token_scopes,
    refresh_and_validate_scopes,
    validate_access_token_scopes,
)


@patch("yt_idea_collector.auth.validate_access_token_scopes")
@patch("yt_idea_collector.auth.Request")
def test_scope_validation_accepts_all_required_scopes(request, validate):
    creds = Mock()
    creds.token = "access-token"
    refresh_and_validate_scopes(creds)
    creds.refresh.assert_called_once_with(request.return_value)
    validate.assert_called_once_with("access-token", SCOPES)


@patch("yt_idea_collector.auth.access_token_scopes")
def test_scope_validation_explains_incomplete_refresh_token(scopes):
    scopes.return_value = {SCOPES[2]}
    with pytest.raises(RuntimeError, match="Revoke the app.*Missing scopes"):
        validate_access_token_scopes("access-token")


@patch("yt_idea_collector.auth.access_token_scopes")
def test_account_specific_validation_only_requires_requested_scopes(scopes):
    scopes.return_value = set(SHEETS_SCOPES)
    validate_access_token_scopes("business-token", SHEETS_SCOPES)


@patch("yt_idea_collector.auth.urlopen")
def test_access_token_scopes_uses_tokeninfo_response(urlopen):
    response = urlopen.return_value.__enter__.return_value
    response.read.return_value = json.dumps({"scope": "scope-a scope-b"}).encode()
    assert access_token_scopes("secret-access-token") == {"scope-a", "scope-b"}
    request = urlopen.call_args.args[0]
    assert request.full_url == "https://oauth2.googleapis.com/tokeninfo"
    assert b"secret-access-token" in request.data
