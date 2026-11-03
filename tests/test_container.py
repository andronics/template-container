"""Render template-base, a code stack (template-python, template-typescript) with an image, then
template-container, and check the projects that result.

    uv run pytest -n auto         # every test (siblings: ../template-base, ../template-python, ...)
    uv run pytest -m docker       # also compose, kustomize and kubeconform, and actionlint, through Docker

Each render must pass its Definition of done's checks unchanged: `sh scripts/checks.sh` and the
stack's manifest check.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from conftest import BASE, MATRIX, render
from stacking import GIT, ROOT, checks, commit, copy, sh, stage


def run(project: Path, *cmd: str) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if k not in ("VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT")}
    return subprocess.run(cmd, cwd=project, capture_output=True, text=True, env=env)


def test_renders_once_per_variant(request: pytest.FixtureRequest, variant: str) -> None:
    """Under xdist, each variant's tests share one worker, so it renders once (conftest.py, --dist loadgroup)."""
    if os.environ.get("PYTEST_XDIST_WORKER") and request.config.getoption("dist") == "loadgroup":
        assert request.node.nodeid.endswith(f"@{variant}"), "xdist isn't grouping by variant"


def test_checks_pass(project: Path) -> None:
    result = checks(project)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.splitlines()[0] == "00-base OK"


def test_never_asks_others_questions() -> None:
    """One answer, one place: base's and the stack's answers are read, never asked (decision 0001)."""
    config = yaml.safe_load((ROOT / "copier.yml").read_text())
    # ask: false (the recorded copies) is never prompted.
    asked = {k for k, v in config.items()
             if not k.startswith("_") and v.get("when") is not False and v.get("ask") is not False}  # fmt: skip
    assert asked == {"multi_arch"}
    assert config["_answers_file"] == ".copier-answers.container.yml"
    assert config["_external_data"]["base"] == ".copier-answers.base.yml"


def test_files_by_name(project: Path, variant: str) -> None:
    """Only prefixed workflows, no slot, and the manifests the stack's `contrib` names."""
    workflows = {p.name for p in (project / ".github/workflows").glob("container-*")}
    assert workflows == {"container-build.yml", "container-cleanup.yml"}
    contrib = MATRIX[variant][1].get("contrib", [])
    assert (project / "contrib/docker/compose.yml").is_file() == ("docker" in contrib)
    assert (project / "contrib/k8s/kustomization.yaml").is_file() == ("k8s" in contrib)
    answers = yaml.safe_load((project / ".copier-answers.container.yml").read_text())
    assert answers["stack"] == MATRIX[variant][0]
    assert answers["stack_answers"]["kind"] == MATRIX[variant][1]["kind"]
    assert "base_answers" not in answers["stack_answers"]
    assert answers["base_answers"]["project_name"] == "demo"


def test_reads_the_stack(project: Path, variant: str) -> None:
    stack = MATRIX[variant][1]
    build = (project / ".github/workflows/container-build.yml").read_text()
    assert "IMAGE: ghcr.io/metalayerlab/demo" in build
    if stack["kind"] == "service":
        assert f"[[ port ]]" not in build and ":8080" in build
    if 3128 in stack.get("extra_ports", []):
        assert "3128" in (project / "contrib/docker/compose.yml").read_text()


def test_networkpolicy_scraper_allowance(project: Path, variant: str) -> None:
    """A python service's /metrics (template-python 0007) gets a commented scraper allowance; nothing is opened."""
    policy = project / "contrib/k8s/networkpolicy.yaml"
    if not policy.is_file():
        return
    text = policy.read_text()
    stack, answers = MATRIX[variant]
    assert ("# A Prometheus scraper" in text) == (stack == "python" and answers["kind"] == "service")
    assert len(yaml.safe_load(text)["spec"]["ingress"]) == 1


def test_release_follows_the_stack_by_name(project: Path) -> None:
    """The image builds after the stack's `Release` workflow, which never names this overlay."""
    build = yaml.safe_load((project / ".github/workflows/container-build.yml").read_text())
    assert build[True]["workflow_run"] == {"workflows": ["Release"], "types": ["completed"], "branches": ["main"]}
    releases = [p for p in (project / ".github/workflows").glob("*-release.yml")]
    assert len(releases) == 1 and yaml.safe_load(releases[0].read_text())["name"] == "Release"
    assert "workflows/container" not in releases[0].read_text()  # never calls it (a comment may name it)


def test_marked(project: Path) -> None:
    for name in ("container-build.yml", "container-cleanup.yml"):
        head = "\n".join((project / ".github/workflows" / name).read_text().splitlines()[:12])
        assert "Template-owned: template-container" in head


def test_manifests(project: Path) -> None:
    """The stack's manifest check validates this overlay's files (tools it lacks are skipped locally)."""
    result = run(project, "bash", "scripts/check-manifests.sh")
    assert result.returncode == 0 and "manifests OK" in result.stdout, result.stdout + result.stderr


@pytest.mark.docker
def test_docker_checks(project: Path) -> None:
    cmds = [("docker", "run", "--rm", "-v", f"{project}:/repo", "-w", "/repo", "rhysd/actionlint:1.7.12", "-color")]
    if (project / "contrib/docker/compose.yml").is_file():
        cmds.append(("docker", "compose", "-f", "contrib/docker/compose.yml", "config", "--quiet"))
    if (project / "contrib/k8s").is_dir():
        cmds.append(("sh", "-c", "docker run --rm -v \"$PWD/contrib/k8s:/k8s\" registry.k8s.io/kubectl:v1.37.2 kustomize /k8s"
                     " | docker run --rm -i ghcr.io/yannh/kubeconform:v0.8.0 -strict -summary"))  # fmt: skip
    for cmd in cmds:
        result = run(project, *cmd)
        assert result.returncode == 0, f"{' '.join(cmd)}:\n{result.stdout}\n{result.stderr}"


