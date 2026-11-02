from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from stacking import ROOT, commit, copy, sh, sibling, stage  # noqa: E402

# Each render gets a venv: link it to uv's cache instead of copying every package into it.
os.environ.setdefault("UV_LINK_MODE", "symlink")

BASE = {"project_name": "demo", "description": "A demo project", "github_owner": "metalayerlab"}

# Stack answers for each render: (stack, answers). Python's are checked here; TypeScript's
# when template-typescript is checked out next to this repository.
MATRIX: dict[str, tuple[str, dict[str, object]]] = {
    "python-service": ("python", {"kind": "service", "container_image": True, "contrib": ["docker", "k8s", "systemd"],
                                  "extra_ports": [3128], "puid_pgid": True}),
    "python-service-bare": ("python", {"kind": "service", "container_image": True, "contrib": []}),
    "python-cli": ("python", {"kind": "cli", "container_image": True}),
    "typescript-service": ("typescript", {"kind": "service", "container_image": True, "contrib": ["docker", "k8s"]}),
    "typescript-web": ("typescript", {"kind": "web", "container_image": True, "contrib": ["docker", "k8s"]}),
}  # fmt: skip


def staged(name: str, env: str, factory: pytest.TempPathFactory) -> Path | None:
    found = sibling(name, env)
    return stage(found, factory.mktemp("src") / name) if found else None


@pytest.fixture(scope="session")
def base_src(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """template-base: $TEMPLATE_BASE, or ../template-base."""
    src = staged("template-base", "TEMPLATE_BASE", tmp_path_factory)
    if src is None:
        pytest.fail("template-base must be checked out next to this repository, or set TEMPLATE_BASE")
    return src


@pytest.fixture(scope="session")
def stacks(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path | None]:
    """The code stacks next to this repository ($TEMPLATE_PYTHON, $TEMPLATE_TYPESCRIPT)."""
    return {s: staged(f"template-{s}", f"TEMPLATE_{s.upper()}", tmp_path_factory) for s in ("python", "typescript")}


@pytest.fixture(scope="session")
def container_src(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return stage(ROOT, tmp_path_factory.mktemp("src") / "template-container")


def render(base_src: Path, stack_src: Path | None, container_src: Path | None, dst: Path, stack: dict,
           container: dict | None = None, bootstrap: bool = True) -> Path:  # fmt: skip
    if stack_src is None:
        pytest.skip("the stack overlay isn't checked out next to this repository")
    copy(base_src, dst, BASE)
    copy(stack_src, dst, stack)
    if container_src is not None:
        copy(container_src, dst, container or {})
    if bootstrap:
        sh("sh", "scripts/bootstrap.sh", cwd=dst)
    return commit(dst)


@pytest.fixture(scope="session", params=list(MATRIX))
def variant(request: pytest.FixtureRequest) -> str:
    return str(request.param)


@pytest.fixture(scope="session")
def project(variant: str, base_src: Path, stacks: dict[str, Path | None], container_src: Path,
            tmp_path_factory: pytest.TempPathFactory) -> Path:  # fmt: skip
    stack, answers = MATRIX[variant]
    return render(base_src, stacks[stack], container_src, tmp_path_factory.mktemp(variant) / "demo", answers)
