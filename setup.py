"""Setup configuration for AI Dev Swarm."""

from setuptools import setup, find_packages

setup(
    name="ai-dev-swarm",
    version="0.1.0",
    description="10-agent coding swarm with CrewAI + Ollama. Cursor as commander.",
    author="noidsoup",
    url="https://github.com/noidsoup/swarm",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "crewai>=0.30.0",
        "crewai-tools>=0.5.0",
        "langchain-community>=0.0.10",
        "ollama>=0.1.0",
        "gitpython>=3.1.0",
        "watchdog>=3.0.0",
    ],
    entry_points={
        "console_scripts": [
            "swarm-run=run:main",
            "swarm-daemon=swarm.background_loop:start_background_daemon",
        ],
    },
    include_package_data=True,
)
