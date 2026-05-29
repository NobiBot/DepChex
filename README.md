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
pip install pipx
pipx install .
```

## Usage

```bash
depchex
```

Type a local path or GitHub URL and click **Scan**:
- **Local path**: e.g. `.` or `/path/to/project`
- **GitHub URL**: e.g. `https://github.com/owner/repo`

Use the **Paste** button to paste from the clipboard (Wayland).

### Command-line usage (no TUI)

```python
from depchex.scanner import scan_project

# Local path
for pkg in scan_project("/path/to/project"):
    print(f"{pkg.name:30s} {pkg.risk.name}")

# Or GitHub URL (auto-detected)
for pkg in scan_project("https://github.com/owner/repo"):
    print(f"{pkg.name:30s} {pkg.risk.name}")
```

## How it works

1. **Parses dependencies** from `requirements.txt`, `pyproject.toml`, or `setup.cfg` — either from a local path or fetched remotely from a GitHub URL
2. **Queries the PyPI JSON API** for each package to determine whether it exists publicly
3. **Classifies each package** based on its existence and release history on PyPI

## Limitations

- The 3-release threshold is a heuristic — it may produce false positives or negatives in edge cases
- Network-dependent (requires access to `pypi.org` and optionally `api.github.com` for branch detection)
- GitHub scanning fetches only `requirements.txt`, `pyproject.toml`, and `setup.cfg` from the repo root — nested dependency files are not retrieved
- Does not detect typosquatting, dependency hijacking, or other supply chain attacks

## License

MIT
