from unittest.mock import Mock, patch

import pytest

from yt_idea_collector.auth import SCOPES, refresh_and_validate_scopes


@patch("yt_idea_collector.auth.Request")
def test_scope_validation_accepts_all_required_scopes(request):
    creds = Mock()
    creds.granted_scopes = list(SCOPES)
    refresh_and_validate_scopes(creds)
    creds.refresh.assert_called_once_with(request.return_value)


@patch("yt_idea_collector.auth.Request")
def test_scope_validation_explains_incomplete_refresh_token(request):
    creds = Mock()
    creds.granted_scopes = [SCOPES[2]]
    with pytest.raises(RuntimeError, match="GOOGLE_REFRESH_TOKEN.*yt-idea-oauth"):
        refresh_and_validate_scopes(creds)


@patch("yt_idea_collector.auth.Request")
def test_scope_validation_tolerates_token_endpoint_without_scope_echo(request):
    creds = Mock()
    creds.granted_scopes = None
    refresh_and_validate_scopes(creds)
