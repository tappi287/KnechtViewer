import sys
from typing import Union

from PySide2.QtGui import QDragMoveEvent, QDragEnterEvent, Qt, QDropEvent
from PySide2.QtWidgets import QApplication, QVBoxLayout, QLabel, QMainWindow, QWidget, QTreeWidget, QTreeView


class Example(QMainWindow):
    def __init__(self):
        super().__init__()
        central_widget, layout = QWidget(self), QVBoxLayout(self)
        central_widget.setLayout(layout)

        label = QLabel('Drag file from your local file system on this window', self)
        layout.addWidget(label)

        self.file_label = QLabel('<No file set>')
        layout.addWidget(self.file_label)

        tree_view = QTreeView(self)
        tree_view.setDragDropMode(QTreeView.DragDrop)
        tree_view.dropEvent = self.dropEvent
        tree_view.dragEnterEvent = self.dragEnterEvent
        tree_view.dragMoveEvent = self.dragMoveEvent
        tree_view.setAcceptDrops(True)
        layout.addWidget(tree_view)

        self.setCentralWidget(central_widget)
        self.setWindowTitle('DnD Example')
        self.setGeometry(800, 600, 800, 400)
        self.setAcceptDrops(True)

    def _handle_drag_event(self, e: Union[QDragMoveEvent, QDragEnterEvent]):
        if e.mimeData().hasUrls():
            e.setDropAction(Qt.LinkAction)
            e.accept(self.rect())
        else:
            e.ignore()

    def dragMoveEvent(self, e: QDragMoveEvent):
        self._handle_drag_event(e)

    def dragEnterEvent(self, e: QDragEnterEvent):
        self._handle_drag_event(e)

    def dropEvent(self, e: QDropEvent):
        for url in e.mimeData().urls():
            if url.isLocalFile():
                self.file_label.setText(url.toLocalFile())
                break
        e.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = Example()
    ex.show()
    app.exec_()