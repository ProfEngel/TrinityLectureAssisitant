import sys
import os
from PySide6.QtCore import Qt, QUrl, QTimer, QObject, QEvent
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QLineEdit, QVBoxLayout
from PySide6.QtWebEngineWidgets import QWebEngineView

class ContentResizeFilter(QObject):
    """EventFilter der auf dem WebEngine-FocusProxy lauscht und Resize an den Rändern ermöglicht."""
    GRIP = 14  # Pixel-Zone am Rand

    def __init__(self, window):
        super().__init__(window)
        self.win = window
        self.resizing = False
        self.dragging = False
        self.edges = ()
        self.drag_start = None
        self.start_geo = None
        self.window_start = None

    def _detect_edges(self, local_pos):
        w, h = self.win.width(), self.win.height()
        g = self.GRIP
        edges = []
        if local_pos.x() >= w - g: edges.append("r")
        if local_pos.y() >= h - g: edges.append("b")
        if local_pos.x() <= g: edges.append("l")
        if local_pos.y() <= g: edges.append("t")
        return tuple(edges)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.LeftButton:
            edges = self._detect_edges(event.position().toPoint())
            if edges:
                self.resizing = True
                self.edges = edges
                self.drag_start = event.globalPosition().toPoint()
                self.start_geo = self.win.geometry()
                return True
            else:
                local_pos = event.position().toPoint()
                # Top 50 pixels for dragging, excluding the top-right 50 pixels for the close button
                if local_pos.y() < 50 and local_pos.x() < self.win.width() - 50:
                    self.dragging = True
                    self.drag_start = event.globalPosition().toPoint()
                    self.window_start = self.win.pos()
                    return True # Event konsumieren, damit Browser den Drag nicht stiehlt
                return False
        elif event.type() == QEvent.Type.MouseMove:
            if self.resizing and self.drag_start:
                from PySide6.QtCore import QRect
                delta = event.globalPosition().toPoint() - self.drag_start
                g = self.start_geo
                x, y, w, h = g.x(), g.y(), g.width(), g.height()
                minW, minH = self.win.minimumWidth(), self.win.minimumHeight()
                if "r" in self.edges: w = max(minW, g.width() + delta.x())
                if "b" in self.edges: h = max(minH, g.height() + delta.y())
                if "l" in self.edges:
                    nw = max(minW, g.width() - delta.x())
                    x = g.x() + g.width() - nw; w = nw
                if "t" in self.edges:
                    nh = max(minH, g.height() - delta.y())
                    y = g.y() + g.height() - nh; h = nh
                self.win.setGeometry(QRect(x, y, w, h))
                return True
            elif self.dragging and self.drag_start and self.window_start:
                delta = event.globalPosition().toPoint() - self.drag_start
                self.win.move(self.window_start + delta)
                return True
            # Cursor-Feedback am Rand
            edges = self._detect_edges(event.position().toPoint())
            if ("r" in edges and "b" in edges) or ("l" in edges and "t" in edges):
                self.win.setCursor(Qt.SizeFDiagCursor)
            elif ("l" in edges and "b" in edges) or ("r" in edges and "t" in edges):
                self.win.setCursor(Qt.SizeBDiagCursor)
            elif "r" in edges or "l" in edges:
                self.win.setCursor(Qt.SizeHorCursor)
            elif "b" in edges or "t" in edges:
                self.win.setCursor(Qt.SizeVerCursor)
            else:
                self.win.setCursor(Qt.ArrowCursor)
        elif event.type() == QEvent.Type.MouseButtonRelease:
            if self.resizing:
                self.resizing = False
                self.edges = ()
                return True
            if self.dragging:
                self.dragging = False
                return False
        return False


