#!/usr/bin/env python3
"""Lint a git commit message against the vega-packaging hashtag convention.

Mirrors the parsing rules of vega.packaging.commits.CommitMessage and the way
vega-versioning-workflow feeds commit subjects and bodies to the
update_semantic_version CLI, so problems surface before the push instead of in CI.

Usage:
    uv run --no-project python check_commit_message.py MESSAGE_FILE
    git log -1 --format=%B | uv run --no-project python check_commit_message.py -

Exit status: 0 when there are no errors (warnings allowed), 1 when there are errors.
"""
import re
import sys

# Same tag pattern as vega.packaging.commits.CommitMessage.parse
TAG_RE = re.compile(r"#[a-z0-9]+")
# Anything that looks like a hashtag, including ones the parser would not recognize
HASH_WORD = re.compile(r"#[A-Za-z0-9]+")

BUMPS = {"major": 0, "minor": 1, "patch": 2}
CHANGES = {
    "added": "Added",
    "changed": "Changed",
    "updated": "Changed",
    "deprecated": "Deprecated",
    "removed": "Removed",
    "fixed": "Fixed",
    "security": "Security",
}
IGNORE = "ignore"
SECTION_ORDER = ["Added", "Changed", "Deprecated", "Removed", "Fixed", "Security"]
NOT_YET_SUPPORTED = {"publish", "release"}
SHELL_UNSAFE = {'"': "double quote", "`": "backtick", "$": "dollar sign"}
BOT_SUBJECT = "Updating Packaging Files and Label to v"
MAX_SUBJECT = 72


def short(text, limit=60):
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


def plain_form(word):
    """How to write a non-tag hashtag without the '#'."""
    return f"issue {word}" if word.isdigit() else word


def split_message(text):
    """Splits a message into (subject_lines, body, all_lines) the way git's %s / %b do."""
    lines = text.replace("\r\n", "\n").strip("\n").split("\n")
    blank = next((i for i, line in enumerate(lines) if not line.strip()), len(lines))
    return lines[:blank], "\n".join(lines[blank + 1:]), lines


