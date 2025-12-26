"""
Marstek Venus E API Client using UDP.

This module imports the standalone API client for use in Home Assistant.
The standalone version (../../marstek_api.py) can be used for testing
without Home Assistant dependencies.
"""
# The API client is defined in a standalone file so it can be tested
# without Home Assistant. We import and re-export it here for the integration.
import sys
from pathlib import Path

# Add the parent directory to the path to import marstek_api
_parent_dir = Path(__file__).parent.parent.parent
if str(_parent_dir) not in sys.path:
    sys.path.insert(0, str(_parent_dir))

# Import from standalone API
from marstek_api import (
    MarstekApiClient,
    MarstekConnectionError,
    MarstekApiError,
    MarstekProtocol,
    TIMEOUT,
)

# Re-export for use in integration
__all__ = [
    "MarstekApiClient",
    "MarstekConnectionError",
    "MarstekApiError",
    "MarstekProtocol",
    "TIMEOUT",
]
