"""
ui/main_window.py
Main application window with chat sidebar and HTML content area.
Agent now runs in a background thread – UI stays responsive.
"""

from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QObject
from PySide6.QtWebEngineWidgets import QWebEngineView
from llm_client import LLMClient, detect_running_server
from agent.orchestrator import run_sub_agent

class AgentWorker(QObject):
    """Runs the sub‑agent in a separate thread."""
    finished = Signal(str)              # final answer (or error message)
    status_update = Signal(str)         # blue agent status messages
    html_update = Signal(str)           # HTML for the content area

    def __init__(self, llm, task):
        super().__init__()
        self.llm = llm
        self.task = task

    def run(self):
        # The function we call; status and html callbacks emit signals.
        def status_cb(msg):
            self.status_update.emit(msg)
        def html_cb(html):
            self.html_update.emit(html)

        result = run_sub_agent(
            self.llm,
            self.task,
            update_html_callback=html_cb,
            status_callback=status_cb
        )
        self.finished.emit(result)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Agent Desktop")
        self.resize(1200, 800)

        # Initialize LLM client
        endpoint = detect_running_server()
        if not endpoint:
            endpoint = "http://localhost:11434/v1"
        self.llm = LLMClient(base_url=endpoint, model="llama3.2")

        self.setup_ui()
        self.append_message("System", "Connected to LLM. I'm ready to help. Try asking me to search for something and present results.")

        # Track worker thread
        self.worker_thread = None
        self.worker = None

    def setup_ui(self):
        splitter = QSplitter(Qt.Horizontal)

        # Sidebar
        sidebar = QWidget()
        sidebar.setMinimumWidth(300)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(5, 5, 5, 5)

        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setStyleSheet("background-color: #f5f5f5; font-size: 13px;")
        sidebar_layout.addWidget(self.chat_history)

        input_layout = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("What should I do?")
        self.input_field.returnPressed.connect(self.send_message)
        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send_message)
        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.send_button)
        sidebar_layout.addLayout(input_layout)

        # Content area
        self.content_view = QWebEngineView()
        self.content_view.setHtml("<h2 style='color: gray; text-align: center; margin-top: 50px;'>Agent output will appear here</h2>")

        splitter.addWidget(sidebar)
        splitter.addWidget(self.content_view)
        splitter.setSizes([350, 850])

        self.setCentralWidget(splitter)

    def append_message(self, sender: str, message: str):
        self.chat_history.append(f"<b>{sender}:</b> {message}")

    def append_agent_status(self, message: str):
        self.chat_history.append(f"<span style='color: blue;'><b>Agent:</b> {message}</span>")

    def send_message(self):
        if self.worker_thread and self.worker_thread.isRunning():
            self.append_message("System", "Agent is still working. Please wait.")
            return

        user_text = self.input_field.text().strip()
        if not user_text:
            return

        self.append_message("You", user_text)
        self.input_field.clear()

        # Disable input
        self.input_field.setEnabled(False)
        self.send_button.setEnabled(False)
        self.send_button.setText("Working...")

        # Launch agent in background
        self.start_agent_thread(user_text)

    def start_agent_thread(self, task):
        # Create worker and thread
        self.worker_thread = QThread()
        self.worker = AgentWorker(self.llm, task)
        self.worker.moveToThread(self.worker_thread)

        # Connect signals
        self.worker.status_update.connect(self.append_agent_status)
        self.worker.html_update.connect(self.content_view.setHtml)
        self.worker.finished.connect(self.on_agent_finished)

        # Clean up thread when done
        self.worker_thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)

        self.worker_thread.start()

    def on_agent_finished(self, result):
        self.append_message("Assistant", result)
        # If it looks like HTML, push to content view
        if result.strip().startswith("<") and ">" in result:
            self.content_view.setHtml(result)

        # Re-enable input
        self.input_field.setEnabled(True)
        self.send_button.setEnabled(True)
        self.send_button.setText("Send")
        self.input_field.setFocus()