import sqlite3
import sys
import os
import threading
from PyQt6.QtWidgets import QDialog, QApplication, QToolTip, QCheckBox, QMainWindow, QWidget, QSizePolicy, QScrollArea, \
    QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit, QPushButton, QToolButton, QAbstractButton
from PyQt6.QtGui import QPixmap, QIcon, QCursor, QContextMenuEvent
from PyQt6.QtCore import Qt, QSize,pyqtSignal
from ollimca_core.query import Query
from ollimca_core.config import Config
import textwrap


def wrap_text(text, max_width=80):
    lines = text.split('\n')
    wrapped_lines = [textwrap.fill(line, width=max_width) for line in lines]
    return '\n'.join(wrapped_lines)

class PopupDialog(QDialog):
    def __init__(self, parent=None, options=None, items_per_line=3):
        super().__init__(parent)
        if options is None:
            options = []
        self.setWindowTitle("Select Names")
        self.setGeometry(100, 100, 300, 400)
        self.layout = QVBoxLayout()

        self.checkbox_dict = {}

        items_in_line=0
        line = QHBoxLayout()
        for option in options:
            if items_in_line == items_per_line:
                items_in_line = 0
                self.layout.addLayout(line)
                line = QHBoxLayout()

            checkbox = QCheckBox(option["name"], self)
            # checkbox.setAccessibleName(option["name"])
            line.addWidget(checkbox)
            self.checkbox_dict[option["id"]] = checkbox
            items_in_line += 1

        if items_in_line > 0:
            self.layout.addLayout(line)

        self.setLayout(self.layout)

    def get_checked_names(self):
        checked_names = []
        for id,checkbox in self.checkbox_dict.items():
            if checkbox.isChecked():
                checked_names.append(id)
        return checked_names


class ClickableLabel(QLabel):
    clicked = pyqtSignal(str)
    popup = ""
    def __init__(self, path, description, parent=None):
        super().__init__(parent)
        self.path = path  # Initialize the path attribute
        self.popup = self.path
        self.setMouseTracking(True)
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        self.description = description

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.path)

    # def enterEvent(self, event):
    #     QToolTip.showText(event.globalPosition().toPoint(), f"{self.popup}", self)
    #
    def contextMenuEvent(self, event):
        if QToolTip.isVisible():
            QToolTip.hideText()
        else:
            QToolTip.showText(event.globalPos(), f"{self.description}", self)

    def leaveEvent(self, event):
        QToolTip.hideText()

