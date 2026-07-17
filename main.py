# main.py
import os
# Force software rendering before anything else
os.environ["QT_OPENGL"] = "software"
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
os.environ["QT_QUICK_BACKEND"] = "software"

import subprocess
import sys
import importlib

REQUIRED_PACKAGES = [
    "PySide6",
    "requests",
    "duckduckgo_search",
]

def install_packages(packages):
    print("Installing required packages...")
    for package in packages:
        print(f"  - Installing {package}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    print("Installation complete.\n")

def check_dependencies():
    for pkg in REQUIRED_PACKAGES:
        try:
            importlib.import_module(pkg)
        except ImportError:
            return False
    return True

def main():
    if not check_dependencies():
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            if messagebox.askyesno(
                "Missing Dependencies",
                "Required packages are not installed.\nDo you want to install them now?"
            ):
                root.destroy()
                install_packages(REQUIRED_PACKAGES)
            else:
                root.destroy()
                sys.exit("Cannot run without dependencies.")
        except ImportError:
            print("Missing dependencies. Install manually:")
            print(f"  pip install {' '.join(REQUIRED_PACKAGES)}")
            sys.exit(1)

    # Set AA_UseSoftwareOpenGL BEFORE creating QApplication
    from PySide6.QtCore import Qt, QCoreApplication
    QCoreApplication.setAttribute(Qt.AA_UseSoftwareOpenGL)

    from PySide6.QtWidgets import QApplication
    from ui.main_window import MainWindow

    app = QApplication(sys.argv)
    # No need to call app.setAttribute again – it's already set

    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()