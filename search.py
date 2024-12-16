import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit, QPushButton, QTextEdit
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt
import requests

class MainWindow(QMainWindow):
    def __init__(self):
        global results_display
        super().__init__()

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

        labels = ["Content", "Mood", "Intent", "Color"]
        self.inputs = {}

        for label in labels:
            label_widget = QLabel(label)
            input_widget = QLineEdit()
            search_form_layout.addWidget(label_widget)
            search_form_layout.addWidget(input_widget)
            self.inputs[label] = input_widget

        search_button = QPushButton("Search")
        search_button.clicked.connect(self.on_search_clicked)
        search_form_layout.addWidget(search_button)

        main_layout.addWidget(search_form)

        # Results display
        self.results_display = QWidget()
        self.grid_layout = QGridLayout()
        self.results_display.setLayout(self.grid_layout)
        self.results_display.setStyleSheet("""
            background-color: #111111;
            color: #dddddd;
            font-weight: bold;
            font-size: small;
            margin-top: 20px;
            padding: 10px;
            border: 1px inset #ccc;
            min-height: 50px;
        """)
        main_layout.addWidget(self.results_display)

    def on_search_clicked(self):
        content = self.inputs["Content"].text()
        mood = self.inputs["Mood"].text()
        intent = self.inputs["Intent"].text()
        color = self.inputs["Color"].text()

        # Send HTTP POST request to the backend
        url = "http://127.0.0.1:9706/api/query"
        data = {
            "content": content,
            "mood": mood,
            "intent": intent,
            "color": color
        }
        response = requests.post(url, json=data)

        if response.status_code == 200:
            image_paths = response.json()
            self.display_images(image_paths)
        else:
            label = QLabel(f"Error: {response.status_code}")
            self.grid_layout.addWidget(label, 0, 0)  # Add error message to the grid

    def display_images(self, image_paths):
        # Clear previous results
        for i in reversed(range(self.grid_layout.count())):
            widget = self.grid_layout.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()

        # Display new images
        row = 0
        col = 0
        for path in image_paths:
            label = QLabel()
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                label.setPixmap(pixmap.scaled(300, 300, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))  # Scale the image to fit within a width of 300 pixels
            else:
                label.setText("Image not found")
            self.grid_layout.addWidget(label, row, col)
            # Move to the next column
            col += 1
            # If we reach the end of a row, move to the next row and reset the column counter
            if col >= 3:  # Assuming 3 columns per row
                col = 0
                row += 1

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()

    sys.exit(app.exec())
