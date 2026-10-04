"""Regression tests for the actual inline gate and explicit workflow guards.

These tests do not emulate GitHub's implicit job-success/skip scheduling rules.
"""

import itertools
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def load_workflow(name):
    # BaseLoader preserves the YAML key `on` and output strings like True/False.
    return yaml.load((WORKFLOWS / name).read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


VERSION = load_workflow("update_version_workflow.yml")
PIPELINE = load_workflow("bump_build_and_publish.yml")
PUSH_CALLER = load_workflow("versioning_on_push.yml")
GATE_STEP = VERSION["jobs"]["branch-gate"]["steps"][0]


def evaluate_guard(expression, needs):
    """Evaluate only the expression subset used by the checked-in guards.

    Expressions come from trusted workflow files, not user input. Missing outputs
    become empty strings, as in Actions. This is not a general Actions evaluator.
    """
    code = expression.strip()
    if code.startswith("${{"):
        code = code[3:-2].strip()
    code = code.replace("needs.*.result", repr([job.get("result", "") for job in needs.values()]))

    def substitute(match):
        job = needs.get(match[1], {})
        if match[3]:
            return repr(job.get("outputs", {}).get(match[3], ""))
        return repr(job.get("result", ""))

    code = re.sub(r"needs\.([\w-]+)\.(outputs\.([\w-]+)|result)", substitute, code)
    code = code.replace("&&", " and ").replace("||", " or ")
    code = re.sub(r"!(?!=)", " not ", code)

    def contains(haystack, needle):
        if isinstance(haystack, list):
            return needle in haystack
        return str(needle).casefold() in str(haystack).casefold()

    return eval(code, {"__builtins__": {}}, {"contains": contains, "always": lambda: True})


class BranchGateTests(unittest.TestCase):
    def run_gate(self, **overrides):
        script = GATE_STEP["run"]
        self.assertTrue(script.startswith("python3 - <<'PY'\n"))
        self.assertTrue(script.rstrip().endswith("\nPY"))
        python_code = script.split("\n", 1)[1].rsplit("\nPY", 1)[0]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            marker = Path(directory) / "injected"
            env = {
                **os.environ,
                "ALLOWED_BRANCHES": "",
                "DEFAULT_BRANCH": "main",
                "REF_NAME": "main",
                "REF_TYPE": "branch",
                "EVENT_NAME": "push",
                "DELETED": "false",
                "GITHUB_OUTPUT": str(output),
                **overrides,
            }
            result = subprocess.run(
                [sys.executable, "-c", python_code],
                env=env, cwd=directory, text=True, capture_output=True, timeout=10,
            )
            self.assertFalse(marker.exists(), "Input executed as code")
            return result, output.read_text(encoding="utf-8") if output.exists() else ""

    def assert_gate(self, expected, **overrides):
        result, output = self.run_gate(**overrides)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertEqual(output, f"allowed={expected}\n")

    def test_default_branch_with_omitted_or_empty_input(self):
        for branch in ("main", "master", "trunk"):
            with self.subTest(branch=branch):
                self.assert_gate(True, DEFAULT_BRANCH=branch, REF_NAME=branch)
                self.assert_gate(False, DEFAULT_BRANCH=branch, REF_NAME="feature/work")

    def test_default_branch_is_a_single_literal_name(self):
        self.assert_gate(True, DEFAULT_BRANCH="release,main", REF_NAME="release,main")
        for ref in ("release", "main"):
            with self.subTest(ref=ref):
                self.assert_gate(False, DEFAULT_BRANCH="release,main", REF_NAME=ref)

    def test_explicit_main_overrides_repository_default(self):
        self.assert_gate(True, ALLOWED_BRANCHES="main", DEFAULT_BRANCH="trunk")
        self.assert_gate(False, ALLOWED_BRANCHES="main", DEFAULT_BRANCH="trunk", REF_NAME="trunk")
        self.assert_gate(True, ALLOWED_BRANCHES="main", DEFAULT_BRANCH="")

    def test_exact_case_sensitive_matching_no_globs(self):
        for ref in ("mai", "Main", "main-extra", "refs/heads/main", "feature/work"):
            with self.subTest(ref=ref):
                self.assert_gate(False, ALLOWED_BRANCHES="main", REF_NAME=ref)
        self.assert_gate(False, ALLOWED_BRANCHES="feature/*", REF_NAME="feature/work")

    def test_multiple_branches_whitespace_crlf_and_duplicates(self):
        for raw in ("main,release/1.x", "main\nrelease/1.x", " \r\n main, ,release/1.x\r\nmain\n "):
            for ref in ("main", "release/1.x", "release/2.x"):
                with self.subTest(raw=raw, ref=ref):
                    self.assert_gate(ref != "release/2.x", ALLOWED_BRANCHES=raw, REF_NAME=ref)

    def test_invalid_empty_configuration(self):
        for overrides in (
            {"DEFAULT_BRANCH": ""},
            {"DEFAULT_BRANCH": " "},
            {"ALLOWED_BRANCHES": " "},
            {"ALLOWED_BRANCHES": ",,\r\n\t"},
        ):
            with self.subTest(overrides=overrides):
                result, output = self.run_gate(**overrides)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("::error::", result.stdout)
                self.assertEqual(output, "")

    def test_unsupported_refs_events_and_deletions_fail_closed(self):
        for overrides in (
            {"REF_TYPE": "tag"},  # A tag literally named main must not qualify.
            {"REF_TYPE": ""},
            {"EVENT_NAME": "pull_request"},
            {"EVENT_NAME": "workflow_dispatch"},
            {"EVENT_NAME": "schedule"},
            {"EVENT_NAME": "workflow_call"},  # Must use the originating push context.
            {"DELETED": "true"},
            {"DELETED": ""},
        ):
            with self.subTest(overrides=overrides):
                self.assert_gate(False, **overrides)

    def test_shell_looking_names_remain_literal(self):
        for name in ("$(touch injected)", "`touch injected`", "main;touch injected", "${PATH}"):
            with self.subTest(name=name):
                self.assert_gate(False, ALLOWED_BRANCHES=name)
                self.assert_gate(True, ALLOWED_BRANCHES=name, REF_NAME=name)


class WorkflowGuardTests(unittest.TestCase):
    def test_one_main_only_push_caller(self):
        self.assertEqual(PUSH_CALLER["on"]["push"]["branches"], ["main"])
        caller = PUSH_CALLER["jobs"]["update-version"]
        self.assertEqual(caller["uses"], "./.github/workflows/update_version_workflow.yml")
        self.assertEqual(caller["with"]["allowed_branches"], "main")
        push_workflows = [
            path.name for path in WORKFLOWS.glob("*.yml")
            if "push" in load_workflow(path.name)["on"]
        ]
        self.assertEqual(push_workflows, ["versioning_on_push.yml"])

    def test_input_and_output_wiring(self):
        for workflow in (VERSION, PIPELINE):
            self.assertNotIn("push", workflow["on"])
            inputs = workflow["on"]["workflow_call"]["inputs"]
            self.assertEqual(inputs["allowed_branches"]["type"], "string")
            self.assertEqual(inputs["allowed_branches"]["default"], "")
        self.assertEqual(
            PIPELINE["jobs"]["update-version"]["with"]["allowed_branches"],
            "${{ inputs.allowed_branches || '' }}",
        )
        self.assertEqual(
            VERSION["on"]["workflow_call"]["outputs"]["eligible"]["value"],
            "${{ jobs.versioning-status.outputs.eligible }}",
        )
        self.assertEqual(GATE_STEP["env"], {
            "ALLOWED_BRANCHES": "${{ inputs.allowed_branches || '' }}",
            "DEFAULT_BRANCH": "${{ github.event.repository.default_branch }}",
            "REF_NAME": "${{ github.ref_name }}",
            "REF_TYPE": "${{ github.ref_type }}",
            "EVENT_NAME": "${{ github.event_name }}",
            "DELETED": "${{ github.event.deleted }}",
        })
        self.assertEqual(
            VERSION["jobs"]["branch-gate"]["outputs"]["allowed"],
            "${{ steps.branch_policy.outputs.allowed }}",
        )
        self.assertNotIn("${{", GATE_STEP["run"])
        self.assertNotIn("uses", GATE_STEP)  # No caller checkout/script dependency.

    def test_commit_inspection_and_version_side_effects_are_gated(self):
        inspect_job = VERSION["jobs"]["check-commit-message"]
        version_job = VERSION["jobs"]["update-semantic-version"]
        self.assertEqual(inspect_job["needs"], "branch-gate")
        self.assertEqual(version_job["needs"], ["branch-gate", "check-commit-message"])
        self.assertTrue(any("tagging_message" in step.get("with", {}) for step in version_job["steps"]))
        for allowed, subject, body in itertools.product(
            ("True", "False", ""), ("change #publish #release", "skip [#ignore]"), ("", "skip [#ignore]"),
        ):
            needs = {
                "branch-gate": {"outputs": {"allowed": allowed}},
                "check-commit-message": {"outputs": {
                    "head-commit-subject": subject, "head-commit-description": body,
                }},
            }
            with self.subTest(allowed=allowed, subject=subject, body=body):
                self.assertEqual(evaluate_guard(inspect_job["if"], needs), allowed == "True")
                expected = allowed == "True" and "[#ignore]" not in subject + body
                self.assertEqual(evaluate_guard(version_job["if"], needs), expected)

    def test_stable_eligibility_requires_successful_versioning(self):
        status = VERSION["jobs"]["versioning-status"]
        self.assertEqual(status["if"], "${{ always() }}")
        self.assertEqual(status["needs"], ["branch-gate", "update-semantic-version"])
        self.assertEqual(status["outputs"]["eligible"], "${{ steps.status.outputs.eligible }}")
        expression = status["steps"][0]["env"]["ELIGIBLE"]
        for allowed, result in itertools.product(("True", "False", ""), ("success", "skipped", "failure", "cancelled")):
            with self.subTest(allowed=allowed, result=result):
                actual = evaluate_guard(expression, {
                    "branch-gate": {"outputs": {"allowed": allowed}},
                    "update-semantic-version": {"result": result},
                })
                self.assertEqual(actual, "True" if allowed == "True" and result == "success" else "False")

    def test_build_publish_release_predicates_cannot_bypass_eligibility(self):
        languages = {"rust": "rust:", "python": "python:", "react": "npm:", "docker": "docker:"}
        for language, build_type in languages.items():
            job = PIPELINE["jobs"][f"build_and_publish_{language}"]
            self.assertEqual(job["needs"], "update-version")
            for eligible, build, publish, release in itertools.product(
                ("True", "False", ""), ("", build_type), ("True", "False"), ("True", "False"),
            ):
                with self.subTest(language=language, eligible=eligible, build=build, publish=publish, release=release):
                    actual = evaluate_guard(job["if"], {"update-version": {"outputs": {
                        "eligible": eligible, "build": build, "publish": publish, "release": release,
                    }}})
                    expected = eligible == "True" and (bool(build) or publish == "True" or release == "True")
                    self.assertEqual(actual, expected)

    def test_release_requires_version_success_but_allows_skipped_languages(self):
        condition = PIPELINE["jobs"]["release"]["if"]
        for eligible, version_result, build_result, release in itertools.product(
            ("True", "False", ""), ("success", "skipped", "failure", "cancelled"),
            ("success", "skipped", "failure", "cancelled"), ("True", "False"),
        ):
            with self.subTest(eligible=eligible, version=version_result, build=build_result, release=release):
                needs = {
                    "update-version": {"result": version_result, "outputs": {"eligible": eligible, "release": release}},
                    "language": {"result": build_result},
                }
                actual = evaluate_guard(condition, needs)
                expected = eligible == "True" and version_result == "success" and release == "True" and build_result in ("success", "skipped")
                self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
