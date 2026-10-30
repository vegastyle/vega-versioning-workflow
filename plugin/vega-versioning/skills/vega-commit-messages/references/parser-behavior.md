# Parser behavior reference

How a commit message travels from `git push` to `CHANGELOG.md`, with source pointers. Read this for edge cases the
main SKILL.md does not cover.

## Contents
- Pipeline
- Parsing algorithm
- Behavior table
- Known quirks
- Source files

## Pipeline

1. **Collect** (`vega-versioning-workflow/.github/workflows/update_version_workflow.yml`, job
   `check-commit-message`). For a push to an existing branch it runs
   `git log --pretty=%s <before>..<after>` and `git log --pretty=%b <before>..<after>`. **All subjects in the push
   become one newline-joined string, and all bodies become another.** For a new branch, only the head commit is used.
2. **Gate.** The `update-semantic-version` job is skipped entirely if either string contains the literal `[#ignore]`.
   The house convention doesn't use the bracket form. It puts a bare `#ignore` on the last line of the body instead,
   which the CLI skips (step 4).
3. **Invoke** the CLI as
   `update_semantic_version --subject "<subjects>" --description "<bodies>" ... --github_env`.
   The strings are interpolated straight into a double-quoted bash argument, which is why `"`, backticks, and `$` are
   unsafe.
4. **Parse each string separately** (`vega/packaging/bootstrappers/update_semantic_version.py`, `main()`). For each of
   subject and description that is non-empty, it calls `update_semantic_version(message)`, which:
   - builds `commits.CommitMessage(message)`,
   - returns early unless `is_valid`: the string contains `#` and does not contain `#ignore` (case-insensitive,
     substring match, so `#ignored` also counts),
   - otherwise bumps every discovered packaging file (`pyproject.toml`, `Cargo.toml`, `package.json`, Dockerfile,
     `CHANGELOG.md` which is auto-created, and the GitHub env file) and inserts a changelog section.

   So if both the subject string and the body string are valid, **two changelog sections** get written. Both bumps
   start from the same original version, so the two sections usually carry the same version number. The packaging
   files keep the body's result, because the body is parsed last.
5. **Bot commit.** `git-auto-commit-action` commits `Updating Packaging Files and Label to v<version>` and tags
   `v<version>`.

## Parsing algorithm

From `vega/packaging/commits.py`, `CommitMessage.parse`:

```python
sections = re.split("(#[a-z0-9]+)", message)   # lowercase letters and digits only
for section in sections:
    if section.startswith("#"):
        key = None                               # every tag ends the previous entry
        tag = section[1:].upper()
        # Versions.MAJOR/MINOR/PATCH -> keep the highest bump seen
        # Changes.ADDED/CHANGED/UPDATED/DEPRECATED/REMOVED/FIXED/SECURITY -> key = that section
        # WorkflowTypes.PUBLISH/RELEASE -> set flags (IGNORE handled by is_valid)
        # anything else -> no-op, key stays None
        continue
    if key is not None and section:
        changes[key].append(section.strip())     # outer whitespace only; inner newlines kept
```

`markdown()` renders `## [version] - YYYY/MM/DD HH:MM:SS`, then one `### Section` per change kind in enum order
(Added, Changed, Deprecated, Removed, Fixed, Security), with a `- entry` bullet per entry. `#updated` is an enum alias
of `#changed`, so it renders under **Changed**.

## Behavior table

Verified against vega-packaging 0.7.5.

| Input | Result |
|-------|--------|
| `#fixed resolved issue #42 in parser` + `#patch` | Fixed: `resolved issue`. The words "in parser" are lost. |
| `#Fixed parser crash` + `#patch` | no entries; the patch bump still happens |
| `#patch #added x #minor` | bump = minor (the highest wins) |
| `#added x` (no bump) | valid, then `SemanticVersion.bump(None)` raises `AttributeError` and CI fails |
| `#added first line` + newline + `continued line` | one entry with an embedded newline |
| `#deprecated old flag` | Deprecated: `old flag` |
| `#fixed x` + `#patch` + `#ignore` | whole string skipped: no bump, no changelog |
| `#changed C# support` | Changed: `C# support` (a `#` followed by a space is not a tag) |
| `Refactor docker parser` (no `#`) | not valid, silently skipped |
| subject `Add C# support`, body with tags | the subject is valid with no bump, so CI crashes |
| subject `Add flag #minor`, body `#added flag` + `#minor` | two `## [0.8.0]` sections, one of them empty |
| `#patch` + trailer lines after it | ignored (no active change key); the convention still keeps `#` out of trailers |
| subject `Add flag (#123)` (GitHub squash default) | the subject is valid with no bump, so CI crashes |
| `#minor #publish ...` | `PUBLISH=True` in GITHUB_ENV (the pipeline is not working yet) |

## Known quirks

These are tooling bugs to be aware of, not conventions:

- Tags in both subject and body write two changelog sections for one release.
- A message that has `#` but no bump tag crashes instead of being skipped or using a default bump.
- Shell interpolation of the message in the workflow allows command injection through backticks or `$(...)`.
- The README still documents a `--message` flag. The CLI now takes `--subject` and `--description`.

## Source files

- `vega-packaging/src/vega/packaging/commits.py`: `CommitMessage` (parse, is_valid, markdown)
- `vega-packaging/src/vega/packaging/const.py`: `Versions`, `Changes`, `WorkflowTypes` enums
- `vega-packaging/src/vega/packaging/bootstrappers/update_semantic_version.py`: CLI entry, subject and body loop
- `vega-packaging/src/vega/packaging/versions.py`: `SemanticVersion.bump`
- `vega-packaging/src/vega/packaging/parsers/changelog.py`: changelog insertion
- `vega-versioning-workflow/.github/workflows/update_version_workflow.yml`: message collection, `[#ignore]` gate
