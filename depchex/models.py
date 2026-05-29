from dataclasses import dataclass
from enum import auto, Enum

class Risk(Enum):
    CONFIRMED = auto()
    SUSPICIOUS = auto()
    SAFE = auto()


@dataclass
class Package:
    name: str
    version: str | None
    source_file: str
    risk: Risk = Risk.SAFE
    pypi_exist: bool | None = None
    pypi_releases: int | None = None
    pypi_first_release: str | None = None
