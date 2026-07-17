"""
agent/workspace.py
Manages per-project workspace directories.
"""

import os
import datetime

class Workspace:
    def __init__(self, base_dir: str = "workspace"):
        self.base_dir = base_dir
        self.current_project = None

    def new_project(self, name: str = None) -> str:
        """Create a new project folder and return its path."""
        if name is None:
            name = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        project_path = os.path.join(self.base_dir, name)
        os.makedirs(project_path, exist_ok=True)
        self.current_project = project_path
        return project_path

    def get_path(self, relative: str = "") -> str:
        """Return the absolute path inside the current project."""
        if not self.current_project:
            raise RuntimeError("No active project. Call new_project() first.")
        return os.path.join(self.current_project, relative)