class ContentWindow(QMainWindow):
    DEFAULT_W = 750
    DEFAULT_H = 700

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_MacAlwaysShowToolWindow, True)
        self.resize(self.DEFAULT_W, self.DEFAULT_H)
        self.setMinimumSize(350, 300)
        self.is_sticky = False
        
        self.browser = QWebEngineView(self)
        self.browser.setAttribute(Qt.WA_TranslucentBackground)
        self.browser.page().setBackgroundColor(Qt.transparent)
        self.setCentralWidget(self.browser)

        # Resize-Filter auf dem WebEngine-Proxy installieren
        self._resize_filter = ContentResizeFilter(self)
        QTimer.singleShot(200, self._install_resize_filter)

        # URL-Hash-Listener für auto Image-Sizing
        self.browser.urlChanged.connect(self._on_url_changed)

    def _on_url_changed(self, url):
        """Passt Fenstergröße an Bildgröße an wenn IMAGE_PAYLOAD gesetzt."""
        fragment = url.fragment()
        if fragment == "close":
            self.is_sticky = False
            self.hide_content()
            return

        if fragment.startswith("imgsize_"):
            try:
                _, w, h = fragment.split("_")
                img_w, img_h = int(w), int(h)
                screen = QApplication.primaryScreen().geometry()
                # Max 80% des Bildschirms, min 400px
                max_w = int(screen.width() * 0.8)
                max_h = int(screen.height() * 0.85)
                win_w = min(img_w + 40, max_w)   # 20px padding je Seite
                win_h = min(img_h + 60, max_h)   # 30px oben+unten
                self.resize(win_w, win_h)
                
                # Fenster nach Resize neu zentrieren
                target_x = (screen.width() - win_w) // 2
                target_y = (screen.height() - win_h) // 2
                self.move(target_x, target_y)
            except Exception:
                pass

    def _install_resize_filter(self):
        proxy = self.browser.focusProxy()
        if proxy:
            proxy.installEventFilter(self._resize_filter)
            proxy.setMouseTracking(True)


    def show_content(self, html_content, parent_pos):
        # Größe auf Standard zurücksetzen
        self.resize(self.DEFAULT_W, self.DEFAULT_H)

        # HTML Template mit Glass-Morphism
        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                html, body {{
                    background: transparent !important;
                    margin: 0;
                    padding: 0;
                    width: 100%;
                    height: 100%;
                    overflow: hidden;
                }}
                .glass-container {{ 
                    background: rgba(10, 10, 10, 0.85); 
                    backdrop-filter: blur(20px); 
                    -webkit-backdrop-filter: blur(20px);
                    color: white; 
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                    border-radius: 20px; 
                    border: 1px solid rgba(255,255,255,0.1);
                    margin: 10px;
                    padding: 20px;
                    height: calc(100% - 62px);
                    overflow-y: auto;
                    box-sizing: border-box;
                }}
                ::-webkit-scrollbar {{
                    width: 10px;
                    height: 10px;
                }}
                ::-webkit-scrollbar-track {{
                    background: transparent;
                }}
                ::-webkit-scrollbar-thumb {{
                    background: rgba(255, 255, 255, 0.2);
                    border-radius: 5px;
                }}
                ::-webkit-scrollbar-thumb:hover {{
                    background: rgba(255, 255, 255, 0.4);
                }}
                h2 {{ margin-top: 0; font-weight: 300; border-bottom: 1px solid rgba(255,255,255,0.2); padding-bottom: 10px; font-size: 18px; }}
                a {{ color: #00bfff; text-decoration: none; }}
            </style>
        </head>
        <body>
            <div class="glass-container">
                <div onclick="window.location.hash='close'" style="position: absolute; top: 15px; right: 25px; font-size: 20px; font-weight: bold; cursor: pointer; color: white; opacity: 0.5; z-index: 1000; font-family: sans-serif;">✕</div>
                {html_content}
            </div>
        </body>
        </html>
        """
        self.is_sticky = "<!-- KEEP_OPEN -->" in html_content
        # Base-URL setzen, damit file:// Bilder geladen werden können
        base_url = QUrl.fromLocalFile(os.path.dirname(os.path.abspath(__file__)) + "/")
        self.browser.setHtml(full_html, base_url)
        
        # Position berechnen: Exakt mittig auf dem Bildschirm
        screen = QApplication.primaryScreen().geometry()
        target_x = (screen.width() - self.DEFAULT_W) // 2
        target_y = (screen.height() - self.DEFAULT_H) // 2
        
        self.move(target_x, target_y)
        self.show()

    def hide_content(self):
        self.hide()

class ChatWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_MacAlwaysShowToolWindow, True)
        self.resize(300, 60)
        
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(10, 10, 10, 10)
        
        self.input_field = QLineEdit(self)
        self.input_field.setPlaceholderText("Flüstere mit Trinity...")
        self.input_field.setStyleSheet("""
            QLineEdit {
                background: rgba(20, 20, 20, 0.9);
                border: 1px solid rgba(0, 191, 255, 0.5);
                border-radius: 15px;
                color: white;
                padding: 10px 15px;
                font-size: 16px;
                font-family: -apple-system, sans-serif;
            }
            QLineEdit:focus {
                border: 1px solid rgba(0, 191, 255, 1.0);
            }
        """)
        self.input_field.returnPressed.connect(self.send_message)
        self.layout.addWidget(self.input_field)

    def show_chat(self, parent_pos):
        self.move(parent_pos.x() - 150, parent_pos.y() + 160)
        self.show()
        self.activateWindow()
        self.input_field.setFocus()

    def send_message(self):
        text = self.input_field.text().strip()
        if text:
            cmd_file = os.path.join(os.path.dirname(__file__), "core", "cmd.txt")
            with open(cmd_file, "w", encoding="utf-8") as f:
                f.write("SILENT:" + text)
        self.input_field.clear()
        self.hide()

class WebEngineDragFilter(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.dragging = False
        self.drag_pos = None

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.LeftButton:
                self.dragging = True
                self.drag_pos = event.globalPosition().toPoint() - self.window.frameGeometry().topLeft()
                self.click_start = event.globalPosition().toPoint()
                return False 
        elif event.type() == QEvent.Type.MouseMove:
            if self.dragging and self.drag_pos is not None:
                self.window.move(event.globalPosition().toPoint() - self.drag_pos)
                return True 
        elif event.type() == QEvent.Type.MouseButtonRelease:
            if self.dragging:
                self.dragging = False
                diff = event.globalPosition().toPoint() - getattr(self, 'click_start', event.globalPosition().toPoint())
                if diff.manhattanLength() < 5:
                    # Es war ein Klick, kein Drag!
                    self.window.chat_window.show_chat(self.window.pos())
            self.drag_pos = None
        return False


class TrinityWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Fenster-Eigenschaften für das "Floating Icon"
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint | 
            Qt.FramelessWindowHint | 
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_MacAlwaysShowToolWindow, True)
        
        # Web-Ansicht für das HTML-Widget
        self.browser = QWebEngineView(self)
        self.setCentralWidget(self.browser)
        
        # Pfad zum UI-Ordner
        ui_path = os.path.join(os.path.dirname(__file__), "ui", "index.html")
        self.browser.load(QUrl.fromLocalFile(ui_path))
        self.browser.page().setBackgroundColor(Qt.transparent)

        # Initiale Größe und Position (unten rechts, passend für den Avatar)
        self.resize(150, 150) 
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - 200, screen.height() - 200)

        # Sekundäres Fenster für Inhalte (ohne parent, damit es auf macOS eigenständig auf Top bleibt)
        self.content_window = ContentWindow(None)
        
        # Chat-Eingabe Fenster (ohne parent)
        self.chat_window = ChatWindow(None)

        # Drag Filter installieren, um die HTML-Ebene zu überlisten
        self.drag_filter = WebEngineDragFilter(self)
        if self.browser.focusProxy():
            self.browser.focusProxy().installEventFilter(self.drag_filter)
        else:
            self.browser.installEventFilter(self.drag_filter)

        # Timer für State-Sync (Python IPC)
        self.state_file = os.path.join(os.path.dirname(__file__), "core", "state.txt")
        self.last_state = "idle"
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_state)
        self.timer.start(100) # alle 100ms prüfen

    def check_state(self):
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, "r") as f:
                    current_state = f.read().strip()
                if current_state and current_state != self.last_state:
                    self.browser.page().runJavaScript(f"window.setTrinityState('{current_state}');")
                    
                    if current_state == "reporting":
                        payload_file = os.path.join(os.path.dirname(__file__), "core", "payload.html")
                        if os.path.exists(payload_file):
                            with open(payload_file, "r", encoding="utf-8") as f:
                                content = f.read()
                            self.content_window.show_content(content, self.pos())
                    elif current_state == "idle":
                        if not getattr(self.content_window, 'is_sticky', False):
                            self.content_window.hide_content()
                    elif current_state == "hide_window":
                        self.content_window.is_sticky = False
                        self.content_window.hide_content()
                        self.browser.page().runJavaScript("window.setTrinityState('idle');")
                        
                    self.last_state = current_state
        except Exception:
            pass

    def mousePressEvent(self, event):
        # Ermöglicht das Verschieben des Widgets
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Icon setzen
    icon_path = os.path.join(os.path.dirname(__file__), "core", "icon.png")
    if os.path.exists(icon_path):
        from PySide6.QtGui import QIcon
        app.setWindowIcon(QIcon(icon_path))
    
    # Trinity starten
    window = TrinityWindow()
    window.show()
    
    sys.exit(app.exec())
