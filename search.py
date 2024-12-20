import sys
import os
import threading
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QSizePolicy, QScrollArea, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit, QPushButton
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt, QSize,pyqtSignal
from ollimca_core.query import Query
from ollimca_core.config import Config

class ClickableLabel(QLabel):
    clicked = pyqtSignal(str)

    def __init__(self, path, parent=None):
        super().__init__(parent)
        self.path = path  # Initialize the path attribute
        self.setMouseTracking(True)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.path)


class MainWindow(QMainWindow):
    chroma_path = ""
    embedding_model = ""
    image_viewer = None

    current_page = 1
    items_per_page = 12
    continuous_scroll = False
    do_not_scroll = False
    row = 0
    col = 0

    def __init__(self):
        super().__init__()
        global scroll_area

        cfg = Config()
        config = cfg.ReadConfig()
        self.chroma_path = os.path.join("db", config['db']['chroma_path'])
        self.embedding_model = config["embedding_model"]
        self.image_viewer = config["image_viewer"]

        self.setWindowTitle("Ollimca (OLLama IMage CAtegoriser)")
        self.setGeometry(100, 100, 800, 600)

        # Create the main widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)

        # Search form
        search_form = QWidget()
        search_form_layout = QHBoxLayout()
        search_form.setLayout(search_form_layout)

        labels = ["Content", "Mood", "Color"]
        self.inputs = {}

        for label in labels:
            label_widget = QLabel(label)
            input_widget = QLineEdit()
            search_form_layout.addWidget(label_widget)
            search_form_layout.addWidget(input_widget)
            self.inputs[label] = input_widget
            input_widget.textChanged.connect(self.on_search_changed)

        search_button = QPushButton("Search")
        search_button.clicked.connect(self.on_search_clicked)
        search_form_layout.addWidget(search_button)

        main_layout.addWidget(search_form)


        # Results display
        results_display = QWidget()
        self.grid_layout = QGridLayout(results_display)
        scroll_area = QScrollArea()
        scroll_area.setStyleSheet("""
            background-color: #111111;
            color: #dddddd;
        """)
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setWidget(results_display)
        main_layout.addWidget(scroll_area)

        results_display.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Connect the scrollbar's valueChanged signal to a slot
        scroll_area.verticalScrollBar().valueChanged.connect(self.on_scroll_value_changed)

    def on_search_changed(self):
        self.current_page = 1
        self.continuous_scroll = False
        self.current_page = 1
        self.col = 0
        self.row = 0

    def on_search_clicked(self):
        query = Query(self.chroma_path, self.embedding_model)

        content = self.inputs["Content"].text()
        mood = self.inputs["Mood"].text()
        color = self.inputs["Color"].text()
        image_paths = query.Query(content, mood, color, self.current_page, self.items_per_page)
        self.display_images(image_paths)

    def display_images(self, image_paths):
        if self.continuous_scroll == False:
            # Clear previous results
            for i in reversed(range(self.grid_layout.count())):
                widget = self.grid_layout.itemAt(i).widget()
                if widget is not None:
                    widget.deleteLater()
            self.row=0
            self.col=0

        # Display new images
        self.grid_layout.setSpacing(0)
        self.ignore_signal=True
        for path in image_paths:
            label = ClickableLabel(path)
            label.setFixedHeight(300)
            label.setFixedWidth(300)
            label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

            pixmap = QPixmap(path)
            if not pixmap.isNull():
                label.setPixmap(pixmap.scaled(300, 300, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))  # Scale the image to fit within a width of 300 pixels
                label.setFixedSize(QSize(300, 300))
            else:
                label.setText("Image not found")

            label.clicked.connect(lambda _, path=path: self.open_image(path))

            self.grid_layout.addWidget(label, self.row, self.col)
            # Move to the next column
            self.col += 1
            # If we reach the end of a row, move to the next row and reset the column counter
            if self.col >= 3:  # Assuming 3 columns per row
                self.col = 0
                self.row += 1
        self.ignore_signal=False

    def on_scroll_value_changed(self, value):
        scrollbar = scroll_area.verticalScrollBar()
        if value == scrollbar.maximum() and self.ignore_signal == False:
            self.current_page += 1
            self.continuous_scroll = True
            self.on_search_clicked()

    def open_image(self, path):
        def run_viewer():
            os.system(f'{self.image_viewer} "{path}"')

        thread = threading.Thread(target=run_viewer)
        thread.start()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()

    sys.exit(app.exec())
