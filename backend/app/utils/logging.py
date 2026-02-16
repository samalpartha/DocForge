"""
DocForge CLI — Pipeline step logger with duration tracking.
"""

import logging
import time
from contextlib import contextmanager
from typing import Generator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger("docforge")


@contextmanager
def step_timer(step_name: str) -> Generator[None, None, None]:
    """Context manager that logs the start and duration of a pipeline step."""
    logger.info("▶ %s — started", step_name)
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info("✔ %s — completed in %.0f ms", step_name, elapsed_ms)
