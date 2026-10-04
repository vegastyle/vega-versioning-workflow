# vega-versioning-workflow
> GitHub Actions workflows for automated semantic versioning, multi-language builds, and releases powered by [vega-packaging](https://github.com/vegastyle/vega-packaging).

## About
These workflows use the **update_semantic_version** and **build_and_publish** CLI commands from `vega-packaging` to:
1. Parse commit hashtags (`#patch`, `#minor`, `#major`, `#publish`, `#release`) to determine what to do.
2. Bump the semantic version in all relevant packaging files and commit the changes.
3. Build and publish packages for each detected language in parallel.
4. Create a GitHub release (with cross-compiled Rust binaries attached, if applicable).

Trigger the publish flow by including `#publish` in a commit message.
Trigger the release flow (includes publish + GitHub release creation) by including `#release`.

---

## Workflow Overview

### `update_version_workflow.yml` — Version bumping only
A reusable workflow that handles commit message parsing and semantic version updates. It does **not** build or publish.

**Outputs:**
| Output | Description |
|---|---|
| `eligible` | `True` only after an allowed branch push successfully completes versioning; `False` when excluded, ignored, or unsuccessful. Treat missing outputs as denial too. |
| `semantic-version` | The new version string (e.g. `1.2.3`); empty when versioning is skipped |
| `publish` | `True` if `#publish` was in the commit message |
| `release` | `True` if `#release` was in the commit message |
| `build_rust` | `True` if a `Cargo.toml` was found and updated |
| `build_python` | `True` if a `pyproject.toml` was found and updated |
| `build_npm` | `True` if a `package.json` was found and updated |
| `build_docker` | `True` if a `Dockerfile` was found and updated |

**Inputs:**
| Input | Required | Description |
|---|---|---|
| `allowed_branches` | No | Comma/newline-separated exact branch names. Empty/omitted uses the caller repository's default branch. |
| `cargo_path` | No | Path to `Cargo.toml` (if Rust project) |

---

### `bump_build_and_publish.yml` — Full orchestration
The top-level workflow that composes version bumping, parallel builds, and release creation.

**Jobs run in this order:**
1. `update-version` — bumps version, detects build types, outputs flags.
2. (parallel, conditional on `publish==True` or `release==True`)
   - `build_and_publish_rust` — cross-compiles Rust binaries, uploads `bin/` artifact.
   - `build_and_publish_python` — publishes Python package to PyPI.
   - `build_and_publish_react` — publishes NPM package.
   - `build_and_publish_docker` — builds and pushes Docker image.
3. `release` — downloads all artifacts, creates GitHub release with binary attachments.

Each language job exits immediately if its `build_*` flag is not `True`, so unused jobs are always fast.

**Inputs:**
| Input | Required | Description |
|---|---|---|
| `allowed_branches` | No | Same branch allowlist policy as the versioning workflow. |
| `pypi_registry` | No | PyPI registry URL |
| `npm_registry` | No | NPM registry URL |
| `docker_registry` | No | Docker registry |
| `cargo_registry` | No | Named crates.io registry |
| `cargo_path` | No | Path to `Cargo.toml` |
| `tailscale_tags` | No | Comma-separated Tailscale tags. Leave empty to skip Tailscale entirely. |
| `tailscale_ping` | No | Optional host/IP list to ping after connecting to Tailscale. |
| `release_provider` | No | Release provider (`github`, default) |

**Secrets:**
| Secret | Required | Description |
|---|---|---|
| `TS_OAUTH_CLIENT_ID` | Only when `tailscale_tags` is set | Tailscale OAuth client ID |
| `TS_OAUTH_SECRET` | Only when `tailscale_tags` is set | Tailscale OAuth client secret |

---

### `build_and_publish_rust.yml` — Rust build (reusable)
Cross-compiles the Rust project for 5 targets and uploads the `bin/` directory as a workflow artifact.

**Targets compiled:** `x86_64-linux`, `aarch64-linux`, `x86_64-macos`, `aarch64-macos`, `x86_64-windows`

**Inputs:**
| Input | Required | Description |
|---|---|---|
| `semantic_version` | Yes | Version tag to checkout |
| `cargo_path` | No | Path to `Cargo.toml` (default: `Cargo.toml`) |
| `vega_packaging_ref` | No | vega-packaging version to install (default: `v0.6.2`) |
| `build_rust` | Yes | `True` to run, anything else exits immediately |

---

### `build_and_publish_python.yml` — Python build (reusable)
Publishes the Python package to PyPI or a private registry.

**Inputs:**
| Input | Required | Description |
|---|---|---|
| `semantic_version` | Yes | Version tag to checkout |
| `pypi_registry` | No | PyPI registry URL |
| `build_python` | Yes | `True` to run, anything else exits immediately |
| `tailscale_tags` | No | Comma-separated Tailscale tags. Leave empty to skip Tailscale. |
| `tailscale_ping` | No | Optional host/IP list to ping after connecting to Tailscale. |

**Secrets:**
| Secret | Required | Description |
|---|---|---|
| `TS_OAUTH_CLIENT_ID` | Only when `tailscale_tags` is set | Tailscale OAuth client ID |
| `TS_OAUTH_SECRET` | Only when `tailscale_tags` is set | Tailscale OAuth client secret |

---

### `build_and_publish_react.yml` — NPM build (reusable)
Publishes the NPM package to a registry.

**Inputs:**
| Input | Required | Description |
|---|---|---|
| `semantic_version` | Yes | Version tag to checkout |
| `npm_registry` | No | NPM registry URL |
| `build_npm` | Yes | `True` to run, anything else exits immediately |
| `tailscale_tags` | No | Comma-separated Tailscale tags. Leave empty to skip Tailscale. |
| `tailscale_ping` | No | Optional host/IP list to ping after connecting to Tailscale. |

**Secrets:**
| Secret | Required | Description |
|---|---|---|
| `TS_OAUTH_CLIENT_ID` | Only when `tailscale_tags` is set | Tailscale OAuth client ID |
| `TS_OAUTH_SECRET` | Only when `tailscale_tags` is set | Tailscale OAuth client secret |

---

### `build_and_publish_docker.yml` — Docker build (reusable)
Builds and pushes a Docker image to a registry.

**Inputs:**
| Input | Required | Description |
|---|---|---|
| `semantic_version` | Yes | Version tag to checkout |
| `docker_registry` | No | Docker registry |
| `build_docker` | Yes | `True` to run, anything else exits immediately |
| `tailscale_tags` | No | Comma-separated Tailscale tags. Leave empty to skip Tailscale. |
| `tailscale_ping` | No | Optional host/IP list to ping after connecting to Tailscale. |

**Secrets:**
| Secret | Required | Description |
|---|---|---|
| `TS_OAUTH_CLIENT_ID` | Only when `tailscale_tags` is set | Tailscale OAuth client ID |
| `TS_OAUTH_SECRET` | Only when `tailscale_tags` is set | Tailscale OAuth client secret |

---

## Branch Policy

Versioning and the full pipeline process only non-deletion **branch pushes** on the allowlist. Excluded branches get no version calculation, generated-file commit, tag, build, publish, or release, even with `#publish` or `#release`. Tag pushes and callers triggered by pull requests, schedules, or manual dispatch are not supported and are denied. The gate/status jobs still run to report the decision.

- With `allowed_branches` omitted or `""`, the caller repository's default branch is allowed.
- Set `allowed_branches: main` to enforce **main only**, regardless of the repository's default branch.
- To opt into multiple branches, use `allowed_branches: "main, release/1.x"` or a YAML block:
  ```yaml
  allowed_branches: |
    main
    release/1.x
  ```

Matching is literal and case-sensitive: `mai`, `Main`, and `refs/heads/main` do not match `main`. Surrounding whitespace and blank entries are removed; CRLF is supported. Globs are not expanded. A whitespace/delimiter-only list fails configuration validation rather than allowing everything. Comma-containing branch names cannot be represented in an explicit allowlist; an omitted input still treats the repository's default branch as one literal name.

`@main` in a `uses:` reference selects the workflow implementation, **not** the caller branch being authorized. Reusable workflows use the caller's push context. Custom consumers must require `eligible == 'True'` before starting any tag-dependent jobs; `[#ignore]` in any pushed commit subject/body also prevents versioning and downstream jobs.

All allowed branches share the global `v<version>` tag namespace. Use distinct version lines for multi-branch policies; concurrent runs may still collide. This policy does not serialize or redesign tag allocation.

This repository runs `.github/workflows/versioning_on_push.yml` on pushes to `main`, explicitly passing `allowed_branches: main`. The reusable versioning and full-pipeline workflows do not trigger directly on push, avoiding duplicate version/tag runs. Use `#minor #added` in a commit message to request a minor version bump and changelog entry.

**Behavior change:** non-default branches no longer version or publish unless explicitly allowlisted. Existing tags are not removed, and merged commits are processed normally when pushed to an allowed branch.

---

## How To Use

Follow the GitHub docs on [calling reusable workflows](https://docs.github.com/en/actions/using-workflows/reusing-workflows#calling-a-reusable-workflow).

### Example: Full pipeline with Rust and Python

Create `.github/workflows/on_push.yml` in your repo:

```yaml
name: On Push

on: push

permissions:
  actions: read
  contents: write
  pull-requests: write
  statuses: read

jobs:
  bump-build-and-publish:
    uses: vegastyle/vega-versioning-workflow/.github/workflows/bump_build_and_publish.yml@main
    with:
      allowed_branches: main
      cargo_path: Cargo.toml
      pypi_registry: https://pypi.org/simple
      tailscale_tags: tag:ci
      tailscale_ping: my-private-host.my-tailnet.ts.net
    secrets:
      TS_OAUTH_CLIENT_ID: ${{ secrets.TS_OAUTH_CLIENT_ID }}
      TS_OAUTH_SECRET: ${{ secrets.TS_OAUTH_SECRET }}
```

### Example: Version bump only (no build/publish)

```yaml
name: On Push

on: push

permissions:
  actions: read
  contents: write
  pull-requests: write
  statuses: read

jobs:
  update-version:
    uses: vegastyle/vega-versioning-workflow/.github/workflows/update_version_workflow.yml@main
    with:
      allowed_branches: main
```

---

## Validation

Run the branch-policy and workflow-guard regression tests locally:

```sh
python -m pip install -r requirements-test.txt
python -m unittest discover -s tests -v
```

Run `actionlint` against `.github/workflows/*.yml` to check Actions syntax. Local tests execute the embedded gate and check explicit job predicates; they do not emulate GitHub's runner scheduling. Before rollout, test the push caller and both reusable entry points in a disposable repository: allowed pushes create tags, excluded/ignored pushes create none, and failed/skipped versioning never starts tag-dependent jobs.

## Commit Hashtags

| Hashtag | Effect |
|---|---|
| `#major` | Bump major version |
| `#minor` | Bump minor version |
| `#patch` | Bump patch version |
| `#publish` | Trigger build + publish jobs |
| `#release` | Trigger build + publish + GitHub release creation |
| `[#ignore]` | Skip versioning and downstream jobs for the push when present in any commit subject or body |
| `#added` / `#removed` / `#changed` / `#fixed` / `#security` | Log changes in CHANGELOG.md |