@pytest.mark.parametrize(("case", "error"), [
    ("no base", "needs template-base first"),
    ("old base", "needs template-base v2.0.0 or later; this project has v1.0.0"),
    ("no stack", "needs a stack overlay first"),
    ("no image", "needs the stack answer container_image: true (template-python)"),
    ("two stacks", "found more than one stack overlay: python,typescript"),
])  # fmt: skip
def test_needs_base_and_a_stack(case: str, error: str, base_src: Path, stacks: dict, container_src: Path,
                                tmp_path: Path) -> None:  # fmt: skip
    """Base, then exactly one stack with an image, at the versions this overlay needs; otherwise the copy
    fails and says why."""
    dst = tmp_path / "p"
    python = stacks["python"]
    if python is None:
        pytest.skip("template-python isn't checked out next to this repository")
    if case == "old base":
        copy(stage(base_src, tmp_path / "old-base", tag="v1.0.0"), dst, BASE)
    elif case != "no base":
        copy(base_src, dst, BASE)
    if case == "no image":
        copy(python, dst, {"kind": "cli", "container_image": False})
    elif case == "two stacks":
        copy(python, dst, {"kind": "cli"})
        (dst / ".copier-answers.stack-typescript.yml").write_text("_commit: v1.0.0\n_src_path: x\n")
    with pytest.raises(Exception, match=re.escape(error)):
        copy(container_src, dst, {})


def test_update_keeps_the_stack_values(base_src: Path, stacks: dict, container_src: Path, tmp_path: Path) -> None:
    """`copier update` replays both versions without base's or the stack's answers file; the recorded
    copies keep the port, image and manifests intact, and a project edit survives."""
    project = render(base_src, stacks["python"], container_src, tmp_path / "p",
                     {"kind": "service", "container_image": True, "contrib": ["docker"], "port": 9090})  # fmt: skip
    compose = project / "contrib/docker/compose.yml"
    compose.write_text(compose.read_text() + "# a project edit\n")
    commit(project)
    newer = tmp_path / "newer"
    shutil.copytree(container_src, newer)
    cleanup = newer / "template/.github/workflows/container-cleanup.yml.jinja"
    cleanup.write_text(cleanup.read_text().replace("cut-off: 7d", "cut-off: 8d"))
    sh(*GIT, "commit", "-qam", "newer", cwd=newer)
    sh("git", "tag", "v1.0.1", cwd=newer)
    answers = project / ".copier-answers.container.yml"
    answers.write_text(answers.read_text().replace(str(container_src), str(newer)))
    commit(project)
    sh("uvx", "--from", "copier>=9.19,<10", "copier", "update", "-a", ".copier-answers.container.yml", "--trust",
       "--skip-tasks", "--defaults", "--conflict", "inline", "--vcs-ref", "v1.0.1", cwd=project)  # fmt: skip
    changed = sorted(line[3:] for line in sh("git", "status", "--porcelain", cwd=project).splitlines())
    assert changed == [".copier-answers.container.yml", ".github/workflows/container-cleanup.yml"]
    assert "cut-off: 8d" in (project / ".github/workflows/container-cleanup.yml").read_text()
    assert "9090" in compose.read_text() and "# a project edit" in compose.read_text()
    assert "<<<<<<<" not in sh("git", "diff", cwd=project)


def test_stack_answer_change_reaches_the_manifests(base_src: Path, stacks: dict, container_src: Path,
                                                    tmp_path: Path) -> None:  # fmt: skip
    """The stack's `port` changes (an update with -d), then this overlay updates: the validator finds its
    recorded copy stale, rereads the stack's answers, and compose publishes the new port."""
    project = render(base_src, stacks["python"], container_src, tmp_path / "p",
                     {"kind": "service", "container_image": True, "contrib": ["docker"], "port": 9090})  # fmt: skip
    sh("uvx", "--from", "copier>=9.19,<10", "copier", "update", "-a", ".copier-answers.stack-python.yml", "--trust",
       "--skip-tasks", "--defaults", "--conflict", "inline", "--vcs-ref", "v1.0.0", "-d", "port=9191",
       cwd=project)  # fmt: skip
    commit(project)
    newer = tmp_path / "newer"
    shutil.copytree(container_src, newer)
    cleanup = newer / "template/.github/workflows/container-cleanup.yml.jinja"
    cleanup.write_text(cleanup.read_text().replace("cut-off: 7d", "cut-off: 8d"))
    sh(*GIT, "commit", "-qam", "newer", cwd=newer)
    sh("git", "tag", "v1.0.1", cwd=newer)
    answers = project / ".copier-answers.container.yml"
    answers.write_text(answers.read_text().replace(str(container_src), str(newer)))
    commit(project)
    sh("uvx", "--from", "copier>=9.19,<10", "copier", "update", "-a", ".copier-answers.container.yml", "--trust",
       "--skip-tasks", "--defaults", "--conflict", "inline", "--vcs-ref", "v1.0.1", cwd=project)  # fmt: skip
    assert "9191" in (project / "contrib/docker/compose.yml").read_text()
    assert yaml.safe_load(answers.read_text())["stack_answers"]["port"] == 9191
    assert "<<<<<<<" not in sh("git", "diff", cwd=project)
