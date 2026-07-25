from __future__ import annotations

from typing import Protocol

from PySide6.QtGui import QUndoCommand


class ProjectTarget(Protocol):
    def _set_project_json(self, project_json: str) -> None: ...


class ReplaceProjectCommand(QUndoCommand):
    def __init__(
        self,
        controller: ProjectTarget,
        before_json: str,
        after_json: str,
        label: str,
    ) -> None:
        super().__init__(label)
        self.controller = controller
        self.before_json = before_json
        self.after_json = after_json

    def redo(self) -> None:
        self.controller._set_project_json(self.after_json)

    def undo(self) -> None:
        self.controller._set_project_json(self.before_json)
