"""Entry point for PyInstaller .exe build."""
import sys
import os

# Ensure the src directory is on the path when running as frozen exe
if getattr(sys, 'frozen', False):
    base_dir = sys._MEIPASS  # type: ignore[attr-defined]
    os.environ.setdefault("AGENT_WORKSPACE_ROOT", os.path.expanduser("~"))
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))

from agent_app.tray import launch_jarvis

if __name__ == "__main__":
    launch_jarvis()
