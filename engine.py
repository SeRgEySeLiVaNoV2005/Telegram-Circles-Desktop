import sys, asyncio, threading, mss, cv2, os, keyboard, time
import numpy as np
import subprocess
from telethon import TelegramClient
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, pyqtSignal, Qt
from interface import CircleUI, ChatSelector

from dotenv import load_dotenv
load_dotenv()

API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
# ------------------------------------

CIRCLE_SIZE = 400
FPS = 25


class EngineSignals(QObject):
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
        self.signals = EngineSignals()

        self.signals.show_ui.connect(lambda: self.ui.show())
        self.signals.hide_ui.connect(self._safe_hide)
        self.signals.set_rec_mode.connect(lambda m: self.ui.set_recording_mode(m))
        self.signals.show_selector.connect(self.create_chat_selector)

    def _safe_hide(self):
        if self.ui: self.ui.hide()
        if self.selector: self.selector.hide()

    async def start_client(self):
        await self.client.start()
        dialogs = await self.client.get_dialogs(limit=60)
        self.dialogs_cache = [(d.id, d.name) for d in dialogs if
                              d.is_user or d.is_group or (d.is_channel and d.entity.admin_rights)]
        keyboard.add_hotkey('f10', self.handle_f10)
        keyboard.add_hotkey('esc', self.close_all)
        print("Telegram готов. F10 - запись.")

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
        threading.Thread(target=self.record_loop, daemon=True).start()

    def stop_recording(self):
        self.is_recording = False

    def record_loop(self):
        frames = []
        with mss.mss() as sct:
            while self.is_recording:
                t_start = time.time()
                rect = self.ui.get_capture_rect()  # Получаем точные DPI-координаты

                try:
                    img = np.array(sct.grab(rect))
                    frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                    # Принудительный ресайз для компенсации масштаба Windows
                    if frame.shape[0] != CIRCLE_SIZE or frame.shape[1] != CIRCLE_SIZE:
                        frame = cv2.resize(frame, (CIRCLE_SIZE, CIRCLE_SIZE))
                    frames.append(frame)
                except:
                    pass

                wait = (1 / FPS) - (time.time() - t_start)
                if wait > 0: time.sleep(wait)

        self.signals.set_rec_mode.emit(False)
        self.process_video(frames)

    def process_video(self, frames):
        if not frames: return
        t, f = "temp.avi", "circle.mp4"
        out = cv2.VideoWriter(t, cv2.VideoWriter_fourcc(*'XVID'), FPS, (CIRCLE_SIZE, CIRCLE_SIZE))
        for fr in frames: out.write(fr)
        out.release()

        subprocess.run(
            ['ffmpeg', '-y', '-i', t, '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-preset', 'ultrafast', '-crf', '26',
             f],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        if os.path.exists(t): os.remove(t)
        time.sleep(0.3)
        self.signals.show_selector.emit()

    def create_chat_selector(self):
        if self.selector: self.selector.close()
        self.selector = ChatSelector(self.dialogs_cache)
        cp = self.ui.screen_geom.center()
        self.selector.move(cp.x() - 175, cp.y() - 250)
        self.selector.chat_selected.connect(self.send_to_tg)
        self.selector.show()

    def send_to_tg(self, cid):
        asyncio.run_coroutine_threadsafe(self.upload(cid), loop)

    async def upload(self, cid):
        try:
            await self.client.send_file(cid, "circle.mp4", video_note=True)
            if os.path.exists("circle.mp4"): os.remove("circle.mp4")
        except Exception as e:
            print(f"Error: {e}")
        finally:
            self.signals.hide_ui.emit()

    def close_all(self):
        self.signals.hide_ui.emit()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    engine = TelegramEngine();
    engine.ui = CircleUI(CIRCLE_SIZE)
    loop = asyncio.new_event_loop()


    def r_a():
        asyncio.set_event_loop(loop);
        loop.run_until_complete(engine.start_client());
        loop.run_forever()


    threading.Thread(target=r_a, daemon=True).start()
    sys.exit(app.exec())