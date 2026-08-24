import sys
import os
from pathlib import Path
import pytest

# Add workspace directory to sys.path
workspace_dir = Path(__file__).resolve().parent.parent
if str(workspace_dir) not in sys.path:
    sys.path.insert(0, str(workspace_dir))
