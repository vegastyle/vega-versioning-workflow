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
| `semantic-version` | The new version string (e.g. `1.2.3`) |
| `publish` | `True` if `#publish` was in the commit message |
| `release` | `True` if `#release` was in the commit message |
| `build_rust` | `True` if a `Cargo.toml` was found and updated |
| `build_python` | `True` if a `pyproject.toml` was found and updated |
| `build_npm` | `True` if a `package.json` was found and updated |
| `build_docker` | `True` if a `Dockerfile` was found and updated |

**Inputs:**
| Input | Required | Description |
|---|---|---|
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
| `pypi_registry` | No | PyPI registry URL |
| `npm_registry` | No | NPM registry URL |
| `docker_registry` | No | Docker registry |
| `cargo_registry` | No | Named crates.io registry |
| `cargo_path` | No | Path to `Cargo.toml` |
| `release_provider` | No | Release provider (`github`, default) |

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

---

### `build_and_publish_react.yml` — NPM build (reusable)
Publishes the NPM package to a registry.

**Inputs:**
| Input | Required | Description |
|---|---|---|
| `semantic_version` | Yes | Version tag to checkout |
| `npm_registry` | No | NPM registry URL |
| `build_npm` | Yes | `True` to run, anything else exits immediately |

---

### `build_and_publish_docker.yml` — Docker build (reusable)
Builds and pushes a Docker image to a registry.

**Inputs:**
| Input | Required | Description |
|---|---|---|
| `semantic_version` | Yes | Version tag to checkout |
| `docker_registry` | No | Docker registry |
| `build_docker` | Yes | `True` to run, anything else exits immediately |

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
      cargo_path: Cargo.toml
      pypi_registry: https://pypi.org/simple
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
```

---

## Commit Hashtags

| Hashtag | Effect |
|---|---|
| `#major` | Bump major version |
| `#minor` | Bump minor version |
| `#patch` | Bump patch version |
| `#publish` | Trigger build + publish jobs |
| `#release` | Trigger build + publish + GitHub release creation |
| `#ignore` | Skip all version bumping and CI for this commit |
| `#added` / `#removed` / `#changed` / `#fixed` / `#security` | Log changes in CHANGELOG.md |
