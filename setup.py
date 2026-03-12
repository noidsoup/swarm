"""Setup configuration for AI Dev Swarm."""

from setuptools import setup, find_packages

BASE_REQUIREMENTS = [
    "crewai[tools]>=0.108.0",
    "litellm>=1.0.0",
    "python-dotenv>=1.1.0",
    "requests>=2.31.0",
    "pydantic>=2.10.0",
    "mcp>=1.0.0",
    "watchdog>=3.0.0",
]

setup(
    name="ai-dev-swarm",
    version="0.1.0",
    description="11-agent coding swarm with CrewAI + Ollama. Cursor as commander.",
    author="noidsoup",
    url="https://github.com/noidsoup/swarm",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=BASE_REQUIREMENTS,
    extras_require={
        "docker": [
            "fastapi>=0.115.0",
            "uvicorn[standard]>=0.34.0",
            "redis>=5.0.0",
            "rq>=2.0.0",
            "httpx>=0.28.0",
            "sse-starlette>=2.0.0",
            "psutil>=6.0.0",
        ],
        "client": [
            "httpx>=0.28.0",
            "rich>=13.0.0",
        ],
    },
    scripts=[
        "swarm-run",
        "swarm-daemon",
        "swarm-run.bat",
        "swarm-daemon.bat",
    ],
    entry_points={
        "console_scripts": [
            "swarm-run=swarm.cli:main",
            "swarm-daemon=swarm.daemon_cli:main",
        ],
    },
    include_package_data=True,
)
