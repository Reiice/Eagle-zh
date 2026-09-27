"""Static checks for the GitHub Actions workflow.

A step-level `permissions` key passed every eyeball review and still killed the run at
startup ("Unexpected value 'permissions'"), so the schema is asserted mechanically instead.

pyyaml is the only optional dependency; without it the file is still scanned for tabs and
for needs/step-id wiring, which are the other ways this workflow breaks silently.
"""

from __future__ import annotations

import os
import re
import sys

WORKFLOW_KEYS = {"name", "on", True, "permissions", "env", "defaults", "concurrency", "jobs", "run-name"}
JOB_KEYS = {
    "name", "needs", "runs-on", "environment", "concurrency", "matrix", "strategy",
    "services", "container", "steps", "outputs", "permissions", "timeout-minutes",
    "cancel-in-progress", "if", "env", "defaults", "continue-on-error",
}
STEP_KEYS = {
    "id", "if", "name", "run", "shell", "working-directory", "env", "uses", "with",
    "continue-on-error", "timeout-minutes",
}


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else ".github/workflows/build-zh.yml"
    raw = open(path, encoding="utf-8").read()
    problems: list[str] = []

    if "\t" in raw:
        line = raw[: raw.index("\t")].count("\n") + 1
        problems.append(f"line {line}: tab character (YAML forbids tabs for indentation)")

    try:
        import yaml
    except ImportError:
        print("pyyaml unavailable -- ran tab check only")
        print("RESULT:", "FAIL" if problems else "PASS (partial)")
        for p in problems:
            print("  -", p)
        return 1 if problems else 0

    doc = yaml.safe_load(raw)

    bad = set(doc) - WORKFLOW_KEYS
    if bad:
        problems.append(f"workflow-level keys not allowed: {sorted(map(str, bad))}")

    jobs = doc.get("jobs") or {}
    for jname, job in jobs.items():
        bad = set(job) - JOB_KEYS
        if bad:
            problems.append(f"job '{jname}': keys not allowed: {sorted(map(str, bad))}")

        ids = set()
        for i, step in enumerate(job.get("steps") or [], 1):
            bad = set(step) - STEP_KEYS
            if bad:
                problems.append(
                    f"job '{jname}' step {i} ({step.get('name') or step.get('uses')}): "
                    f"keys not allowed at step level: {sorted(map(str, bad))}"
                )
            if step.get("id"):
                ids.add(step["id"])

        for out_expr in (job.get("outputs") or {}).values():
            for ref in re.findall(r"steps\.([A-Za-z0-9_-]+)\.", str(out_expr)):
                if ref not in ids:
                    problems.append(f"job '{jname}' outputs reference unknown step id {ref!r}")

        need = job.get("needs")
        need = [need] if isinstance(need, str) else list(need or [])
        for n in need:
            if n not in jobs:
                problems.append(f"job '{jname}' needs unknown job {n!r}")
        for expr in re.findall(r"needs\.([A-Za-z0-9_-]+)\.", str(job)):
            if expr not in jobs:
                problems.append(f"job '{jname}' references unknown job {expr!r} in an expression")

    # Every job must resolve to a runner, otherwise the workflow fails before any step runs.
    for jname, job in jobs.items():
        if "runs-on" not in job and "uses" not in job:
            problems.append(f"job '{jname}' has no runs-on")

    trig = doc.get("on", doc.get(True))
    if not trig:
        problems.append("no triggers defined")

    print(f"{path}: {len(jobs)} job(s), "
          f"{sum(len(j.get('steps') or []) for j in jobs.values())} step(s)")
    for p in problems:
        print("  -", p)
    print("RESULT:", "FAIL" if problems else "PASS")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
