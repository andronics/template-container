# 0002: The cleanup workflow's account and token

<!-- Add a line for this record to the index in docs/decisions/README.md (CI checks). -->

Status: Proposed
Date: 2026-11-03
Authors: Stephen Cox

## Context

`container-cleanup.yml` (decision 0001) runs snok/container-retention-policy v3.1.0 daily. It passed
`account: <github_owner>` for every project. On andronics/trackie, a personal account's project, the
scheduled run 41617009556 (2026-11-03) panicked: `Failed to fetch packages: missing field 'id' at line 1
column 141`.

The action's `account` input is `user` for a personal account and an organisation's name otherwise; any
value but `user` becomes an organisation (its `src/client/urls.rs`). So it asked for
`/orgs/andronics/packages/container/trackie`, and GitHub answered with a 404 object
(`{"message":"Not Found",...,"status":"404"}`, 141 characters) where a package was expected. The same call
on `/users/andronics/packages/container/trackie` finds the package, linked to andronics/trackie.

The token wasn't the cause. With `GITHUB_TOKEN` the action never lists packages; it fetches each
`image-names` entry by name (its `fetch_packages`), which GitHub allows when the package grants the
repository's Actions the Admin role. GitHub grants that by default to the repository whose workflow
published the package ("Deleting and restoring a package" in GitHub's docs). qbt-rules and ferryman, both
personal-account projects, ran the pre-overlay workflow with `account: user` and `GITHUB_TOKEN` and passed
daily. Listing a user's packages and deleting a version over the REST API otherwise needs a classic
personal access token (`read:packages`, `delete:packages`); GitHub Packages takes no fine-grained or GitHub
App token, `GITHUB_TOKEN` aside.

## Decision

- **`account`:** `user` when the owner is a personal account, the owner's name when it's an organisation.
  This overlay reads base's `owner_is_org` (base v2.0.8 and later); for an older base it applies base's own
  rule, that `code_owners` naming `@<owner>` means a personal account.
- **`token`:** `secrets.PACKAGES_DELETE_TOKEN || secrets.GITHUB_TOKEN`, as before (the secret name
  qbt-rules and ferryman used). The secret is optional: a classic PAT with `read:packages` and
  `delete:packages`, owned by the personal account that owns the package, or by an organisation member
  with admin access to it.
- The action stays pinned by SHA.

## Alternatives considered

- **Skip the cleanup for a personal account without `PACKAGES_DELETE_TOKEN`** (with a notice). It assumed
  `GITHUB_TOKEN` can't manage a personal account's packages; it can, by name, with the Admin role the
  publishing repository already has. Skipping would turn off a cleanup that works. *Rejected.*
- **Require `PACKAGES_DELETE_TOKEN` everywhere:** a long-lived PAT per project, for no gain while
  `GITHUB_TOKEN` works. *Rejected.*

## Consequences

- Personal-account projects (trackie) clean up again with `GITHUB_TOKEN` after `copier update`.
- A package not published by the project's own workflow needs the Admin role granted under Manage Actions
  access, or the secret; without either, deleting a version fails with a permissions error.
- `PACKAGES_DELETE_TOKEN`, when set, takes precedence; with `account: user` it acts on its owner's packages,
  so it must belong to the account that owns the image.

## Open questions

None.
