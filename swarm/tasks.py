"""Task factories — each function returns a CrewAI Task for a pipeline phase."""

from __future__ import annotations

from crewai import Agent, Task


# ---------------------------------------------------------------------------
# Phase 1: PLAN
# ---------------------------------------------------------------------------
def plan_task(architect: Agent, feature_request: str) -> Task:
    return Task(
        description=(
            f"Analyze this feature request and create a step-by-step implementation plan.\n\n"
            f"REQUEST: {feature_request}\n\n"
            f"First, use the ListDirectory and ReadFile tools to understand the existing "
            f"codebase structure. Then produce a plan with:\n"
            f"1. Files to create or modify (with paths)\n"
            f"2. Implementation steps in order\n"
            f"3. Acceptance criteria\n"
            f"4. Potential risks or edge cases"
        ),
        expected_output=(
            "A numbered implementation plan with file paths, clear steps, "
            "and acceptance criteria. Markdown format."
        ),
        agent=architect,
    )


# ---------------------------------------------------------------------------
# Phase 2: BUILD
# ---------------------------------------------------------------------------
def build_task(builder: Agent, plan: str) -> Task:
    return Task(
        description=(
            f"Implement the following plan by writing code.\n\n"
            f"PLAN:\n{plan}\n\n"
            f"Use WriteFile to create or update files. Use ReadFile to check "
            f"existing code before modifying. Use Shell to run commands if needed.\n"
            f"Write production-quality code with proper error handling."
        ),
        expected_output=(
            "A summary of all files created or modified, with a brief description "
            "of each change. List the exact file paths."
        ),
        agent=builder,
    )


# ---------------------------------------------------------------------------
# Phase 3: REVIEW
# ---------------------------------------------------------------------------
def review_task(reviewer: Agent, build_summary: str) -> Task:
    return Task(
        description=(
            f"Review the code changes described below. Use ReadFile and GitDiff "
            f"to inspect the actual code.\n\n"
            f"BUILD SUMMARY:\n{build_summary}\n\n"
            f"Check for:\n"
            f"- Bugs and logic errors\n"
            f"- Missing error handling\n"
            f"- Anti-patterns\n"
            f"- Naming and readability issues\n"
            f"- Missing edge cases\n\n"
            f"If the code is acceptable, respond with exactly: APPROVED\n"
            f"If changes are needed, list each issue with the file, line, and suggested fix."
        ),
        expected_output=(
            "Either 'APPROVED' (if code is clean) or a list of issues, each with "
            "file path, description, and suggested fix."
        ),
        agent=reviewer,
    )


def fix_task(builder: Agent, review_feedback: str) -> Task:
    return Task(
        description=(
            f"Address the following code review feedback by modifying the code.\n\n"
            f"REVIEW FEEDBACK:\n{review_feedback}\n\n"
            f"Read each file mentioned, apply the fixes, and write the updated files."
        ),
        expected_output=(
            "A summary of all fixes applied, listing each file and what changed."
        ),
        agent=builder,
    )


# ---------------------------------------------------------------------------
# Phase 4: QUALITY GATES
# ---------------------------------------------------------------------------
def security_task(security_agent: Agent, build_summary: str) -> Task:
    return Task(
        description=(
            f"Perform a security audit of the code changes.\n\n"
            f"BUILD SUMMARY:\n{build_summary}\n\n"
            f"Check for OWASP Top 10, XSS, injection, auth issues, secrets in code, "
            f"and insecure dependencies. Use ReadFile to inspect code. "
            f"Use Shell to run 'npm audit' or 'pip-audit' if applicable."
        ),
        expected_output=(
            "A security report listing each finding with severity (Critical/High/Medium/Low), "
            "file path, description, and remediation. If clean, say: NO ISSUES FOUND."
        ),
        agent=security_agent,
    )


def performance_task(perf_agent: Agent, build_summary: str) -> Task:
    return Task(
        description=(
            f"Analyze the code changes for performance issues.\n\n"
            f"BUILD SUMMARY:\n{build_summary}\n\n"
            f"Check for: unnecessary re-renders, large bundle imports, missing memoization, "
            f"N+1 queries, blocking operations, unoptimized images, layout shifts."
        ),
        expected_output=(
            "A performance report listing each issue with impact level, "
            "file path, and optimization suggestion. If clean, say: NO ISSUES FOUND."
        ),
        agent=perf_agent,
    )


def test_task(tester: Agent, build_summary: str) -> Task:
    return Task(
        description=(
            f"Write automated tests for the code changes.\n\n"
            f"BUILD SUMMARY:\n{build_summary}\n\n"
            f"Use ReadFile to inspect the implemented code. "
            f"Use WriteFile to create test files. "
            f"Use RunTests to verify they pass.\n"
            f"Cover happy paths, edge cases, and error paths."
        ),
        expected_output=(
            "A summary of test files created and their results (pass/fail). "
            "Include the test file paths."
        ),
        agent=tester,
    )


def lint_task(linter: Agent, build_summary: str) -> Task:
    return Task(
        description=(
            f"Run the linter on all changed files and fix any issues.\n\n"
            f"BUILD SUMMARY:\n{build_summary}\n\n"
            f"Use the Lint tool to check for errors. "
            f"Use ReadFile and WriteFile to fix any issues found."
        ),
        expected_output=(
            "Lint results showing all files are clean, or a summary of fixes applied."
        ),
        agent=linter,
    )


# ---------------------------------------------------------------------------
# Phase 5: POLISH
# ---------------------------------------------------------------------------
def refactor_task(refactorer: Agent, build_summary: str) -> Task:
    return Task(
        description=(
            f"Refactor the code changes for clarity and maintainability.\n\n"
            f"BUILD SUMMARY:\n{build_summary}\n\n"
            f"Look for: duplicated logic, unclear names, overly complex functions, "
            f"missing type annotations, dead code. "
            f"Do NOT change behavior — only improve readability."
        ),
        expected_output=(
            "A summary of refactoring changes applied, or 'NO REFACTORING NEEDED' "
            "if the code is already clean."
        ),
        agent=refactorer,
    )


def docs_task(docs_agent: Agent, build_summary: str) -> Task:
    return Task(
        description=(
            f"Write or update documentation for the code changes.\n\n"
            f"BUILD SUMMARY:\n{build_summary}\n\n"
            f"Add JSDoc/docstrings to public functions. "
            f"Update README if a new feature was added. "
            f"Add inline comments only where logic is non-obvious."
        ),
        expected_output=(
            "A summary of documentation changes, listing each file updated."
        ),
        agent=docs_agent,
    )


# ---------------------------------------------------------------------------
# Phase 6: JUDGE
# ---------------------------------------------------------------------------
def judge_task(judge: Agent, full_summary: str) -> Task:
    return Task(
        description=(
            f"Make the final approval decision on these code changes.\n\n"
            f"FULL PIPELINE SUMMARY:\n{full_summary}\n\n"
            f"Use GitDiff to review the final state of all changes. "
            f"Consider correctness, security, performance, test coverage, "
            f"and code quality.\n\n"
            f"If approved, respond with exactly: APPROVED\n"
            f"If rejected, explain what must be fixed."
        ),
        expected_output=(
            "Either 'APPROVED' or a rejection with specific reasons and required fixes."
        ),
        agent=judge,
    )
