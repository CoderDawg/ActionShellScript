from __future__ import annotations

from dataclasses import dataclass
import re
from functools import total_ordering


class InvalidVersion(ValueError):
    pass


_VERSION_RE = re.compile(r"^\s*v?(?P<release>\d+(?:\.\d+)*)\s*$")


@total_ordering
@dataclass(frozen=True)
class Version:
    _text: str
    _release: tuple[int, ...]

    def __init__(self, version: str) -> None:
        match = _VERSION_RE.match(version)
        if match is None:
            raise InvalidVersion(f"Invalid version: {version!r}")

        object.__setattr__(self, "_text", version)
        object.__setattr__(
            self,
            "_release",
            tuple(int(part) for part in match.group("release").split(".")),
        )

    @property
    def release(self) -> tuple[int, ...]:
        return self._release

    @property
    def public(self) -> str:
        return ".".join(str(part) for part in self._release)

    @property
    def base_version(self) -> str:
        return self.public

    def __str__(self) -> str:
        return self.public

    def __repr__(self) -> str:
        return f"Version('{self.public}')"

    def __hash__(self) -> int:
        return hash(self._release)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Version):
            return self._release == other._release
        if isinstance(other, str):
            try:
                return self == Version(other)
            except InvalidVersion:
                return False
        return NotImplemented

    def __lt__(self, other: object) -> bool:
        if isinstance(other, Version):
            return self._release < other._release
        if isinstance(other, str):
            return self < Version(other)
        return NotImplemented


def parse(version: str) -> Version:
    return Version(version)