def check(text):
    errors, warnings, notes = [], [], []
    subject_lines, body, all_lines = split_message(text)
    subject = " ".join(line.strip() for line in subject_lines)
    body_first_line = len(subject_lines) + 2

    # --- Subject -----------------------------------------------------------------------
    if not subject:
        errors.append("subject is empty")
    if len(subject_lines) > 1:
        warnings.append("no blank line after the first line: git treats the first "
                        f"{len(subject_lines)} lines as the subject")
    if subject.startswith(BOT_SUBJECT):
        errors.append(f"subject '{BOT_SUBJECT}...' is reserved for the CI bot's version commit")
    if len(subject) > MAX_SUBJECT:
        warnings.append(f"subject is {len(subject)} chars; keep it to {MAX_SUBJECT} or fewer")
    if "#" in subject:
        errors.append("subject contains '#': CI parses the subject as its own message, so a tag there writes a "
                      "second, duplicate changelog section, and a '#' without a bump tag crashes CI. Move tags "
                      "to the body and write things like 'issue 57' or 'C sharp' without '#'")

    # --- Shell safety (whole message) ----------------------------------------------------
    for lineno, line in enumerate(all_lines, 1):
        for char, name in SHELL_UNSAFE.items():
            if char in line:
                errors.append(f"line {lineno}: {name} ({char}) - CI pastes the message into a double-quoted "
                              "bash argument, so this breaks the command or runs as shell code")

    # --- #ignore -------------------------------------------------------------------------
    ignored = "#ignore" in text.lower()
    if "[#ignore]" in text.lower():
        errors.append("write #ignore without brackets, on its own line at the bottom of the body")
    if ignored:
        body_tags = list(TAG_RE.finditer(body))
        last = body_tags[-1] if body_tags else None
        last_line = ""
        if last:
            line_start = body.rfind("\n", 0, last.start()) + 1
            line_end = body.find("\n", last.end())
            last_line = body[line_start:len(body) if line_end == -1 else line_end]
        if not last or last.group() != "#ignore" or last_line.strip() != "#ignore":
            warnings.append("put #ignore on its own line as the last tag, after the bump tag")
        notes.append("#ignore: CI skips this commit (no bump, no changelog). CI combines the bodies of all commits "
                     "in a push, so push this commit on its own or the other commits are skipped too")

    # --- Line-level vocabulary checks ----------------------------------------------------
    for lineno, line in enumerate(body.split("\n"), body_first_line):
        for match in HASH_WORD.finditer(line):
            word = match.group()[1:]
            if word == IGNORE:
                continue
            if word != word.lower():
                known = word.lower() in CHANGES or word.lower() in BUMPS or word.lower() == IGNORE
                hint = f"use #{word.lower()}" if known else "the parser only reads lowercase tags"
                errors.append(f"line {lineno}: #{word} is not recognized ({hint}); its text is not parsed as a tag")
            elif word in NOT_YET_SUPPORTED:
                errors.append(f"line {lineno}: #{word} is not supported yet (publish/release pipeline is "
                              "coming soon); remove it unless the user explicitly asked for it")

    # --- Simulate the parser -------------------------------------------------------------
    sections = []
    pos = 0
    for match in TAG_RE.finditer(body):
        sections.append(("text", body[pos:match.start()], None))
        sections.append(("tag", match.group()[1:], body.count("\n", 0, match.start()) + body_first_line))
        pos = match.end()
    sections.append(("text", body[pos:], None))

    bumps_seen, changes = [], {}
    key = tag = None
    last_tag_kind = None
    seen_tag = False
    for kind, value, lineno in sections:
        if kind == "tag":
            seen_tag = True
            if value in BUMPS:
                bumps_seen.append(value)
                last_tag_kind = "bump"
            elif value in CHANGES:
                tag = value
                last_tag_kind = "change"
            elif value == IGNORE or value in NOT_YET_SUPPORTED:
                pass  # handled above
            elif key is not None:
                errors.append(f"line {lineno}: #{value} inside the #{tag} entry is not a tag; it ends the entry "
                              "and the text after it is lost. Only real tags get a '#': write "
                              f"'{plain_form(value)}' instead")
            else:
                errors.append(f"line {lineno}: #{value} is not a tag. Only real tags get a '#': write "
                              f"'{plain_form(value)}' in a change entry or the subject, or leave it out")
            key = CHANGES.get(value)
            continue

        text_part = value.strip()
        if key is not None and value:
            if not text_part:
                errors.append(f"#{tag} has no entry text (renders as an empty bullet)")
                continue
            changes.setdefault(key, []).append(text_part)
            if "\n" in text_part:
                warnings.append(f"#{tag} entry spans several lines ('{short(text_part)}'); the line breaks end "
                                "up inside one changelog bullet - keep each entry on one line, and put trailers "
                                "after the bump tag")
            first_word = text_part.split()[0].lower().strip(".,:;")
            if first_word == tag:
                warnings.append(f"#{tag} entry starts with '{first_word}' again; the tag word is already the "
                                f"section heading, so write "
                                f"'#{tag} {short(text_part[len(first_word):].strip(), 30)}'")
        elif text_part and not seen_tag:
            notes.append(f"not added to the changelog (before the first tag): '{short(text_part)}'")

    # --- Bump ------------------------------------------------------------------------------
    bump = min(bumps_seen, key=BUMPS.get) if bumps_seen else None
    if bump is None:
        if "#" in body or "#" in subject:
            errors.append("no bump tag (#major, #minor or #patch): CI crashes on messages with '#' but no bump, "
                          "and ignored commits still carry their bump tag")
        else:
            errors.append("no tags at all: CI ignores this commit (no version, no changelog). Add change tags "
                          "and a bump tag, plus #ignore on the last line if it should not be versioned")
    elif len(bumps_seen) > 1:
        warnings.append(f"{len(bumps_seen)} bump tags ({', '.join('#' + b for b in bumps_seen)}); the highest "
                        f"(#{bump}) wins - keep exactly one")
    if bump and last_tag_kind != "bump":
        warnings.append("put the bump tag after all change tags; text after the last entry (like trailers) "
                        "otherwise gets glued onto that entry")
    if bump and not changes:
        warnings.append("bump without any change tags: the changelog gets an empty version section")

    return errors, warnings, notes, bump, changes, ignored


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    if argv[1] == "-":
        text = sys.stdin.read()
    else:
        with open(argv[1], encoding="utf-8", errors="replace") as handle:
            text = handle.read()

    errors, warnings, notes, bump, changes, ignored = check(text)

    for label, items in (("ERROR", errors), ("WARNING", warnings), ("NOTE", notes)):
        for item in items:
            print(f"{label}: {item}")

    if bump:
        print(f"\nBump: #{bump}" + (" (skipped by CI because of #ignore)" if ignored else ""))
        print("CHANGELOG.md preview" + (" if it were not ignored" if ignored else "") + ":\n")
        print("## [x.y.z] - <date>")
        for section in SECTION_ORDER:
            if section in changes:
                print(f"\n### {section}\n")
                for entry in changes[section]:
                    print(f"- {entry}")
    print(f"\nResult: {'FAIL' if errors else 'PASS'} ({len(errors)} errors, {len(warnings)} warnings)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
