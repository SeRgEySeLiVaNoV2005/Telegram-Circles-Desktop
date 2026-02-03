import sys
import math
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLineEdit, QListWidget,
                             QListWidgetItem, QApplication, QHBoxLayout, QLabel)
from PyQt6.QtCore import Qt, QRect, pyqtSignal, QSize, QTimer, QElapsedTimer, QPoint
from PyQt6.QtGui import QPainter, QColor, QRegion, QPen, QFont


class ChatItemWidget(QWidget):
    def __init__(self, name, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(15)
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
            item = QListWidgetItem(self.list_widget);
            item.setData(Qt.ItemDataRole.UserRole, cid);
            item.setSizeHint(QSize(0, 60))
            self.list_widget.setItemWidget(item, ChatItemWidget(name))

    def filter_chats(self, t):
        self.update_list([d for d in self.all_dialogs if t.lower() in d[1].lower()])

    def on_item_clicked(self, i):
        self.chat_selected.emit(i.data(Qt.ItemDataRole.UserRole));
        self.close()


class CircleUI(QWidget):
    def __init__(self, circle_size=400):
        super().__init__()
        self.circle_size = circle_size
        self.is_recording = False
        self.start_time = QElapsedTimer()
        self.elapsed_ms = 0
        self.ui_timer = QTimer()
        self.ui_timer.timeout.connect(self.refresh_ui)

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.screen_obj = QApplication.primaryScreen()
        self.center = self.screen_obj.geometry().center()
        self.click_offset = QPoint(0, 0)
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

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            # Смещение клика относительно левого верхнего угла окна
            self.click_offset = e.position().toPoint()

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.MouseButton.LeftButton:
            global_pos = e.globalPosition().toPoint()
            current_screen = QApplication.screenAt(global_pos)
            if not current_screen: return

            geo = current_screen.availableGeometry()

            # Реальные размеры окна (с учетом всех факторов Qt)
            win_w = self.width()
            win_h = self.height()

            # Желаемые координаты верхнего левого угла
            target_x = global_pos.x() - self.click_offset.x()
            target_y = global_pos.y() - self.click_offset.y()

            # ЖЕСТКОЕ ОГРАНИЧЕНИЕ ПО ГРАНИЦАМ ЭКРАНА
            final_x = max(geo.left(), min(target_x, geo.left() + geo.width() - win_w))
            final_y = max(geo.top(), min(target_y, geo.top() + geo.height() - win_h))

            # Перемещаем окно только если не идет запись
            if not self.is_recording:
                self.move(final_x, final_y)

            # Всегда обновляем центр для корректного захвата (mss)
            # Центр круга = позиция окна + половина его размера
            self.center = QPoint(
                int(final_x + win_w // 2),
                int(final_y + win_h // 2)
            )
            self.update()

    def paintEvent(self, event):
        p = QPainter(self);
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Центр для рисования — это центр нашего виджета
        local_center = QPoint(self.width() // 2, self.height() // 2)
        c_rect = QRect(local_center.x() - self.circle_size // 2,
                       local_center.y() - self.circle_size // 2,
                       self.circle_size, self.circle_size)

        if self.is_recording:
            # Затемнение всего экрана при записи
            # Нам нужно рисовать на весь экран, когда self.is_recording = True
            p.setClipRegion(QRegion(self.rect()) - QRegion(c_rect, QRegion.RegionType.Ellipse))
            p.fillRect(self.rect(), QColor(0, 0, 0, 160))
            p.setClipping(False)

            p.setPen(QPen(QColor(255, 255, 255, 50), 4));
            p.drawEllipse(c_rect)
            progress = min(self.elapsed_ms / 60000, 1.0)
            span_angle = int(-progress * 360 * 16)
            start_angle = 90 * 16
            color = QColor(255, 215, 0, 200)
            if self.elapsed_ms > 55000: color = QColor(255, 50, 50, 220)
            p.setPen(QPen(color, 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawArc(c_rect, start_angle, span_angle)

            angle_rad = math.radians(90 - (progress * 360))
            dot_x = local_center.x() + (self.circle_size / 2) * math.cos(angle_rad)
            dot_y = local_center.y() - (self.circle_size / 2) * math.sin(angle_rad)
            p.setBrush(QColor(255, 255, 255));
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPoint(int(dot_x), int(dot_y)), 5, 5)

            p.setPen(QColor(255, 255, 255));
            p.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            sec = self.elapsed_ms // 1000
            p.drawText(QRect(local_center.x() - 50, local_center.y() - self.circle_size // 2 - 40, 100, 30),
                       Qt.AlignmentFlag.AlignCenter, f"00:{sec:02d}")
        else:
            p.setPen(QPen(QColor(255, 215, 0, 180), 3))
            p.drawEllipse(c_rect)

    def get_capture_rect(self):
        # mss требует координаты экрана с учетом DPI
        # Поскольку мы включили DPI Awareness, Qt выдает нам логические пиксели,
        # которые совпадают с физическими при правильной настройке.
        dpr = self.screen().devicePixelRatio()
        radius = self.circle_size // 2
        return {
            "left": int((self.center.x() - radius) * dpr),
            "top": int((self.center.y() - radius) * dpr),
            "width": int(self.circle_size * dpr),
            "height": int(self.circle_size * dpr)
        }

    def resize_to_circle(self):
        if not self.is_recording:
            # Окно чуть больше круга для красоты
            self.setFixedSize(self.circle_size + 20, self.circle_size + 20)
        else:
            # При записи окно расширяется на весь экран для оверлея
            geo = self.screen().geometry()
            self.setGeometry(geo)