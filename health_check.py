"""Health check — print current status."""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.state import read_status

status = read_status()
print(json.dumps(status, indent=2))
