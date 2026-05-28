from pathlib import Path
from models import Package
import httpx

def parse_deps(project_path: str) -> list[Package]:
    deps: list[Package] = []
    path = Path(project_path)
    req_file = path / "requirements.txt"
    if req_file.exists():
        for line in req_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "==" in line:
                name, version = line.split("==", 1)
                deps.append(Package(name=name.strip(), version=version.strip(), source_file="requirements.txt"))
            else:
                deps.append(Package(name=line, version=None, source_file="requirements.txt"))
    pyproj_file = path / "pyproject.toml"

    if pyproj_file.exists():
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib
        data = tomllib.loads(pyproj_file.read_text())
        raw_deps = data.get("project", {}).get("dependencies", [])
        for dep in raw_deps:
            dep = dep.strip()
            if ">" in dep or "~" in dep or "=" in dep or "<" in dep:
                import re
                parts = re.split(r"[><=~!]+", dep, maxsplit=1)
                name = parts[0].strip()
            else:
                name = dep
            deps.append(Package(name=name, version=None, source_file="pyproject.toml"))
    return deps

def check_pypi(name:str) -> bool:
    url = f"https://pypi.org/pypi/{name}/json"
    try:
        resp = httpx.get(url, timeout=10)
        return resp.status_code == 200
    except httpx.RequestError:
            return False

def looks_internal(name: str) -> bool:
    if "-" in name or "_" in name or "." in name:
        return True
    if len(name) > 30:
        return True
    return False


from models import Risk
def scan_project(path: str) -> list[Package]:
    deps = parse_deps(path)
    for pkg in deps:
        pkg.pypi_exist = check_pypi(pkg.name)
        if looks_internal(pkg.name) and pkg.pypi_exist:
            pkg.risk = Risk.CONFIRMED
    return deps
