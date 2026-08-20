from __future__ import annotations

import qtawesome as qta

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QPlainTextEdit,
    QToolButton,
    QVBoxLayout,
)


class DocumentStatusDialog(QDialog):
    def __init__(self, parent=None, *, lines: list[str]) -> None:
        super().__init__(parent)
        self.setWindowTitle("Document Status")
        self.setWindowIcon(qta.icon("mdi6.file-document-check-outline"))
        self.setMinimumSize(560, 320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.status_view = QPlainTextEdit(self)
        self.status_view.setObjectName("documentStatusView")
        self.status_view.setReadOnly(True)
        self.status_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.status_view.setPlainText("\n".join(lines))
        layout.addWidget(self.status_view, 1)

        footer_row = QHBoxLayout()
        footer_row.setContentsMargins(0, 0, 0, 0)
        footer_row.setSpacing(4)

        self.copy_button = QToolButton(self)
        self.copy_button.setObjectName("documentStatusCopyButton")
        self.copy_button.setAutoRaise(True)
        self.copy_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self._copy_button_icon = qta.icon("msc.clippy")
        self._copy_success_icon = qta.icon("msc.check")
        self._copy_button_tooltip = "Copy text to clipboard"
        self._copy_success_tooltip = "Copied to clipboard"
        self._copy_feedback_timer = QTimer(self)
        self._copy_feedback_timer.setSingleShot(True)
        self._copy_feedback_timer.setInterval(700)
        self._copy_feedback_timer.timeout.connect(self._restore_copy_button_feedback)
        self.copy_button.setIcon(self._copy_button_icon)
        self.copy_button.setToolTip(self._copy_button_tooltip)
        self.copy_button.setStatusTip(self.copy_button.toolTip())
        self.copy_button.clicked.connect(self.copy_to_clipboard)
        footer_row.addWidget(self.copy_button, 0)
        footer_row.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        buttons.rejected.connect(self.reject)
        footer_row.addWidget(buttons, 0)

        layout.addLayout(footer_row, 0)

    def copy_to_clipboard(self) -> None:
        QApplication.clipboard().setText(self.status_view.toPlainText())
        self.copy_button.setIcon(self._copy_success_icon)
        self.copy_button.setToolTip(self._copy_success_tooltip)
        self.copy_button.setStatusTip(self.copy_button.toolTip())
        self._copy_feedback_timer.start()

    def _restore_copy_button_feedback(self) -> None:
        self.copy_button.setIcon(self._copy_button_icon)
        self.copy_button.setToolTip(self._copy_button_tooltip)
        self.copy_button.setStatusTip(self.copy_button.toolTip())
