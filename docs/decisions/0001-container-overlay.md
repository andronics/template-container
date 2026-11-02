# 0001: The container feature overlay

Status: Proposed
Date: 2026-11-02
Authors: Stephen Cox; drafted by Claude (Claude Code)

## Context

template-base's decision **0001** (from the idea note **🥞 Stacked Copier Templates**, in the brain's
`vault/ideas/`) allows **feature overlays** next to the one stack overlay. A feature overlay has prefixed
files and drop-ins only: it fills no slot and adds no required check. Both left open whether Docker and
`contrib/` should be one; their recommendation was "not yet, until a third language duplicates them".
Building template-python and template-typescript showed what both would carry. The image build and cleanup
workflows were byte-identical across the two languages, and so were the docker and k8s manifests apart from
web's `config.json`. Stephen chose this overlay over duplicating them (2026-11-02). This is the first
feature overlay.

## Decision

- **What it owns:** `.github/workflows/container-build.yml` and `container-cleanup.yml` (were
  `docker-build.yml` and `docker-cleanup.yml`), `contrib/docker/compose.yml` and `contrib/k8s/*`, and
  `.copier-answers.container.yml`.
- **What it doesn't:** the Dockerfile, `.dockerignore`, `docker/entrypoint.sh`, nginx's configs, the
  systemd unit and the manifest check are language-specific, so each stack keeps them. Each stack also
  keeps its `container_image` and `contrib` answers, because its wiki, `.standard.toml` and release-please's
  `extra-files` need them before this overlay is applied.
- **Asks** only `multi_arch`. **Reads** base's answers, and the one stack's: `kind`, `port`,
  `extra_ports`, `health_path`, `timezone`, `puid_pgid`, `contrib`, and `package_name` for Python's
  settings prefix.
- **It names the stacks it supports** (`_external_data`: `python`, `typescript`; a missing file reads as
  `{}`), and exactly one must be applied. Base still names no overlay, and the dependency points from the
  feature to the stack. A new stack is one line here.
- **It fails the copy with the reason** when base is missing or older than `v2.0.0`, the stack missing or older than `v1.0.0`, when
  there are two stacks, or when the stack's `container_image` isn't true.
- **Release → image:** `container-build.yml` runs on `workflow_run` of the stack's `Release` workflow
  (both stacks name it that). It builds the `v*` tag that points at the run's head commit, if there is
  one, and moves `:latest`. `workflow_run` fires even when release-please used `GITHUB_TOKEN`, and the
  stack's release workflow never names this overlay's file. Manual dispatch rebuilds a given tag, as
  before.
- **`base_answers`, `stack` and `stack_answers`:** recorded as answers of this overlay (`ask: false`, with
  validators that reject a copy that differs from its file), following template-base 0001's pattern,
  because `copier update` replays without the other templates' answers files. The templates read only the
  recorded copies; the compatibility check passes in a replay and checks the files in the real render.

## Alternatives considered

- **Duplicate Docker and contrib in each code overlay** (the note's recommendation). *Rejected* by
  Stephen for one overlay.
- **The stack's release workflow calls `container-build.yml`** (`uses:`, as project-template did): a stack
  would name a feature overlay's file, and actionlint fails when it isn't there. *Rejected.*
- **`contrib` asked here:** the stack is applied first, and its wiki and release config need the answer.
  *Rejected.*
- **This overlay owns the Dockerfile:** its build stages, base image and healthcheck differ by language
  (40 of 94 lines). *Rejected.*

## Consequences

- A project with an image has three answers files: base's, the stack's and this one's.
- The stack's `scripts/check-manifests.sh` and `stack-ci.yml`'s manifest job validate this overlay's
  compose and kustomize files. The stack's `checks.d` drop-in fails when its `contrib` names docker or k8s
  and this overlay isn't applied.
- The release image is built by a second workflow run, after `Release` finishes, instead of inside it.

## Open questions

None.
