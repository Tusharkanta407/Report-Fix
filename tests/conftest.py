from pathlib import Path

import pytest

from engine.ingestion import load_dataset

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@pytest.fixture(scope="session")
def dataset():
    return load_dataset(DATA_DIR)


@pytest.fixture(scope="session")
def taxonomy(dataset):
    return dataset.taxonomy
