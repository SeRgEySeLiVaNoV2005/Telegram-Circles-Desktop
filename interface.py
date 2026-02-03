import sys
import math
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLineEdit, QListWidget,
                             QListWidgetItem, QApplication, QHBoxLayout, QLabel)
from PyQt6.QtCore import Qt, QRect, pyqtSignal, QSize, QTimer, QElapsedTimer, QPoint
from PyQt6.QtGui import QPainter, QColor, QRegion, QPen, QFont


class ChatItemWidget(QWidget):
    """Виджет элемента списка чатов (аватар + имя)"""

    def __init__(self, name, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(15)

        # Генерация "аватара" на основе первой буквы имени
        self.avatar = QLabel(name[0].upper() if name else "?")
        self.avatar.setFixedSize(40, 40)
        self.avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        color_hash = abs(hash(name)) % 5
        colors = ["#e17076", "#7bc862", "#65a9e0", "#faa774", "#b694f9"]
        self.avatar.setStyleSheet(
            f"background-color: {colors[color_hash]}; color: white; border-radius: 20px; font-weight: bold; font-size: 16px;")

        self.name_label = QLabel(name)
        self.name_label.setStyleSheet("color: #f5f5f5; font-size: 14px; border: none; background: transparent;")

        layout.addWidget(self.avatar)
        layout.addWidget(self.name_label)
        layout.addStretch()


class ChatSelector(QWidget):
    """Окно выбора чата после записи"""
    chat_selected = pyqtSignal(object)

    def __init__(self, dialogs_data):
        super().__init__()
        self.all_dialogs = dialogs_data
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(350, 500)
        self._old_pos = None
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet("""
            QWidget#MainFrame { background-color: #17212b; border-radius: 15px; border: 1px solid #2b5278; }
            QLineEdit { background-color: #242f3d; border: 1px solid #3b4754; padding: 10px; margin: 10px; border-radius: 10px; color: white; }
            QListWidget { border: none; background: transparent; outline: none; }
            QListWidget::item { background: transparent; border-radius: 10px; margin: 2px 8px; }
            QListWidget::item:hover { background-color: #202b36; }
            QListWidget::item:selected { background-color: #2b5278; }
        """)
        l = QVBoxLayout(self);
        l.setContentsMargins(0, 0, 0, 0)
        self.frame = QWidget();
        self.frame.setObjectName("MainFrame")
        fl = QVBoxLayout(self.frame)

        self.title = QLabel("Выберите чат");
        self.title.setStyleSheet("color: #538bb4; font-weight: bold; margin: 10px; border:none;")
        self.search_bar = QLineEdit();
        self.search_bar.setPlaceholderText("Поиск...")
        self.search_bar.textChanged.connect(self.filter_chats)

        self.list_widget = QListWidget();
        self.list_widget.itemClicked.connect(self.on_item_clicked)

        fl.addWidget(self.title);
        fl.addWidget(self.search_bar);
        fl.addWidget(self.list_widget)
        l.addWidget(self.frame)
        self.update_list(self.all_dialogs)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton: self._old_pos = e.globalPosition().toPoint()

    def mouseMoveEvent(self, e):
        if self._old_pos:
            delta = e.globalPosition().toPoint() - self._old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self._old_pos = e.globalPosition().toPoint()

    def mouseReleaseEvent(self, e):
        self._old_pos = None

    def update_list(self, data):
        self.list_widget.clear()
        for cid, name in data:
            item = QListWidgetItem(self.list_widget)
            item.setData(Qt.ItemDataRole.UserRole, cid)
            item.setSizeHint(QSize(0, 60))
            self.list_widget.setItemWidget(item, ChatItemWidget(name))

    def filter_chats(self, t):
        self.update_list([d for d in self.all_dialogs if t.lower() in d[1].lower()])

    def on_item_clicked(self, i):
        self.chat_selected.emit(i.data(Qt.ItemDataRole.UserRole))
        self.close()


class CircleUI(QWidget):
    """Основной интерфейс круга с HUD и прогресс-баром"""

    def __init__(self, circle_size=400):
        super().__init__()
        self.circle_size = circle_size
        self.is_recording = False
        self.start_time = QElapsedTimer()
        self.elapsed_ms = 0

        # Таймер для плавного обновления анимации (30 FPS)
        self.ui_timer = QTimer()
        self.ui_timer.timeout.connect(self.refresh_ui)

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.screen_obj = QApplication.primaryScreen()
        self.dpr = self.screen_obj.devicePixelRatio()
        self.screen_geom = self.screen_obj.geometry()
        self.center = self.screen_geom.center()
        self.resize_to_circle()

    def refresh_ui(self):
        if self.is_recording:
            self.elapsed_ms = self.start_time.elapsed()
            self.update()

    def set_recording_mode(self, state):
        self.is_recording = state
        if state:
            self.elapsed_ms = 0
            self.start_time.start()
            self.ui_timer.start(33)
        else:
            self.ui_timer.stop()
        self.resize_to_circle()
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        c_rect = QRect(self.center.x() - self.circle_size // 2,
                       self.center.y() - self.circle_size // 2,
                       self.circle_size, self.circle_size)

        if self.is_recording:
            # 1. Затемнение экрана вне круга
            p.setClipRegion(QRegion(self.rect()) - QRegion(c_rect, QRegion.RegionType.Ellipse))
            p.fillRect(self.rect(), QColor(0, 0, 0, 160))
            p.setClipping(False)

            # 2. Фоновое кольцо (под прогрессом)
            p.setPen(QPen(QColor(255, 255, 255, 50), 4))
            p.drawEllipse(c_rect)

            # 3. Отрисовка прогресса (60 секунд)
            progress = min(self.elapsed_ms / 60000, 1.0)
            span_angle = int(-progress * 360 * 16)
            start_angle = 90 * 16  # Начинаем сверху (12 часов)

            # Цвет меняется на красный за 5 секунд до конца
            color = QColor(255, 215, 0, 200)  # Золотой
            if self.elapsed_ms > 55000:
                color = QColor(255, 50, 50, 220)  # Красный

            p.setPen(QPen(color, 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawArc(c_rect, start_angle, span_angle)

            # 4. Белая точка на конце линии прогресса
            angle_rad = math.radians(90 - (progress * 360))
            dot_x = self.center.x() + (self.circle_size / 2) * math.cos(angle_rad)
            dot_y = self.center.y() - (self.circle_size / 2) * math.sin(angle_rad)

            p.setBrush(QColor(255, 255, 255))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPoint(int(dot_x), int(dot_y)), 5, 5)

            # 5. Цифровой таймер
            p.setPen(QColor(255, 255, 255))
            p.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            sec = self.elapsed_ms // 1000
            p.drawText(QRect(self.center.x() - 50, self.center.y() - self.circle_size // 2 - 40, 100, 30),
                       Qt.AlignmentFlag.AlignCenter, f"00:{sec:02d}")
        else:
            # Режим перемещения (просто рамка)
            p.setPen(QPen(QColor(255, 215, 0, 180), 3))
            p.drawEllipse(QRect(10, 10, self.circle_size, self.circle_size))

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton: self.drag_pos = e.globalPosition().toPoint()

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.MouseButton.LeftButton:
            delta = e.globalPosition().toPoint() - self.drag_pos
            self.center += delta
            self.drag_pos = e.globalPosition().toPoint()
            if not self.is_recording: self.move(self.x() + delta.x(), self.y() + delta.y())
            self.update()

    def get_capture_rect(self):
        left = self.center.x() - self.circle_size // 2
        top = self.center.y() - self.circle_size // 2
        return {
            "top": int(top * self.dpr),
            "left": int(left * self.dpr),
            "width": int(self.circle_size * self.dpr),
            "height": int(self.circle_size * self.dpr)
        }

    def resize_to_circle(self):
        if not self.is_recording:
            self.setGeometry(self.center.x() - self.circle_size // 2 - 10,
                             self.center.y() - self.circle_size // 2 - 10,
                             self.circle_size + 20, self.circle_size + 20)
        else:
            self.setGeometry(self.screen_geom)