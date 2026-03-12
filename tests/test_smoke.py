"""Basic smoke tests for local verification and CI sanity."""


def test_import_main_modules() -> None:
    """Ensure key merged modules remain importable."""
    import swarm.api  # noqa: F401
    import swarm.task_store  # noqa: F401
    import swarm.worker  # noqa: F401
