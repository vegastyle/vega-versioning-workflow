---
name: vega-commit-messages
description: Write git commit subjects and bodies for repos whose CI uses vega-packaging / vega-versioning-workflow, where lowercase hashtags in the commit body (#added, #changed, #fixed, #removed, #deprecated, #security plus exactly one #major, #minor or #patch) drive automatic semantic version bumps and Keep a Changelog CHANGELOG.md entries. Use this skill whenever you commit, amend, squash, reword, or draft or review a commit message in a repo that has a Keep a Changelog style CHANGELOG.md, a workflow calling vega-versioning-workflow, or a vega-packaging dependency, even if the user only says "commit this" or "write a commit message". This convention replaces Conventional Commits (feat:/fix:/chore:), which this tooling ignores. A wrong message silently drops changelog entries or fails the release CI.
---

# Vega commit messages

## Why the format matters

On every push, `vega-versioning-workflow` runs the `update_semantic_version` CLI from vega-packaging on the pushed
commit messages. The hashtags in those messages are its only input. From them it:

1. bumps the version in every packaging file it finds (`pyproject.toml`, `Cargo.toml`, `package.json`, Docker image
   tags, `CHANGELOG.md`),
2. writes a new `## [x.y.z] - date` section into `CHANGELOG.md` with Added / Changed / Fixed / ... subsections,
3. commits that as a bot (`Updating Packaging Files and Label to vX.Y.Z`) and tags `vX.Y.Z`.

Conventional Commits prefixes (`feat:`, `fix(scope):`, `chore:`) mean nothing to it. A malformed message is either
silently ignored (no version, no changelog entry), silently loses text, or crashes the CI job.

**Recognizing a repo that uses this:** a workflow referencing `vegastyle/vega-versioning-workflow`; a `CHANGELOG.md`
whose header cites Keep a Changelog and Semantic Versioning with sections like `## [0.7.5] - 2026/04/21 23:36:50`;
bot commits titled `Updating Packaging Files and Label to v...`; commit bodies made of lines like `#fixed ...` and
`#patch`. When unsure, look at the house style with `git log -8 --format='%s%n%b'`.

## Message shape

```
<plain subject line: short summary, contains no # characters>

#<change tag> <entry text>
#<change tag> <entry text>
#<bump tag>
```

For example:

```
Fix changelog parser crash when no version headers exist

#fixed crash when CHANGELOG.md has no version sections to iterate over
#added tests covering an empty and a missing changelog
#patch
```

CI turns that into:

```
## [0.7.6] - 2026/09/10 14:02:11

### Added

- tests covering an empty and a missing changelog

### Fixed

- crash when CHANGELOG.md has no version sections to iterate over
```

**`#` is reserved for real tags.** Nowhere in the message, subject or body, should a `#` appear except at the start
of a tag from the table below (or `#ignore`). The parser treats any `#` followed by letters or digits as a possible
tag, so a stray one cuts off changelog text, collides with tag parsing, or crashes CI.

### Subject line

- A plain summary of up to 72 characters, in the style of the existing log.
- **No `#` characters at all.** That rules out tags, `C#`, and `#42`. CI parses the subject and the body as two
  separate messages, and any `#` makes the subject count as a message. A tag in the subject then writes a second,
  duplicate changelog section for the same release. A `#` with no bump tag crashes the job. Write "C sharp" and
  "issue 42" instead.

### Body

- One change tag per line, at the start of the line, followed by its entry text.
- Exactly one bump tag, on its own line, **after** all the change tags. Nothing after the bump tag goes into the
  changelog, so trailers like `Co-Authored-By:` belong there. Text placed after a change entry would get glued onto
  that entry instead.
- If the commit should not be versioned, `#ignore` goes on its own line after the bump tag (see below).
- No free-form prose. Lines before the first tag are ignored. Lines after an entry become part of that entry.

## Change tags

| Tag | Changelog section | Use for |
|-----|-------------------|---------|
| `#added` | Added | new features, flags, parsers, files, tests, docs sections |
| `#changed` | Changed | changes to existing behavior, refactors, dependency or tool version updates, reworded docs |
| `#updated` | Changed | alias of `#changed` (the history uses it often; either is fine) |
| `#deprecated` | Deprecated | still works but is slated for removal |
| `#removed` | Removed | deleted features, flags, files, support |
| `#fixed` | Fixed | bug fixes |
| `#security` | Security | vulnerability fixes and hardening |

Sections always render in the order above, whatever order the tags appear in. Repeat a tag as often as needed; each
use becomes one bullet.

### Writing entry text

The tag word is removed and the rest becomes a bullet under that heading, so write text that reads naturally there:

- `#added support for Cargo workspaces` becomes `- support for Cargo workspaces` under **Added**. Good.
- `#added added support for Cargo workspaces` becomes `- added support for ...`. Redundant, so avoid it.
- Start lowercase, as the existing changelog does. Name the thing that changed (flag, file, parser, class) and its
  effect, in one line. A line break continues the same bullet, so keep each entry on a single line.
- Write for someone reading release notes. Lead with the user-visible effect, give one entry per meaningful change,
  and don't list every file touched.

### Issue and PR numbers

Mention an issue or PR in plain words, like "issue 57" or "PR 123", inside a change entry or in the subject, or
leave it out. Never write `#57`, `Fixes #57`, or `(#123)`: only real tags get a `#`. The trade-off is that GitHub
won't auto-link or auto-close the issue from the commit, so the user closes it by hand or from the PR description.

## Choosing the bump

Pick exactly one from the actual diff, following [semver](https://semver.org/):

- `#major` for breaking changes: a removed or renamed CLI flag, a changed public function or class signature, a
  changed file format, env var or output that others depend on, or dropped support for a platform or language
  version.
- `#minor` for new backward-compatible functionality: a new flag, new file-type or parser support, a new public API.
- `#patch` for everything else: bug fixes, tests, docs, refactors with no behavior change, CI tweaks, dependency pins.

When a commit mixes kinds, the highest one wins: a removed flag plus a bug fix is `#major`. If you write several bump
tags, the parser also picks the highest, but write one so the intent is obvious.

`#major` on a `0.x.y` project moves it to `1.0.0`. That is a milestone, not a routine bump, so call it out and get
the user's OK before committing.

When you report the commit, tell the user in one sentence which bump you chose and why. They can amend before
pushing. After the push, the version gets tagged and is hard to take back.

## Skipping versioning: `#ignore`

Some commits shouldn't produce a version: WIP, CI config you are iterating on, typo fixes, or anything the user says
not to version. Write the message exactly as you normally would, with change tags and a bump tag, then add `#ignore`
as the last tag, on its own line:

```
Fix typos in README.md

#fixed receive and version typos in README.md
#patch
#ignore
```

The change and bump tags still describe the commit, so it reads like every other entry in the log, and `#ignore`
makes CI skip it: no bump, no changelog entry.

- Write `#ignore` bare and lowercase, with no brackets, on its own line at the bottom. Only trailers without a `#`,
  like `Co-Authored-By:`, may follow it.
- Push an ignored commit on its own. CI combines the bodies of every commit in a push into one message, and one
  `#ignore` skips all of it, so real commits pushed alongside lose their bumps and changelog entries.
- Docs-only or test-only changes normally still get recorded (`#added` / `#changed` with `#patch`). Only ignore when
  the user asks for no bump or the change is truly noise.

## `#publish` and `#release` (coming soon)

The tooling defines `#publish` (build and push packages to their registries) and `#release` (build and create a
GitHub release), but the publish and release pipeline doesn't work yet. Work on it is underway, and this section will
be updated once the tags work end to end. Until then, don't add them on your own. If the user explicitly asks for
them, for example while working on that pipeline, include them and mention that they are not functional yet.

## Things that break silently

The linter below catches all of these. They are listed here so you understand what it reports.

- **Uppercase tags.** `#Fixed` and `#PATCH` are not recognized, and their text is dropped.
- **A `#` that isn't a tag.** `#fixed crash reported in #42 on Windows` produces `- crash reported in` and loses
  "on Windows", because any lowercase `#word` ends the current entry. Write "issue 42".
- **Double quotes, backticks and `$`.** The workflow pastes the message into a double-quoted bash argument. A `"`
  ends the argument early, backticks and `$( )` run as commands on the CI runner, and `$VAR` expands to nothing.
  Write `REGISTRY env var`, not `` `$REGISTRY` ``. For quoting, use single quotes, which are safe. The changelog is
  plain bullets anyway, so markdown code formatting adds nothing.
- **A `#` anywhere with no bump tag.** CI crashes (`AttributeError: 'NoneType' object has no attribute 'name'`).
- **Tags in the subject.** They write a second, duplicate changelog section for the same release.
- **Letting git open an editor.** When git opens an editor for the message, it treats lines starting with `#` as
  comments and deletes them, which removes every tag. `-m` and `-F` without an editor are safe by default. This
  rarely comes up, so handle it quietly (see Committing) instead of warning the user about it.
- **GitHub squash merges.** GitHub's default squash title appends the PR number, as in `Add flag (#123)`. That puts
  a `#` in the subject with no bump tag, and CI crashes. When merging with `gh pr merge --squash`, pass `--subject`
  without the PR number and `--body` with the tags.
- **Editing versions by hand.** Don't change version numbers in packaging files, add `## [x.y.z]` sections to
  `CHANGELOG.md`, or touch `## [Unreleased]`. CI does all of that, and manual edits cause double bumps or mismatched
  versions.
- **The bot's subject.** Never write a subject that starts `Updating Packaging Files and Label to v`. That subject
  belongs to the CI bot.

## Committing

1. Write the message to a temporary file outside the repo, for example in your scratch directory.
2. Lint it:
   ```bash
   uv run --no-project python <this skill's dir>/scripts/check_commit_message.py <message file>
   ```
   Fix every ERROR. WARNINGs are judgment calls. The output also shows the bump and a preview of the changelog
   section CI will write. Read it to confirm it says what you meant.
3. Commit with `git commit --cleanup=whitespace -F <message file>`, or `git commit --amend --cleanup=whitespace -F
   <message file>` to reword the last commit. `-F` avoids shell quoting problems. `--cleanup=whitespace` keeps the
   `#` lines even if the user's git config sets `commit.cleanup=strip`.
4. Check the result with `git log -1 --format=%B`. All the tag lines should still be there.
5. Report the subject and the bump, with a one-line reason, to the user.

The cleanup flag is a silent safeguard for commits you run yourself. Don't explain git's comment stripping to the
user unless they are about to write or edit the message in an editor themselves, for example `git commit --amend`
without `-m`, or an interactive rebase.

If you are only asked to draft a message, do steps 1 and 2 and hand over the linted message. If you suggest a
command for the user to run, write plain `git commit -F <message file>`, without `--cleanup`.

## Examples

A feature (`#minor`):

```
Add Cargo workspace support to the cargo parser

#added support for Cargo workspaces, bumping every member crate version together
#changed cargo parser now resolves the workspace root before reading versions
#minor
```

A breaking change (`#major`):

```
Rename BUILD env var to BUILD_TYPES

#changed BUILD env var written to GITHUB_ENV is now BUILD_TYPES, update downstream workflows
#removed BUILD env var
#major
```

Tests and docs only (`#patch`):

```
Document docker registry resolution and cover it with tests

#added README section explaining how the docker parser resolves the latest image tag
#added tests for registry tag lookup when no tags exist yet
#patch
```

A bad message and its fix:

```
fix(pyproject): handle "quoted" versions (#12)
```

Problems: CI ignores the `fix(...)` prefix, and the double quotes break the CI shell command. The `#12` puts a `#` in
the subject with no bump tag, which crashes CI. Fixed:

```
Handle quoted version strings in pyproject.toml

#fixed pyproject parser failing on versions wrapped in single or double quotes, reported in issue 12
#patch
```

## More detail

`references/parser-behavior.md` has the exact parsing algorithm, a behavior table, and source file pointers. Read it
when you hit an edge case this page doesn't cover.
