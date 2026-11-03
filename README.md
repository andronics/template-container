# template-container

A **feature overlay** for a project that ships a container image. It goes on top of
[template-base](https://github.com/andronics/template-base) and a code stack overlay
([template-python](https://github.com/andronics/template-python) or
[template-typescript](https://github.com/andronics/template-typescript)) whose `container_image` answer is
true:

```sh
uvx copier copy --trust gh:andronics/template-base my-project
uvx copier copy --trust gh:andronics/template-python my-project
uvx copier copy --trust gh:andronics/template-container my-project
```

It asks one question, `multi_arch`, and reads everything else from base's and the stack's answers. It needs
template-base `v2.0.0` and the stack `v1.0.0` or later.

## What it adds

| Path | What |
|---|---|
| `container-build.yml` | Builds `ghcr.io/<owner>/<project>` from the stack's Dockerfile. Pushes and PRs get branch tags and a smoke test; each release (after the stack's `Release` workflow) gets `:X.Y.Z`, `:X.Y`, `:X` and `:latest` |
| `container-cleanup.yml` | Deletes branch images older than 7 days |
| `contrib/docker/`, `contrib/k8s/` | Compose and a kustomize base, when the stack's `contrib` names them |

The Dockerfile, the systemd unit and the manifest check stay in the stack: they're language-specific.

## Setup notes

`container-cleanup.yml` uses `GITHUB_TOKEN`, which can delete the image's versions while the package grants
this repository's Actions the Admin role (package settings → Manage Actions access). A package that
`container-build.yml` published has it by default. Otherwise add a `PACKAGES_DELETE_TOKEN` secret: a classic
personal access token with `read:packages` and `delete:packages`, owned by the account that owns the package
(for a personal account) or by an organisation member with admin access to it. Its `account` input is `user`
when base's `owner_is_org` is false, and the organisation's name otherwise
([`docs/decisions/0002`](docs/decisions/0002-cleanup-account-and-token.md)).

## Where this came from

Built from [metalayerlab/project-template](https://github.com/metalayerlab/project-template) `v0.1.23`'s
Docker workflows and contrib manifests, as a new repository with no history.
[`docs/decisions/0001`](docs/decisions/0001-container-overlay.md) records why it exists.

## License

[Unlicense](LICENSE).
