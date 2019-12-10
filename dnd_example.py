import sys
from typing import Union

from PySide2.QtCore import QObject, QRect, Signal
from PySide2.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent, Qt
from PySide2.QtWidgets import QApplication, QLabel, QMainWindow, QTreeView, QVBoxLayout, QWidget


def handle_drag_event(e: Union[QDragMoveEvent, QDragEnterEvent], rect: QRect):
    """ Accept all URLs in dragEnter and dragMove Events inside the provided rect """
    if e.mimeData().hasUrls():
        e.setDropAction(Qt.LinkAction)
        e.accept(rect)
    else:
        e.ignore()


def handle_drop_event(e: QDropEvent, callback):
    for url in e.mimeData().urls():
        if url.isLocalFile():
            callback(f'Yay it works! {url.toLocalFile()}')
            e.accept()
            return

    e.ignore()


class DragNDropHandler(QObject):
    file_dropped = Signal(str)

    def __init__(self, widget: Union[QWidget, QTreeView]):
        super(DragNDropHandler, self).__init__(widget)

        if type(widget) is QTreeView:
            widget.setDragDropMode(QTreeView.DragDrop)

        widget.dropEvent = self.drop_event
        widget.dragEnterEvent = self.drag_enter_event
        widget.dragMoveEvent = self.drag_move_event
        widget.setAcceptDrops(True)

        self.widget = widget

    def drag_move_event(self, e: QDragMoveEvent):
        handle_drag_event(e, self.widget.rect())

    def drag_enter_event(self, e: QDragEnterEvent):
        handle_drag_event(e, self.widget.rect())

    def drop_event(self, e: QDropEvent):
        handle_drop_event(e, self.file_dropped.emit)


def create_ui_contents(parent: Union[QWidget, QMainWindow], layout: QVBoxLayout) -> QWidget:
    """ Fill either Window or Widget example with UI Elements """
    label = QLabel('Drag file from your local file system on this window', parent)
    layout.addWidget(label)

    file_label = QLabel('<No file set>')
    layout.addWidget(file_label)

    tree_view = QTreeView(parent)
    tree_view.drag_n_drop_handler = DragNDropHandler(tree_view)
    tree_view.drag_n_drop_handler.file_dropped.connect(file_label.setText)
    layout.addWidget(tree_view)

    parent.setWindowTitle('DnD Example')
    parent.setGeometry(800, 600, 800, 400)
    parent.setAcceptDrops(True)

    return file_label


class ExampleWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        central_widget, layout = QWidget(self), QVBoxLayout(self)
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        self.file_label = create_ui_contents(self, layout)
        self.setLayout(layout)

    def dragEnterEvent(self, event: QDragEnterEvent):
        handle_drag_event(event, self.rect())

    def dragMoveEvent(self, event: QDragMoveEvent):
        handle_drag_event(event, self.rect())

    def dropEvent(self, event: QDropEvent):
        handle_drop_event(event, self.file_label.setText)


class ExampleWidget(QWidget):
    def __init__(self):
        super(ExampleWidget, self).__init__()

        layout = QVBoxLayout(self)
        self.file_label = create_ui_contents(self, layout)
        self.setLayout(layout)

    def dragEnterEvent(self, event: QDragEnterEvent):
        handle_drag_event(event, self.rect())

    def dragMoveEvent(self, event: QDragMoveEvent):
        handle_drag_event(event, self.rect())

    def dropEvent(self, event: QDropEvent):
        handle_drop_event(event, self.file_label.setText)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = ExampleWindow()
    ex_widget = ExampleWidget()
    ex.show()
    ex_widget.show()

    app.exec_()
