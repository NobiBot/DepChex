import re
import configparser
from pathlib import Path
from .models import Package, Risk
import httpx

_NAME_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9_.-]*)")
_GITHUB_RE = re.compile(
    r"(?:https?://)?github\.com/([A-Za-z0-9._-]+)/([A-Za-z0-9._-]+?)(?:\.git|[/?#].*)?$"
)


def _extract_name(dep: str) -> str | None:
    dep = dep.strip()
    if "#" in dep:
        dep = dep.split("#", 1)[0].strip()
    m = _NAME_RE.match(dep)
    return m.group(1) if m else None


def is_github_url(s: str) -> bool:
    return bool(_GITHUB_RE.match(s.strip()))


def parse_github_url(url: str) -> tuple[str, str]:
    m = _GITHUB_RE.match(url.strip())
    if not m:
        raise ValueError(f"Not a valid GitHub URL: {url}")
    return m.group(1), m.group(2)


def _get_default_branch(owner: str, repo: str) -> str:
    try:
        resp = httpx.get(
            f"https://api.github.com/repos/{owner}/{repo}",
            timeout=5,
            headers={"Accept": "application/vnd.github.v3+json"},
        )
        if resp.status_code == 200:
            return resp.json().get("default_branch", "main")
    except (httpx.RequestError, ValueError, KeyError):
        pass
    return "main"


def _parse_req_text(text: str, source_label: str) -> list[Package]:
    deps: list[Package] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("-") or line.startswith("--"):
            continue
        name = _extract_name(line)
        if name:
            deps.append(Package(name=name, version=None, source_file=source_label))
    return deps


def _parse_pyproject_text(text: str, source_label: str) -> list[Package]:
    deps: list[Package] = []
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib
    try:
        data = tomllib.loads(text)
    except Exception:
        return deps
    for key in ("dependencies", "optional-dependencies"):
        raw = data.get("project", {}).get(key, [])
        if isinstance(raw, dict):
            for group in raw.values():
                for dep in group:
                    name = _extract_name(dep)
                    if name:
                        deps.append(Package(name=name, version=None, source_file=source_label))
        elif isinstance(raw, list):
            for dep in raw:
                name = _extract_name(dep)
                if name:
                    deps.append(Package(name=name, version=None, source_file=source_label))
    return deps


def _parse_setup_cfg_text(text: str, source_label: str) -> list[Package]:
    deps: list[Package] = []
    config = configparser.ConfigParser()
    try:
        config.read_string(text)
    except configparser.Error:
        return deps
    if config.has_option("options", "install_requires"):
        raw = config.get("options", "install_requires")
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            name = _extract_name(line)
            if name:
                deps.append(Package(name=name, version=None, source_file=source_label))
    return deps


def _fetch_raw_file(url: str, timeout: int = 10) -> str | None:
    try:
        resp = httpx.get(url, timeout=timeout, follow_redirects=True)
        if resp.status_code == 200:
            return resp.text
    except httpx.RequestError:
        pass
    return None


def fetch_remote_deps(url: str) -> list[Package]:
    owner, repo = parse_github_url(url)
    branch = _get_default_branch(owner, repo)
    deps: list[Package] = []

    files: list[tuple[str, str, str]] = [
        ("requirements.txt", "requirements.txt", "raw"),
        ("pyproject.toml", "pyproject.toml", "pyproject"),
        ("setup.cfg", "setup.cfg", "cfg"),
    ]

    for filename, label, fmt in files:
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{filename}"
        text = _fetch_raw_file(raw_url)
        if text is None and branch != "main":
            raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/{filename}"
            text = _fetch_raw_file(raw_url)
        if text is not None:
            if fmt == "raw":
                deps.extend(_parse_req_text(text, label))
            elif fmt == "pyproject":
                deps.extend(_parse_pyproject_text(text, label))
            elif fmt == "cfg":
                deps.extend(_parse_setup_cfg_text(text, label))

    return deps


def parse_deps(project_path: str) -> list[Package]:
    deps: list[Package] = []
    path = Path(project_path)

    req_file = path / "requirements.txt"
    if req_file.exists():
        deps.extend(_parse_req_text(req_file.read_text(), "requirements.txt"))

    pyproj_file = path / "pyproject.toml"
    if pyproj_file.exists():
        deps.extend(_parse_pyproject_text(pyproj_file.read_text(), "pyproject.toml"))

    setup_cfg = path / "setup.cfg"
    if setup_cfg.exists():
        deps.extend(_parse_setup_cfg_text(setup_cfg.read_text(), "setup.cfg"))

    return deps


def get_pypi_info(name: str) -> dict:
    url = f"https://pypi.org/pypi/{name}/json"
    try:
        resp = httpx.get(url, timeout=10)
        if resp.status_code == 404:
            return {"exists": False}
        if resp.status_code != 200:
            return {"exists": None}
        data = resp.json()
        releases = data.get("releases", {})
        non_empty = sorted(
            (v, rls) for v, rls in releases.items() if rls
        )
        info = {"exists": True}
        if non_empty:
            info["releases"] = len(non_empty)
            info["first_release"] = non_empty[0][1][0]["upload_time"][:10]
        return info
    except httpx.RequestError:
        return {"exists": None}


def scan_project(input_str: str, progress_callback=None) -> list[Package]:
    if is_github_url(input_str):
        deps = fetch_remote_deps(input_str)
    else:
        deps = parse_deps(input_str)

    for i, pkg in enumerate(deps):
        info = get_pypi_info(pkg.name)
        pkg.pypi_exist = info.get("exists")
        pkg.pypi_releases = info.get("releases")
        pkg.pypi_first_release = info.get("first_release")

        if pkg.pypi_exist is False:
            pkg.risk = Risk.CONFIRMED
        elif pkg.pypi_exist is True:
            releases = pkg.pypi_releases or 0
            if releases >= 3:
                pkg.risk = Risk.SAFE
            else:
                pkg.risk = Risk.SUSPICIOUS

        if progress_callback:
            progress_callback(pkg, i, len(deps))
    return deps
