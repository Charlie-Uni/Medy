"""Shared composition test support; no collected test cases."""

from medops.core.config import Settings


def settings(**kwargs):
    return Settings(
        _env_file=None,
        database_url="postgresql://test:test@localhost/test",
        redis_url="redis://localhost:6379/0",
        **kwargs,
    )
