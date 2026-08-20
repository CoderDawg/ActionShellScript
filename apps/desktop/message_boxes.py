from __future__ import annotations

from PySide6.QtWidgets import QAbstractButton, QMessageBox, QWidget


def build_save_discard_cancel_box(
    parent: QWidget | None,
    title: str,
    text: str,
) -> tuple[QMessageBox, QAbstractButton, QAbstractButton, QAbstractButton]:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Question)
    box.setWindowTitle(title)
    box.setText(text)
    save_button = box.addButton("Save", QMessageBox.ButtonRole.AcceptRole)
    discard_button = box.addButton("Don't Save", QMessageBox.ButtonRole.DestructiveRole)
    cancel_button = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(save_button)
    box.setEscapeButton(cancel_button)
    return box, save_button, discard_button, cancel_button


def question_save_discard_cancel(parent: QWidget | None, title: str, text: str) -> QMessageBox.StandardButton:
    box, save_button, discard_button, _cancel_button = build_save_discard_cancel_box(parent, title, text)
    box.exec()
    clicked_button = box.clickedButton()
    if clicked_button == save_button:
        return QMessageBox.StandardButton.Save
    if clicked_button == discard_button:
        return QMessageBox.StandardButton.Discard
    return QMessageBox.StandardButton.Cancel
