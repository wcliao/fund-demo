import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from simulation.generate_funds import generate_funds  # noqa: E402


@pytest.fixture(scope="session")
def demo_data():
    return generate_funds()
