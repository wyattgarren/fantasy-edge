import json
from pathlib import Path
from typing import Any, Callable

import pytest

from data.cache import FileCache

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def load_fixture() -> Callable[[str], Any]:
    def _load(name: str) -> Any:
        return json.loads((FIXTURES_DIR / name).read_text())

    return _load


@pytest.fixture
def cache(tmp_path: Path) -> FileCache:
    return FileCache(tmp_path / "cache")
