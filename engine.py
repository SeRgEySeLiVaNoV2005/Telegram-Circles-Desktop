import sys, asyncio, threading, mss, cv2, os, keyboard, time, subprocess
import numpy as np
from telethon import TelegramClient
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, pyqtSignal, Qt
from interface import CircleUI, ChatSelector
from dotenv import load_dotenv

# Загрузка конфиденциальных данных из .env
load_dotenv()
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')

# Константы проекта
CIRCLE_SIZE = 400
FPS = 25


class EngineSignals(QObject):
    """Сигналы для связи фоновых потоков с графическим интерфейсом"""
    show_ui = pyqtSignal()
    hide_ui = pyqtSignal()
    set_rec_mode = pyqtSignal(bool)
    show_selector = pyqtSignal()


class TelegramEngine:
    def __init__(self):
        self.client = TelegramClient('my_session', API_ID, API_HASH)
        self.is_recording = False
        self.ui = None
        self.selector = None
        self.ffmpeg_process = None
        self.dialogs_cache = []

        self.signals = EngineSignals()
        self.signals.show_ui.connect(lambda: self.ui.show())
        self.signals.hide_ui.connect(self._safe_hide)
        self.signals.set_rec_mode.connect(lambda m: self.ui.set_recording_mode(m))
        self.signals.show_selector.connect(self.create_chat_selector)

    def _safe_hide(self):
        if self.ui: self.ui.hide()
        if self.selector: self.selector.hide()

    async def start_client(self):
        """Авторизация и получение списка чатов"""
        await self.client.start()
        dialogs = await self.client.get_dialogs(limit=60)
        # Кэшируем только те чаты, куда можно отправить видео
        self.dialogs_cache = [(d.id, d.name) for d in dialogs if
                              d.is_user or d.is_group or (d.is_channel and d.entity.admin_rights)]

        keyboard.add_hotkey('f10', self.handle_f10)
        keyboard.add_hotkey('esc', self.close_all)
        print("Движок готов. Нажмите F10 для появления круга / начала записи.")

    def handle_f10(self):
        if not self.ui.isVisible():
            self.signals.show_ui.emit()
        elif not self.is_recording:
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self):
        self.is_recording = True
        self.signals.set_rec_mode.emit(True)

        # Настройка FFmpeg для приема данных через PIPE
        command = [
            'ffmpeg', '-y',
            '-f', 'rawvideo', '-vcodec', 'rawvideo',
            '-s', f'{CIRCLE_SIZE}x{CIRCLE_SIZE}',
            '-pix_fmt', 'bgr24', '-r', str(FPS),
            '-i', '-',  # Вход из stdin
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-tune', 'zerolatency',
            '-pix_fmt', 'yuv420p',
            '-crf', '28',
            'circle.mp4'
        ]

        # Запускаем FFmpeg в фоне
        self.ffmpeg_process = subprocess.Popen(command, stdin=subprocess.PIPE)

        # Запуск цикла захвата экрана в отдельном потоке
        threading.Thread(target=self.record_loop, daemon=True).start()

    def stop_recording(self):
        self.is_recording = False

    def record_loop(self):
        start_ts = time.time()
        with mss.mss() as sct:
            while self.is_recording:
                t_now = time.time()

                # Лимит Telegram - 60 секунд
                if t_now - start_ts > 60:
                    break

                rect = self.ui.get_capture_rect()
                try:
                    # Захват кадра
                    img = np.array(sct.grab(rect))
                    frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

                    # Ресайз, если координаты окна сместились
                    if frame.shape[0] != CIRCLE_SIZE or frame.shape[1] != CIRCLE_SIZE:
                        frame = cv2.resize(frame, (CIRCLE_SIZE, CIRCLE_SIZE))

                    # Отправка байтов кадра напрямую в FFmpeg
                    self.ffmpeg_process.stdin.write(frame.tobytes())
                except Exception as e:
                    print(f"Запись прервана: {e}")
                    break

                # Поддержание стабильного FPS
                wait = (1 / FPS) - (time.time() - t_now)
                if wait > 0:
                    time.sleep(wait)

        self.finalize_video()

    def finalize_video(self):
        if self.ffmpeg_process:
            try:
                # Закрываем поток данных
                self.ffmpeg_process.stdin.close()
                # Ожидаем, пока FFmpeg полностью завершит работу
                self.ffmpeg_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.ffmpeg_process.kill()  # Если завис — убиваем
            except Exception as e:
                print(f"Ошибка завершения FFmpeg: {e}")

        self.signals.set_rec_mode.emit(False)
        self.signals.show_selector.emit()

    def create_chat_selector(self):
        if self.selector:
            self.selector.close()
        self.selector = ChatSelector(self.dialogs_cache)
        cp = self.ui.screen_geom.center()
        self.selector.move(cp.x() - 175, cp.y() - 250)
        self.selector.chat_selected.connect(self.send_to_tg)
        self.selector.show()

    def send_to_tg(self, cid):
        # Запуск асинхронной отправки через цикл событий
        asyncio.run_coroutine_threadsafe(self.upload(cid), loop)

    async def upload(self, cid):
        # Даем FFmpeg небольшую паузу (0.5 сек), чтобы он точно завершил запись
        await asyncio.sleep(0.5)

        # Проверяем, существует ли файл и не пуст ли он
        if not os.path.exists("circle.mp4") or os.path.getsize("circle.mp4") == 0:
            print("Ошибка: Файл circle.mp4 не найден или пуст.")
            return

        try:
            # Отправка
            await self.client.send_file(cid, "circle.mp4", video_note=True)

            # Удаляем файл только после успешной отправки
            if os.path.exists("circle.mp4"):
                os.remove("circle.mp4")
        except Exception as e:
            print(f"Ошибка при загрузке в Telegram: {e}")
        finally:
            self.signals.hide_ui.emit()

    def close_all(self):
        self.signals.hide_ui.emit()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    engine = TelegramEngine()
    engine.ui = CircleUI(CIRCLE_SIZE)

    # Создаем отдельный цикл событий для Telethon в другом потоке
    loop = asyncio.new_event_loop()


    def start_loop(l):
        asyncio.set_event_loop(l)
        l.run_until_complete(engine.start_client())
        l.run_forever()


    def close_all(self):
        # Отключаем клиента асинхронно, чтобы освободить файл сессии
        asyncio.run_coroutine_threadsafe(self.client.disconnect(), loop)
        self.signals.hide_ui.emit()

    threading.Thread(target=start_loop, args=(loop,), daemon=True).start()

    sys.exit(app.exec())