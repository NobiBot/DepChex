import re
from pathlib import Path
from .models import Package, Risk
import httpx

_NAME_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9_.-]*)")


def _extract_name(dep: str) -> str | None:
    dep = dep.strip()
    if "#" in dep:
        dep = dep.split("#", 1)[0].strip()
    m = _NAME_RE.match(dep)
    return m.group(1) if m else None


def parse_deps(project_path: str) -> list[Package]:
    deps: list[Package] = []
    path = Path(project_path)

    req_file = path / "requirements.txt"
    if req_file.exists():
        for line in req_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("-") or line.startswith("--"):
                continue
            name = _extract_name(line)
            if name:
                deps.append(Package(name=name, version=None, source_file="requirements.txt"))

    pyproj_file = path / "pyproject.toml"
    if pyproj_file.exists():
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib
        data = tomllib.loads(pyproj_file.read_text())
        for key in ("dependencies", "optional-dependencies"):
            raw = data.get("project", {}).get(key, [])
            if isinstance(raw, dict):
                for group in raw.values():
                    for dep in group:
                        name = _extract_name(dep)
                        if name:
                            deps.append(Package(name=name, version=None, source_file="pyproject.toml"))
            elif isinstance(raw, list):
                for dep in raw:
                    name = _extract_name(dep)
                    if name:
                        deps.append(Package(name=name, version=None, source_file="pyproject.toml"))
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


def scan_project(path: str, progress_callback=None) -> list[Package]:
    deps = parse_deps(path)
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
