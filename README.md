# DepChex

A TUI tool that scans Python projects for **dependency confusion** risks.

## What is Dependency Confusion?

Dependency confusion is a supply chain attack where an attacker uploads a malicious package to a public repository (PyPI) using the same name as a private package used internally by an organization. If the build system is misconfigured to search both a private index and PyPI, pip may install the attacker's public version instead of the private one, especially if the public version has a higher version number.

## Risk Classification

| Risk | Color | Meaning |
|---|---|---|
| **CONFIRMED** | Red | Package is **not found on PyPI** — an attacker could register the name and compromise any project that depends on it |
| **SUSPICIOUS** | Yellow | Package **exists on PyPI but has fewer than 3 releases** — could be a recently squatted name; worth investigating |
| **SAFE** | Green | Package exists on PyPI with **3+ releases** — clearly a legitimate public package |

## Installation

```bash
git clone https://github.com/NobiBot/DepChex.git
cd DepChex
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Usage

```bash
dpchex
```

Type the path to a Python project (e.g. `.` for the current directory or `/path/to/project`) and click **Scan**. Use the **Paste** button to paste a path from the clipboard (Wayland).

### Command-line usage (no TUI)

```python
from depchex.scanner import scan_project

for pkg in scan_project("/path/to/project"):
    print(f"{pkg.name:30s} {pkg.risk.name}")
```

## How it works

1. **Parses dependencies** from `requirements.txt` and `pyproject.toml`
2. **Queries the PyPI JSON API** for each package to determine whether it exists publicly
3. **Classifies each package** based on its existence and release history on PyPI

## Limitations

- The 3-release threshold is a heuristic — it may produce false positives or negatives in edge cases
- Network-dependent (requires access to `pypi.org`)
- Does not detect typosquatting, dependency hijacking, or other supply chain attacks

## License

MIT
