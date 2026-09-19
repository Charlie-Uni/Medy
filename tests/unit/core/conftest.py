import logging

import pytest


@pytest.fixture(autouse=True)
def restore_root_logging():
    """configure_logging() replaces root handlers; keep other tests (and caplog) unaffected."""
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    yield
    root.handlers = handlers
    root.setLevel(level)
