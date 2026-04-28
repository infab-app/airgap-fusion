"""Test package — mocks the adsk module and sets up sys.path.

Requires Python 3.10+ (the codebase uses PEP 604 union syntax: X | None).
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

MIN_PYTHON = (3, 10)
if sys.version_info < MIN_PYTHON:
    raise RuntimeError(
        f"Tests require Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ (found {sys.version}). "
        "The AirGap codebase uses PEP 604 union type syntax (X | None)."
    )

# Mock the Fusion SDK before any AirGap imports
adsk_mock = MagicMock()
adsk_mock.core = MagicMock()
adsk_mock.fusion = MagicMock()
adsk_mock.cam = MagicMock()

# Make Application.get().userName return a real string so JSON serialization works
adsk_mock.core.Application.get.return_value.userName = "test_user"

sys.modules["adsk"] = adsk_mock
sys.modules["adsk.core"] = adsk_mock.core
sys.modules["adsk.fusion"] = adsk_mock.fusion
sys.modules["adsk.cam"] = adsk_mock.cam

# Add AirGap source to path so imports resolve
AIRGAP_DIR = Path(__file__).parent.parent / "AirGap"
if str(AIRGAP_DIR) not in sys.path:
    sys.path.insert(0, str(AIRGAP_DIR))
