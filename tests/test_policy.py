from pathlib import Path

import pytest
from pydantic import ValidationError

from qnx_mcp.config import TargetProfile, load_profile
from qnx_mcp.errors import ToolFailure
from qnx_mcp.policy import require_read_path
from qnx_mcp.transport import Command, command_line


@pytest.mark.parametrize(
    "path",
    [
        "/data/demo-else/a",
        "/data/demo/../a",
        "/data/demo/a\x00",
        "/proc/boot/pidin",
        "relative.txt",
    ],
)
def test_read_path_lexical_denial(path):
    with pytest.raises(ToolFailure, match="path|directory"):
        require_read_path(path, ("/data/demo",))


def test_config_rejects_ambiguous_or_broad_policy(tmp_path: Path):
    profile = tmp_path / "invalid.yaml"
    profile.write_text("port: 22\nport: 22222\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate"):
        load_profile(profile)
    with pytest.raises(ValidationError, match="extra"):
        TargetProfile.model_validate({"enable_mutations": True})
    with pytest.raises(ValidationError, match="forbidden"):
        TargetProfile.model_validate({"read_roots": ["/proc"]})
    with pytest.raises(ValidationError, match="non-root"):
        TargetProfile(user="root")


def test_command_template_quotes_format_and_trusted_utility_path():
    p = TargetProfile.model_validate({"utilities": {"pidin": "/an absolute/command;name"}})
    assert command_line(p, Command.PROCESSES) == (
        "LC_ALL=C '/an absolute/command;name' -v -F '%a|%b|%p|%J|%80B|%n'"
    )
