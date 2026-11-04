# AGENTS.md: working on template-container

This repository is a [Copier](https://copier.readthedocs.io/) **feature overlay**: it is applied on top of
template-base and a code stack (template-python, template-typescript, template-go), and adds a container
image's workflows and manifests. These instructions are for changing **the overlay**. Why:
`docs/decisions/0001-container-overlay.md` and template-base's decision 0001.

## Layout

| Path | What |
|---|---|
| `copier.yml` | `multi_arch`; base's and the stack's answers through `_external_data` (recorded for updates); the compatibility check |
| `template/` | `container-*` workflows, `contrib/docker/`, `contrib/k8s/` |
| `tests/` | Renders base, each stack (siblings, or `$TEMPLATE_PYTHON`, `$TEMPLATE_TYPESCRIPT`) and this overlay, and checks the result |
| `docs/decisions/` | Design records; `README.md` is the index |

## The rules of a feature overlay

- **Never fill a slot or add a required job.** Only `container-*` workflows and `NN-container*.sh` drop-ins, each marked `Template-owned: template-container` in its first 12 lines.
- **Never ask another template's question.** Read base's and the stack's answers; record them for `copier update`.
- A language-specific file belongs to the stack. A change base or a stack needs goes there as an issue.

## Rules

- Keep every render green: `uv run pytest -n auto`. Pin actions to SHAs. Never credit an AI. Never create tags or releases.
- Pins are bumped by Renovate (template-base's decision 0002, `pin-bumps.yml`): don't hand-bump one unless it's urgent.
- Asking the user something? Give your recommendation and why. Reply tersely.

## Definition of done

```sh
uv run pytest -n auto -m ''
docker run --rm -v "$PWD:/repo" -w /repo rhysd/actionlint:1.7.12
```
