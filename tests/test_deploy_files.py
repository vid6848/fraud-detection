"""Phase 7 step 2: deployment files stay consistent with the code.

The image itself is built and started in CI (the `docker` job in ci.yml).
"""
import importlib.metadata as md
import re

import pytest

from ml.config import ROOT

# requirements-api.txt name -> the requirements.txt name it must match
SAME_PACKAGE = {"xgboost-cpu": "xgboost"}


def pins(path) -> dict[str, str]:
    lines = (line.split("#")[0].strip() for line in path.read_text().splitlines())
    return {re.sub(r"\[.*\]", "", name).lower(): version
            for name, version in (line.split("==") for line in lines if line)}


def test_api_requirements_match_the_dev_requirements():
    api, dev = pins(ROOT / "requirements-api.txt"), pins(ROOT / "requirements.txt")
    for name, version in api.items():
        if name == "postgrest":  # comes with `supabase` in requirements.txt
            assert version == md.version("postgrest")
        else:
            assert dev[SAME_PACKAGE.get(name, name)] == version, name


def test_dockerfile_runs_as_non_root_on_render_port():
    dockerfile = (ROOT / "Dockerfile").read_text()
    users = re.findall(r"^USER (\S+)", dockerfile, re.M)
    assert users and users[-1] not in {"root", "0"}
    assert '--port \\"$PORT\\"' in dockerfile
    assert "requirements-api.txt" in dockerfile


def test_everything_the_dockerfile_copies_exists_and_is_not_dockerignored():
    dockerfile = (ROOT / "Dockerfile").read_text()
    sources = [s for line in re.findall(r"^COPY (?!--from)(.+)$", dockerfile, re.M)
               for s in line.split()[:-1]]
    allowed = [line[1:] for line in (ROOT / ".dockerignore").read_text().splitlines()
               if line.startswith("!")]
    assert "ml/artifacts/score_distribution.json" in sources  # GET /drift's reference
    for source in sources:
        assert list(ROOT.glob(source.rstrip("/"))), source
        assert source in allowed, f"{source} is excluded by .dockerignore"


def test_render_blueprint():
    yaml = pytest.importorskip("yaml")
    [service] = yaml.safe_load((ROOT / "render.yaml").read_text())["services"]
    assert service["runtime"] == "docker" and service["plan"] == "free"
    assert service["healthCheckPath"] == "/health"
    env = {e["key"]: e for e in service["envVars"]}
    for secret in ("SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY",
                   "CORS_ORIGINS"):
        assert env[secret] == {"key": secret, "sync": False}  # entered in Render, never in git


def test_demo_rows_are_in_the_image():
    allowed = (ROOT / ".dockerignore").read_text()
    assert "!api/" in allowed and (ROOT / "api" / "assets" / "demo_rows.csv.gz").exists()
