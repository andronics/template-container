# Design records

Why template-container is the way it is. Copy [0000-template.md](0000-template.md) to `NNNN-short-title.md`
and add a line below. **Read this index first.** The split itself is template-base's decision 0001.

| # | Title | Status | Decision in one line |
|---|---|---|---|
| [0001](0001-container-overlay.md) | The container feature overlay | Proposed | The first feature overlay: the image's build and cleanup workflows and the docker and k8s manifests; the stack keeps the Dockerfile and `contrib`; the image builds after the stack's `Release` by `workflow_run` |
| [0002](0002-cleanup-account-and-token.md) | The cleanup workflow's account and token | Proposed | `account: user` for a personal account (snok reads any other value as an organisation); `GITHUB_TOKEN`, or a classic PAT in `PACKAGES_DELETE_TOKEN` |
