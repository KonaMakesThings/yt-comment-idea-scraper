import sys
from unittest.mock import patch

from yt_idea_collector import cli


def test_main_withholds_exception_details_from_public_logs(capsys):
    with patch.object(sys, "argv", ["yt-idea-collector"]), patch.object(
        cli, "run", side_effect=RuntimeError("private-resource-id")
    ):
        assert cli.main() == 1

    captured = capsys.readouterr()
    assert "RuntimeError" in captured.err
    assert "private-resource-id" not in captured.err
