from dataclasses import dataclass
from enum import auto, Enum

class Risk(Enum):
    CONFIRMED = auto()
    SAFE = auto()


@dataclass
class Package:
    name: str
    version: str | None
    source_file: str
    risk: Risk = Risk.SAFE
    pypi_exist: bool = False
