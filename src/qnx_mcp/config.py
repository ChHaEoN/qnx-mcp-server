"""A single developer-selected target profile, bound for the process lifetime."""

from pathlib import Path, PurePosixPath
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .policy import DENIED_ROOTS, remote_path


class UtilityPaths(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    uname: str = "/system/bin/uname"
    pidin: str = "/proc/boot/pidin"
    slog2info: str = "/proc/boot/slog2info"

    @field_validator("*")
    @classmethod
    def absolute_utility(cls, value: str) -> str:
        path = remote_path(value)
        if path == PurePosixPath("/") or len(value) > 256:
            raise ValueError("Expected a short absolute utility path")
        return str(path)


class TargetProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    target_id: str = Field(default="qemu", pattern=r"^[A-Za-z0-9_.-]{1,64}$")
    host: str = Field(default="127.0.0.1", pattern=r"^[A-Za-z0-9:][A-Za-z0-9_.:-]{0,252}$")
    port: int = Field(default=22222, ge=1, le=65535)
    user: str = Field(default="qnxuser", pattern=r"^[A-Za-z_][A-Za-z0-9_.-]{0,63}$")
    key_path: str = Field(default="~/.config/qnx-mcp/qemu/client_ed25519", min_length=1)
    known_hosts: str = Field(default="~/.config/qnx-mcp/qemu/known_hosts", min_length=1)
    arch: Literal["x86_64", "aarch64"] = "x86_64"
    read_roots: Annotated[tuple[str, ...], Field(min_length=1, max_length=16)] = (
        "/data/home/qnxuser/qnx-mcp-demo",
    )
    utilities: UtilityPaths = Field(default_factory=UtilityPaths)

    @field_validator("user")
    @classmethod
    def non_root_login(cls, value: str) -> str:
        if value.lower() == "root":
            raise ValueError("Use a dedicated non-root SSH account")
        return value

    @field_validator("read_roots", mode="before")
    @classmethod
    def roots_from_yaml(cls, value: object) -> object:
        return tuple(value) if isinstance(value, list) else value

    @field_validator("read_roots")
    @classmethod
    def narrow_roots(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        roots = tuple(remote_path(x) for x in values)
        if any(
            len(p.parts) < 2
            or len(str(p)) > 1024
            or any(p.is_relative_to(denied) for denied in DENIED_ROOTS)
            for p in roots
        ):
            raise ValueError("Use application directories; /, /dev and /proc are forbidden")
        return tuple(str(p) for p in roots)

    def local_paths(self, directory: Path) -> "TargetProfile":
        def absolute(value: str) -> str:
            path = Path(value).expanduser()
            return str(path if path.is_absolute() else directory / path)

        return self.model_copy(
            update={"key_path": absolute(self.key_path), "known_hosts": absolute(self.known_hosts)}
        )


class ProfileLoader(yaml.SafeLoader):
    def compose_node(self, parent, index):
        if self.check_event(yaml.AliasEvent):
            raise ValueError("YAML aliases are not allowed in target profiles")
        return super().compose_node(parent, index)

    def construct_mapping(self, node, deep=False):
        mapping = super().construct_mapping(node, deep=deep)
        if len(mapping) != len(node.value):
            raise ValueError("Duplicate keys are not allowed in target profiles")
        return mapping


def load_profile(path: Path | None) -> TargetProfile:
    if path is None:
        return TargetProfile().local_paths(Path.cwd())
    path = path.expanduser().resolve()
    with path.open("rb") as source:
        raw = source.read(65_537)
    if len(raw) > 65_536:
        raise ValueError("Target profile exceeds 64 KiB")
    return TargetProfile.model_validate(yaml.load(raw, Loader=ProfileLoader)).local_paths(
        path.parent
    )
