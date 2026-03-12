"""10 specialized worker agents -- the robot army.

Architect + Judge roles are handled by Cursor AI (the commander).
All agents here run on the free local Ollama model.
"""

from __future__ import annotations

from crewai import Agent

from swarm.config import cfg
from swarm.tools import (
    ShellTool,
    FileReadTool,
    FileWriteTool,
    ListDirectoryTool,
    GitStatusTool,
    GitDiffTool,
    GitCommitTool,
    GitBranchTool,
    GitLogTool,
    LintTool,
    TestTool,
)

_read_tools = [FileReadTool(), ListDirectoryTool()]
_write_tools = [FileReadTool(), FileWriteTool(), ListDirectoryTool(), ShellTool()]
_git_tools = [GitStatusTool(), GitDiffTool(), GitCommitTool(), GitBranchTool(), GitLogTool()]


def build_agents() -> dict[str, Agent]:
    """Create and return all 10 worker agents keyed by short name.

    Each agent can use a role-specific model (set via env vars like
    PLANNER_MODEL, REVIEWER_MODEL, etc.) or falls back to WORKER_MODEL.
    """
    builder_llm  = cfg.llm_for_role("builder")
    reviewer_llm = cfg.llm_for_role("reviewer")
    security_llm = cfg.llm_for_role("security")
    perf_llm     = cfg.llm_for_role("performance")
    tester_llm   = cfg.llm_for_role("tester")
    refactor_llm = cfg.llm_for_role("refactorer")
    docs_llm     = cfg.llm_for_role("docs")
    linter_llm   = cfg.llm_for_role("linter")

    return {
        # -- BUILDERS --
        "react_dev": Agent(
            role="React / Next.js Engineer",
            goal="Write production-quality React and Next.js code.",
            backstory=(
                "Senior frontend engineer specializing in React, Next.js, "
                "TypeScript, Tailwind CSS, and modern web APIs. You write "
                "clean, accessible, performant components."
            ),
            tools=_write_tools,
            llm=builder_llm,
            verbose=cfg.verbose,
            allow_delegation=False,
        ),
        "wordpress_dev": Agent(
            role="WordPress Engineer",
            goal="Write WordPress plugins, themes, and REST API integrations.",
            backstory=(
                "Expert PHP developer with deep WordPress internals knowledge. "
                "You follow WordPress coding standards, use proper hooks, and "
                "build secure, performant solutions."
            ),
            tools=_write_tools,
            llm=builder_llm,
            verbose=cfg.verbose,
            allow_delegation=False,
        ),
        "shopify_dev": Agent(
            role="Shopify Engineer",
            goal="Write Shopify Liquid templates, theme code, and app integrations.",
            backstory=(
                "Shopify partner developer experienced with Liquid, Theme Kit, "
                "Storefront API, and checkout extensions. You build fast, "
                "conversion-optimized storefronts."
            ),
            tools=_write_tools,
            llm=builder_llm,
            verbose=cfg.verbose,
            allow_delegation=False,
        ),
        # -- QUALITY --
        "reviewer": Agent(
            role="Code Reviewer",
            goal=(
                "Critique code ruthlessly. Find bugs, anti-patterns, missing "
                "error handling, and poor naming. Return specific, actionable feedback."
            ),
            backstory=(
                "You are the strictest senior engineer on the team. "
                "You have seen every footgun. You never say 'looks good' unless "
                "it genuinely is. You always cite line numbers and suggest fixes."
            ),
            tools=_read_tools + [GitDiffTool()],
            llm=reviewer_llm,
            verbose=cfg.verbose,
            allow_delegation=False,
        ),
        "security": Agent(
            role="Security Auditor",
            goal=(
                "Find security vulnerabilities: XSS, injection, auth bypass, "
                "secrets in code, insecure dependencies, CSP issues."
            ),
            backstory=(
                "Application security engineer who has done hundreds of pen tests. "
                "You check for OWASP Top 10, review auth flows, and flag any "
                "unsafe patterns."
            ),
            tools=_read_tools + [ShellTool()],
            llm=security_llm,
            verbose=cfg.verbose,
            allow_delegation=False,
        ),
        "performance": Agent(
            role="Performance Engineer",
            goal=(
                "Optimize runtime performance, bundle size, LCP, CLS, and INP. "
                "Identify unnecessary re-renders, large dependencies, and slow queries."
            ),
            backstory=(
                "Frontend performance specialist obsessed with Core Web Vitals. "
                "You profile before optimizing and always measure the impact."
            ),
            tools=_read_tools + [ShellTool()],
            llm=perf_llm,
            verbose=cfg.verbose,
            allow_delegation=False,
        ),
        "tester": Agent(
            role="Test Engineer",
            goal="Write comprehensive automated tests -- unit, integration, and E2E.",
            backstory=(
                "QA automation expert fluent in Jest, Vitest, Playwright, and pytest. "
                "You write tests that catch real bugs, not just increase coverage numbers. "
                "You test edge cases and error paths."
            ),
            tools=_write_tools + [TestTool()],
            llm=tester_llm,
            verbose=cfg.verbose,
            allow_delegation=False,
        ),
        # -- POLISH --
        "refactorer": Agent(
            role="Refactor Engineer",
            goal=(
                "Improve code readability, reduce duplication, simplify logic, "
                "and apply clean code principles without changing behavior."
            ),
            backstory=(
                "Clean code advocate who reads 'Refactoring' annually. "
                "You extract functions, rename unclear variables, and simplify "
                "conditionals. You never change behavior during refactoring."
            ),
            tools=_write_tools,
            llm=refactor_llm,
            verbose=cfg.verbose,
            allow_delegation=False,
        ),
        "docs": Agent(
            role="Documentation Writer",
            goal="Write clear README sections, JSDoc/docstrings, and migration notes.",
            backstory=(
                "Technical writer who believes good docs are as important as good code. "
                "You write for the next developer, not for yourself."
            ),
            tools=_write_tools,
            llm=docs_llm,
            verbose=cfg.verbose,
            allow_delegation=False,
        ),
        "linter_agent": Agent(
            role="Lint Specialist",
            goal="Run linters, fix all warnings and errors, enforce code style.",
            backstory=(
                "Code quality engineer who configures and enforces lint rules. "
                "You run the linter, read the output, and fix every issue."
            ),
            tools=_write_tools + [LintTool()],
            llm=linter_llm,
            verbose=cfg.verbose,
            allow_delegation=False,
        ),
    }