class MainWindow(QMainWindow):
    chroma_path = ""
    sqlite_path = ""
    embedding_model = ""
    image_viewer = None
    ollama_emnbed=None

    already_shown_images = []
    checksums = []
    delete_duplicates_missing = False
    current_page_sql = 1
    current_page_chroma = 1
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
        self.sqlite_path = os.path.join("db", config['db']['sqlite_path'])
        self.embedding_model = config["embedding_model"]
        self.image_viewer = config["image_viewer"]
        self.ollama_embed = config["ollama_embed"]
        self.setWindowTitle("Ollimca (OLLama IMage CAtegoriser)")
        self.setGeometry(100, 100, 800, 600)
        self.known_persons = self.get_known_persons()
        self.person_popup = PopupDialog(self, options=self.known_persons)

        # Create the main widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)

        # Search form
        search_form = QWidget()
        search_form_layout = QVBoxLayout()
        search_form.setLayout(search_form_layout)  # Set the layout for the search_form

        labels = ["Content", "Mood", "Color"]
        self.inputs = {}
        button_checkbox_layout = QHBoxLayout()
        for label in labels:
            label_widget = QLabel(label)
            input_widget = QLineEdit()
            button_checkbox_layout.addWidget(label_widget)
            button_checkbox_layout.addWidget(input_widget)
            self.inputs[label] = input_widget
            input_widget.textChanged.connect(self.on_search_changed)

        search_form_layout.addLayout(button_checkbox_layout)

        options_layout = QHBoxLayout()
        delete_duplicates_checkbox = QCheckBox("Delete Duplicates and Missing Images")
        delete_duplicates_checkbox.stateChanged.connect(self.on_delete_duplicates_changed)

        button = QPushButton("Search for recognized face", self)
        button.clicked.connect(self.open_popup)
        options_layout.addWidget(delete_duplicates_checkbox)
        options_layout.addWidget(button)

        search_form_layout.addLayout(options_layout)
        # $$$$search_form_layout.addWidget(delete_duplicates_checkbox)

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

    def get_known_persons(self):
        conn = sqlite3.connect(self.sqlite_path)
        cursor = conn.cursor()
        cursor.execute('SELECT id,callname FROM persons ORDER BY callname')
        rows = cursor.fetchall()
        conn.close()
        rs=[]
        for row in rows:
            rs.append({"name":row[1],"id":row[0]})
        return rs

    def open_popup(self):
        self.person_popup.exec()

    def on_delete_duplicates_changed(self, state):
        self.delete_duplicates_missing=(state == 2)

    def on_search_changed(self):
        self.continuous_scroll = False
        self.current_page_sql = 1
        self.current_page_chroma = 1
        self.col = 0
        self.row = 0
        self.already_shown_images = []
        self.checksums = []

    def on_search_clicked(self):
        query = Query( self.sqlite_path,self.chroma_path, self.embedding_model, self.ollama_embed)
        content = self.inputs["Content"].text()
        mood = self.inputs["Mood"].text()
        color = self.inputs["Color"].text()
        wanted_persons = self.person_popup.get_checked_names()

        (image_details, self.current_page_sql, self.current_page_chroma, self.already_shown_images, self.checksums) = query.query(content, mood, color, self.current_page_sql, self.current_page_chroma, self.items_per_page, self.already_shown_images, self.checksums, self.delete_duplicates_missing, wanted_persons)
        if len(image_details) == 0:
            self.ignore_signal=True
            self.continuous_scroll=False
            self.display_fail()
        else:
            self.display_images(image_details)

    def display_fail(self):
        label = ClickableLabel("", wrap_text("No more images fitting this query were found!"))
        label.setFixedHeight(300)
        label.setFixedWidth(300)
        label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        label.setText("No more images fitting this query were found!")
        self.grid_layout.addWidget(label, self.row, self.col)

    def clear_display(self):
        # Clear previous results
        for i in reversed(range(self.grid_layout.count())):
            widget = self.grid_layout.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()
        self.row=0
        self.col=0

    def display_images(self, image_details):
        if self.continuous_scroll == False:
            self.clear_display()

        # Display new images
        self.grid_layout.setSpacing(0)
        self.ignore_signal=True
        for img_detail in image_details:
            img_path = img_detail[0]
            img_detail = img_detail[1]
            if not os.path.exists(img_path):
                continue
            label = ClickableLabel(img_path, wrap_text(img_detail))
            label.setFixedHeight(300)
            label.setFixedWidth(300)
            label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

            pixmap = QPixmap(img_path)
            if not pixmap.isNull():
                label.setPixmap(pixmap.scaled(300, 300, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))  # Scale the image to fit within a width of 300 pixels
                label.setFixedSize(QSize(300, 300))
            else:
                label.setText("Image not found")

            label.clicked.connect(lambda _, path=img_path: self.open_image(path))

            self.grid_layout.addWidget(label, self.row, self.col)
            # Move to the next column
            self.col += 1
            # If we reach the end of a row, move to the next row and reset the column counter
            if self.col >= 3:  # Assuming 3 columns per row
                self.col = 0
                self.row += 1
        if self.grid_layout.count() < self.items_per_page:
            self.continuous_scroll = True
            self.on_search_clicked()
        self.ignore_signal=False

    def on_scroll_value_changed(self, value):
        scrollbar = scroll_area.verticalScrollBar()
        if value == scrollbar.maximum() and self.ignore_signal == False:
            #self.current_page += 1
            self.continuous_scroll = True
            self.on_search_clicked()

    def open_image(self, path):
        def run_viewer():
            os.system(f'{self.image_viewer} "{path}"')

        thread = threading.Thread(target=run_viewer)
        thread.start()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    icon = QIcon("icon.png")  # Replace with your icon file path
    app.setWindowIcon(icon)
    window = MainWindow()
    window.show()

    sys.exit(app.exec())
