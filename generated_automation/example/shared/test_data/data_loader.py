"""Test data loader utility."""
import json
from pathlib import Path
from typing import Any, Dict

def load_test_data(filename: str = "test_data.json") -> Dict[str, Any]:
    """Load JSON test data from shared/test_data directory."""
    data_path = Path(__file__).resolve().parent / filename
    if data_path.is_file():
        return json.loads(data_path.read_text(encoding="utf-8"))
    return {}
