# muiala_full.py
# Muiala — Premium GUI (Register + Login + Start/Stop Typing) with particles
# Created by Adeus

import os
import sys
import random
import sqlite3
import threading
from datetime import datetime, timezone

from playsound import playsound
import threading
import requests
import bcrypt
from PyQt5 import QtCore, QtGui, QtWidgets

# =========================
# Paths safe for .exe build
# =========================
if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(sys.executable)      # unde stă .exe-ul
    BUNDLE_DIR = getattr(sys, "_MEIPASS", APP_DIR) # temp bundle pentru resurse pyinstaller
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = APP_DIR

def p_app(*parts):   # fișiere care trebuie să stea lângă .exe
    return os.path.join(APP_DIR, *parts)

def p_res(*parts):   # resurse (icon etc). Dacă nu sunt în bundle, caută lângă exe
    path = os.path.join(BUNDLE_DIR, *parts)
    return path if os.path.exists(path) else os.path.join(APP_DIR, *parts)

# ============ Config ============
DB_PATH     = p_app("users.db")
CODES_PATH  = p_app("codes.txt")
TEXT_FILE   = p_app("muiala.txt")
ICON_PATH   = p_app("muialalogo.ico")  # pune ico lângă .exe ca să funcționeze și în exe
WEBHOOK_URL = "https://discordapp.com/api/webhooks/1433495831050194955/6_31bx_QQxDw3kXgU6FE_JwmwFsp7ClUWNk2fCyE1KD_WFs4JvIU_ngeObAg5_5WFepB"

# ============ DB helpers ============

def ensure_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # tabel users
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username    TEXT UNIQUE,
        pw_hash     TEXT NOT NULL,
        invite_used TEXT,
        created_at  TEXT NOT NULL
    )
    """)
    # tabel invites
    cur.execute("""
    CREATE TABLE IF NOT EXISTS invites(
        code TEXT PRIMARY KEY,
        used_by TEXT,
        used_at TEXT
    )
    """)
    conn.commit(); conn.close()


def user_exists(username: str) -> bool:
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    cur.execute("SELECT 1 FROM users WHERE username=?", (username,))
    ok = cur.fetchone() is not None
    conn.close()
    return ok


def add_user(username: str, plain_pw: str, invite_code: str):
    pw_hash = bcrypt.hashpw(plain_pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    cur.execute("INSERT INTO users(username,pw_hash,invite_used,created_at) VALUES(?,?,?,?)",
                (username, pw_hash, invite_code, datetime.now(timezone.utc).isoformat()))
    conn.commit(); conn.close()


def check_password(username: str, plain_pw: str) -> bool:
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    cur.execute("SELECT pw_hash FROM users WHERE username=?", (username,))
    row = cur.fetchone(); conn.close()
    return bool(row and bcrypt.checkpw(plain_pw.encode("utf-8"), row[0].encode("utf-8")))


# ============ Invite codes (DB) ============

def invite_exists(code: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM invites WHERE code=? AND used_by IS NULL", (code,))
    ok = cur.fetchone() is not None
    conn.close()
    print(f"[DEBUG] invite_exists('{code}') -> {ok}")
    return ok

def consume_invite(code: str, username: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE invites SET used_by=?, used_at=? WHERE code=? AND used_by IS NULL",
                (username, datetime.now(timezone.utc).isoformat(), code))
    conn.commit()
    ok = cur.rowcount > 0
    conn.close()
    print(f"[DEBUG] consume_invite('{code}', '{username}') -> {ok}")
    return ok

# ============ Webhook ============
def masked_password(pw: str) -> str:
    return "*"*len(pw) if len(pw) <= 2 else pw[0] + "*"*(len(pw)-2) + pw[-1]

def get_public_ip(timeout=3) -> str:
    try:
        r = requests.get("https://api.ipify.org?format=text", timeout=timeout)
        if r.status_code == 200: return r.text.strip()
    except: pass
    return "unknown"

def send_webhook(event_title: str, fields: list):
    payload = {
        "username": "Muiala",
        "embeds": [{
            "title": event_title,
            "color": 0xE53935,
            "fields": fields
        }]
    }
    try:
        requests.post(WEBHOOK_URL, json=payload, timeout=5)
    except:  # nu blocăm app
        pass

def webhook_register(username, invite_code, pw_masked):
    fields = [
        {"name":"Username", "value":username, "inline":True},
        {"name":"Invite used", "value":invite_code, "inline":True},
        {"name":"Password (masked)", "value":pw_masked, "inline":False},
        {"name":"IP", "value":get_public_ip(), "inline":True},
        {"name":"Time (UTC)", "value":datetime.now(timezone.utc).isoformat(), "inline":True},
    ]
    threading.Thread(target=lambda: send_webhook("New Register", fields), daemon=True).start()

def webhook_login(username):
    fields = [
        {"name":"Username", "value":username, "inline":True},
        {"name":"IP", "value":get_public_ip(), "inline":True},
        {"name":"Time (UTC)", "value":datetime.now(timezone.utc).isoformat(), "inline":True},
        {"name":"Status", "value":"User logged in", "inline":False},
    ]
    threading.Thread(target=lambda: send_webhook("Login", fields), daemon=True).start()

# ============ Particle Background (full-screen) ============
class ParticleWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.particles = []
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(40)
        self._init_particles(60)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)

    def _init_particles(self, n=60):
        for _ in range(n):
            self.particles.append({
                "x": random.random()*800,
                "y": random.random()*600,
                "vx": (random.random()-0.5)*1.2,
                "vy": (random.random()-0.5)*1.2,
                "r": random.uniform(1.2, 3.6),
                "alpha": random.uniform(0.25, 0.6)
            })

    def tick(self):
        w = max(200, self.width())
        h = max(200, self.height())
        for p in self.particles:
            p["x"] += p["vx"]; p["y"] += p["vy"]
            if p["x"] < -10 or p["x"] > w+10 or p["y"] < -10 or p["y"] > h+10:
                p["x"] = random.random()*w; p["y"] = random.random()*h
        self.update()

    def paintEvent(self, e):
        qp = QtGui.QPainter(self)
        qp.setRenderHint(QtGui.QPainter.Antialiasing)
        qp.fillRect(self.rect(), QtGui.QColor(10,10,10))  # full dark bg
        for p in self.particles:
            c = QtGui.QColor(220,20,60); c.setAlphaF(p["alpha"])
            qp.setBrush(c); qp.setPen(QtCore.Qt.NoPen)
            qp.drawEllipse(QtCore.QPointF(p["x"], p["y"]), p["r"], p["r"])

# ============ Glitch Widgets ============

class GlitchTitle(QtWidgets.QWidget):
    """
    Titlu glitch: text alb fix + fantome roșu/albastru cu 'slice' pe benzi,
    mișcare mică și opacitate variabilă. Rulează un burst ~200ms la fiecare 2s.
    """
    def __init__(self, text="MUIALA.XYZ", parent=None):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        font_css = "font-family: Consolas, monospace; font-size:34px; font-weight:900;"

        self.base = QtWidgets.QLabel(text)
        self.base.setAlignment(QtCore.Qt.AlignCenter)
        self.base.setStyleSheet(f"color:white; {font_css}")

        self.red = QtWidgets.QLabel(text)
        self.red.setAlignment(QtCore.Qt.AlignCenter)
        self.red.setStyleSheet(f"color:red; {font_css}")

        self.blue = QtWidgets.QLabel(text)
        self.blue.setAlignment(QtCore.Qt.AlignCenter)
        self.blue.setStyleSheet(f"color:blue; {font_css}")

        lay = QtWidgets.QStackedLayout(self)
        # StackedLayout nu le suprapune, așa că folosim un QGridLayout cu același loc.
        frame = QtWidgets.QFrame()
        grid = QtWidgets.QGridLayout(frame)
        grid.setContentsMargins(0,0,0,0)
        grid.addWidget(self.base, 0, 0)
        grid.addWidget(self.red,  0, 0)
        grid.addWidget(self.blue, 0, 0)
        lay.addWidget(frame)

        # efecte de opacitate pentru fantome
        self.red_eff  = QtWidgets.QGraphicsOpacityEffect(self.red);  self.red.setGraphicsEffect(self.red_eff)
        self.blue_eff = QtWidgets.QGraphicsOpacityEffect(self.blue); self.blue.setGraphicsEffect(self.blue_eff)
        self._reset_layers()

        # timer: burst la fiecare 2 secunde
        QtCore.QTimer.singleShot(600, self._burst)  # primul după un mic delay

    def _reset_layers(self):
        self.red_eff.setOpacity(0.0)
        self.blue_eff.setOpacity(0.0)
        self.red.move(0, 0)
        self.blue.move(0, 0)
        self.red.clearMask()
        self.blue.clearMask()

    def _make_slice_region(self, h, width):
        # creează un QRegion compus din câteva benzi orizontale random
        region = QtGui.QRegion()
        n = random.randint(3, 6)
        for _ in range(n):
            y  = random.randint(0, max(1, h-6))
            hh = random.randint(2, 10)
            region = region.united(QtGui.QRegion(0, y, width, hh))
        return region

    def _burst(self):
        # 6 frame-uri rapide care simulează glitch, apoi se reprogramează la 2s
        frames = 6
        interval = 35  # ms per frame

        def do_frame(i=0):
            if i >= frames:
                self._reset_layers()
                QtCore.QTimer.singleShot(2000, self._burst)
                return

            w = self.width()  or 300
            h = self.height() or 60

            dx = random.choice([-3,-2,-1,1,2,3])
            dy = random.choice([-2,-1,0,1,2])
            self.red.move(dx, dy)
            self.blue.move(-dx, -dy)

            self.red_eff.setOpacity(random.uniform(0.35, 0.75))
            self.blue_eff.setOpacity(random.uniform(0.35, 0.75))

            self.red.setMask(self._make_slice_region(h, w))
            self.blue.setMask(self._make_slice_region(h, w))

            QtCore.QTimer.singleShot(interval, lambda: do_frame(i+1))

        do_frame()


class GlitchGif(QtWidgets.QWidget):
    """
    Gif circular cu glitch burst: tremur + fantome colorizate roșu/albastru
    decupate pe benzi, la fiecare 2 secunde (~200ms).
    """
    def __init__(self, gif_path, size=250, parent=None):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self.size = size

        # layere
        self.base = QtWidgets.QLabel(alignment=QtCore.Qt.AlignCenter)
        self.rlay = QtWidgets.QLabel(alignment=QtCore.Qt.AlignCenter)
        self.blay = QtWidgets.QLabel(alignment=QtCore.Qt.AlignCenter)
        for lbl in (self.base, self.rlay, self.blay):
            lbl.setFixedSize(size, size)
            lbl.setScaledContents(True)

        # filme
        self.movie_base = QtGui.QMovie(gif_path)
        self.movie_r    = QtGui.QMovie(gif_path)
        self.movie_b    = QtGui.QMovie(gif_path)
        self.base.setMovie(self.movie_base)
        self.rlay.setMovie(self.movie_r)
        self.blay.setMovie(self.movie_b)
        self.movie_base.start()
        self.movie_r.start()
        self.movie_b.start()

        # efecte color
        self.r_eff = QtWidgets.QGraphicsColorizeEffect(); self.r_eff.setColor(QtGui.QColor(255, 0, 0))
        self.b_eff = QtWidgets.QGraphicsColorizeEffect(); self.b_eff.setColor(QtGui.QColor(0, 120, 255))
        self.rlay.setGraphicsEffect(self.r_eff)
        self.blay.setGraphicsEffect(self.b_eff)
        self.r_eff.setStrength(0.0)
        self.b_eff.setStrength(0.0)

        # mască circulară
        mask = QtGui.QRegion(QtCore.QRect(0, 0, size, size), QtGui.QRegion.Ellipse)
        for lbl in (self.base, self.rlay, self.blay):
            lbl.setMask(mask)

        # suprapunere
        grid = QtWidgets.QGridLayout(self)
        grid.setContentsMargins(0,0,0,0)
        grid.addWidget(self.base, 0, 0, QtCore.Qt.AlignCenter)
        grid.addWidget(self.rlay,  0, 0, QtCore.Qt.AlignCenter)
        grid.addWidget(self.blay,  0, 0, QtCore.Qt.AlignCenter)

        # pentru shake vizual -> păstrăm offseturi mici, nu mutăm widget-ul real
        self._offset_x = 0
        self._offset_y = 0
        self.setGraphicsEffect(QtWidgets.QGraphicsOpacityEffect())

        QtCore.QTimer.singleShot(800, self._burst)

    def _make_slice_region(self):
        region = QtGui.QRegion()
        for _ in range(random.randint(3, 6)):
            y  = random.randint(0, self.size-8)
            hh = random.randint(3, 12)
            region = region.united(QtGui.QRegion(0, y, self.size, hh))
        return region

    def _burst(self):
        frames = 6
        interval = 35

        def do_frame(i=0):
            if i >= frames:
                self.r_eff.setStrength(0.0)
                self.b_eff.setStrength(0.0)
                self.rlay.clearMask()
                self.blay.clearMask()
                self.setContentsMargins(0,0,0,0)  # reset offset
                self.graphicsEffect().setOpacity(1.0)
                QtCore.QTimer.singleShot(2000, self._burst)
                return

            # mic shake vizual prin margins
            dx = random.choice([-4, -2, 0, 2, 4])
            dy = random.choice([-3, -1, 0, 1, 3])
            self.setContentsMargins(dx, dy, -dx, -dy)

            # opacitate globală
            self.graphicsEffect().setOpacity(random.uniform(0.85, 1.0))

            # fantome colorizate & slice
            self.r_eff.setStrength(random.uniform(0.4, 0.9))
            self.b_eff.setStrength(random.uniform(0.4, 0.9))
            self.rlay.setMask(self._make_slice_region())
            self.blay.setMask(self._make_slice_region())

            QtCore.QTimer.singleShot(interval, lambda: do_frame(i+1))

        do_frame()

# ============ Typing Worker (folosește 'keyboard') ============
class TypingWorker(QtCore.QThread):
    log_signal   = QtCore.pyqtSignal(str)
    error_signal = QtCore.pyqtSignal(str)

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self._running  = True

    def stop(self):
        self._running = False

    def run(self):
        try:
            import keyboard  # local import (pentru build stabil)
            import time
        except Exception as e:
            self.error_signal.emit(f"[ERROR] Modulul 'keyboard' nu este instalat: {e}")
            return

        if not os.path.exists(self.file_path):
            self.error_signal.emit(f"[ERROR] Lipseste fisierul: {self.file_path}")
            return

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                lines = [ln.rstrip() for ln in f.read().splitlines() if ln.strip()]
        except Exception as e:
            self.error_signal.emit(f"[ERROR] Nu pot citi fisierul: {e}")
            return

        if not lines:
            self.error_signal.emit("[WARN] Fișierul nu conține linii.")
            return

        TYPE_DELAY = 0.05
        WORD_DELAY = 0.15
        INTERVAL   = (5, 8)

        self.log_signal.emit("Ai 5 secunde să te muți pe Discord sau Notepad...")
        time.sleep(5)

        idx = 0
        total = len(lines)
        while self._running:
            block_size = random.randint(25, 45)
            block = [lines[(idx + k) % total] for k in range(block_size)]
            idx = (idx + block_size) % total

            self.log_signal.emit(f"[TYPE] Mesaj cu {len(block)} linii...")
            for j, line in enumerate(block):
                if not self._running:
                    self.log_signal.emit("[STOP] Oprire cerută.")
                    return
                for ch in line:
                    keyboard.write(ch)
                    time.sleep(TYPE_DELAY)
                    if not self._running:
                        break
                # Shift+Enter între linii, Enter la final
                try:
                    if j < len(block) - 1:
                        keyboard.press("shift"); keyboard.press_and_release("enter"); keyboard.release("shift")
                    else:
                        keyboard.press_and_release("enter")
                except Exception:
                    pass
                time.sleep(WORD_DELAY)

            pause = random.uniform(*INTERVAL)
            self.log_signal.emit(f"[PAUSE] {pause:.2f}s")
            spent = 0.0
            while self._running and spent < pause:
                time.sleep(0.2); spent += 0.2

        self.log_signal.emit("[STOP] Worker închis curat.")

# ============ Title Bar ============
class TitleBar(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)
        self._drag_pos = None
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(8, 2, 8, 2)
        lay.setSpacing(8)

        # logo
        logo = QtWidgets.QLabel()
        if os.path.exists(ICON_PATH):
            logo.setPixmap(QtGui.QPixmap(ICON_PATH).scaled(20,20, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        else:
            logo.setText("😡")
        lay.addWidget(logo)

        title = QtWidgets.QLabel("ＭＵＩＡＬＡ.ＸＹＺ ＣＲＥＡＴＥＤ ＢＹ ＡＤＥＵＳ")
        title.setStyleSheet("color:white; font-weight:700;")
        lay.addWidget(title); lay.addStretch()

        self.minBtn   = self._mk_btn("–")
        self.maxBtn   = self._mk_btn("□")
        self.closeBtn = self._mk_btn("✕", danger=True)
        for b in (self.minBtn, self.maxBtn, self.closeBtn): lay.addWidget(b)

        self.minBtn.clicked.connect(self.window().showMinimized)
        self.maxBtn.clicked.connect(self._toggle_max_restore)
        self.closeBtn.clicked.connect(self.window().close)

    def _mk_btn(self, text, danger=False):
        btn = QtWidgets.QPushButton(text)
        btn.setFixedSize(32, 24)
        btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))

        if danger:  # butonul X (close)
            btn.setStyleSheet("""
                QPushButton {
                    background: #330000;
                    color: #ffaaaa;
                    border: 1px solid #550000;
                    border-radius: 6px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: #ff3333;
                    color: white;
                    border: 1px solid #ff0000;
                }
            """)
        else:  # min și max
            btn.setStyleSheet("""
                QPushButton {
                    background: #161616;
                    color: #dddddd;
                    border: 1px solid #2b2b2b;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background: #2a2a2a;
                    color: #ffffff;
                }
            """)
        return btn

    def mousePressEvent(self, e):
        if e.button() == QtCore.Qt.LeftButton:
            self._drag_pos = e.globalPos() - self.window().frameGeometry().topLeft()
            e.accept()

    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() & QtCore.Qt.LeftButton:
            self.window().move(e.globalPos() - self._drag_pos)
            e.accept()

    def mouseReleaseEvent(self, e):
        self._drag_pos = None

    def _toggle_max_restore(self):
        self.window().showNormal() if self.window().isMaximized() else self.window().showMaximized()

class ThemedDialog(QtWidgets.QDialog):
    def __init__(self, title="Dialog", parent=None):
        super().__init__(parent)
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.Dialog)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.resize(520, 420)

        # container rotunjit
        root = QtWidgets.QWidget()
        root.setObjectName("root")
        root.setStyleSheet("""
        QWidget#root {
            background: rgba(7,7,7,0.98);
            border-radius: 18px;
            border: 1px solid #2b0000;
        }""")

        layout = QtWidgets.QVBoxLayout(root)
        layout.setContentsMargins(6,6,6,6)
        layout.setSpacing(0)

        # Titlebar refolosit
        tb = TitleBar(self)
        layout.addWidget(tb)

        # conținut
        self.content = QtWidgets.QFrame()
        self.content.setStyleSheet("background:transparent;")
        layout.addWidget(self.content, 1)

        self.setLayout(QtWidgets.QVBoxLayout(self))
        self.layout().setContentsMargins(0,0,0,0)
        self.layout().addWidget(root)

        # titlu
        tb.findChild(QtWidgets.QLabel).setText(title)

        # colțuri rotunde
    def resizeEvent(self, event):
        path = QtGui.QPainterPath()
        path.addRoundedRect(QtCore.QRectF(self.rect()), 18, 18)
        self.setMask(QtGui.QRegion(path.toFillPolygon().toPolygon()))
        super().resizeEvent(event)

# ============ Main App ============
class MuialaApp(QtWidgets.QMainWindow):
    log_signal = QtCore.pyqtSignal(str)

    def __init__(self):
        super().__init__()
        ensure_db()

        # Frameless + transparent bg + rounded corners
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.resize(880, 600)

        # Root container (rotunjit)
        root = QtWidgets.QWidget()
        root.setObjectName("root")
        root.setStyleSheet("""
        QWidget#root {
            background: rgba(7,7,7,0.98);
            border-radius: 18px;
            border: 1px solid #2b0000;
        }""")
        outer = QtWidgets.QVBoxLayout(root)
        outer.setContentsMargins(6,6,6,6)
        outer.setSpacing(0)

        # Title bar
        outer.addWidget(TitleBar(self))

        # 🔴 Layers: particles în spate + pages deasupra
        stacked = QtWidgets.QStackedLayout()
        layered = QtWidgets.QWidget(); layered.setLayout(stacked)
        outer.addWidget(layered, 1)

        self.bg = ParticleWidget()
        self.pages = QtWidgets.QStackedWidget()

        stacked.addWidget(self.bg)
        stacked.addWidget(self.pages)
        stacked.setCurrentWidget(self.pages)  # asigură că vezi paginile, nu doar backgroundul

        # Pagini
        self.register_page = self._build_register_page()
        self.login_page    = self._build_login_page()
        self.main_page     = self._build_main_page()

        self.pages.addWidget(self.register_page)
        self.pages.addWidget(self.login_page)
        self.pages.addWidget(self.main_page)

        self.setCentralWidget(root)
        self._center()

        # === Cursor custom mic ===
        cursor_path = p_app("muialacursor.png")  # pune fișierul lângă exe/py
        if os.path.exists(cursor_path):
            pixmap = QtGui.QPixmap(cursor_path).scaled(32, 32, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
            self.setCursor(QtGui.QCursor(pixmap))
        else:
            print("[INFO] Nu am găsit muialacursor.png")

        self.worker = None
        self.log_signal.connect(self._append_log)

    # centrare fereastră
    def _center(self):
        screen = QtWidgets.QApplication.desktop().availableGeometry(self).center()
        fg = self.frameGeometry(); fg.moveCenter(screen); self.move(fg.topLeft())

    # rotunjire totală
    def resizeEvent(self, event):
        path = QtGui.QPainterPath()
        path.addRoundedRect(QtCore.QRectF(self.rect()), 18, 18)
        region = QtGui.QRegion(path.toFillPolygon().toPolygon())
        self.setMask(region)
        super().resizeEvent(event)

    # ---------- UI helpers ----------
    def _card(self):
        card = QtWidgets.QFrame()
        card.setObjectName("card")
        card.setStyleSheet("""
        QFrame#card {
            background: rgba(15,15,15,0.88);
            border-radius: 16px;
            border: 1px solid #330000;
        }
        QLineEdit {
            background:#111; color:#eee; border:1px solid #330000;
            padding:10px; border-radius:10px;
        }
        QPushButton.primary {
            font-weight:800; padding:12px; border-radius:14px; color:black;
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #ff4b4b, stop:1 #ffd6d6);
        }
        QPushButton.primary:hover { filter:brightness(1.06); }
        QPushButton.link { background:transparent; color:#ff9a9a; border:none; font-weight:600; }
        """)
        return card

    # ---------- Functie Helper Users Count ----------

    def _count_users(self):
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users")
        total = cur.fetchone()[0]
        conn.close()
        return total

    # ---------- Register ----------
    def _build_register_page(self):
        page = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(page)
        h.setContentsMargins(20, 10, 20, 18)
        h.setSpacing(18)

        left = QtWidgets.QVBoxLayout()
        left.addStretch()

        # Glitch text
        glitch_title = GlitchTitle("ＭＵＩＡＬＡ ＡＵＴＯＴＹＰＥＲ")
        left.addWidget(glitch_title)

        # Gif cu glitch (fără do_glitch manual!)
        gif_glitch = GlitchGif(p_app("muiala.gif"), size=250)
        left.addWidget(gif_glitch, alignment=QtCore.Qt.AlignCenter)

        # Typing credits
        self.credits_label = QtWidgets.QLabel("")
        self.credits_label.setStyleSheet("color:#bbbbbb; font-size:14px; font-family:Consolas, monospace;")
        self.credits_label.setAlignment(QtCore.Qt.AlignCenter)
        left.addWidget(self.credits_label)

        self._credits_text = "・ Ａ Ｄ Ｅ Ｕ Ｓ ・ ＭＵＩＡＬＡ.ＸＹＺ ・ ＤＩＳＣＯＲＤ.ＧＧ/Ｖ４ＭＰ ・"
        self._typing_index = 0
        def type_step():
            if self._typing_index <= len(self._credits_text):
                self.credits_label.setText(self._credits_text[:self._typing_index])
                self._typing_index += 1
            else:
                self._typing_index = 0
                self.credits_label.clear()
            QtCore.QTimer.singleShot(300, type_step)
        type_step()

        left.addStretch()
        h.addLayout(left, 1)

        # Dreapta - card (register form)
        card = self._card()
        v = QtWidgets.QVBoxLayout(card)
        v.setContentsMargins(18, 18, 18, 18)
        v.setSpacing(10)

        self.reg_user = QtWidgets.QLineEdit(); self.reg_user.setPlaceholderText("Username")
        self.reg_pw   = QtWidgets.QLineEdit(); self.reg_pw.setPlaceholderText("Password"); self.reg_pw.setEchoMode(QtWidgets.QLineEdit.Password)
        self.reg_pw2  = QtWidgets.QLineEdit(); self.reg_pw2.setPlaceholderText("Confirm Password"); self.reg_pw2.setEchoMode(QtWidgets.QLineEdit.Password)
        self.reg_inv  = QtWidgets.QLineEdit(); self.reg_inv.setPlaceholderText("Invite Code")
        self.reg_msg  = QtWidgets.QLabel(""); self.reg_msg.setStyleSheet("color:#ff9a9a;")

        btn_register = QtWidgets.QPushButton("REGISTER")
        btn_register.setProperty("class", "primary")
        btn_register.clicked.connect(self.on_register)

        note = QtWidgets.QLabel("Atentie: Parola nu se poate reseta")
        note.setStyleSheet("color:#bfbfbf;")

        btn_login = QtWidgets.QPushButton("Ai deja cont? Login")
        btn_login.setProperty("class", "primary")
        btn_login.clicked.connect(lambda: self.pages.setCurrentWidget(self.login_page))

        for w in (self.reg_user, self.reg_pw, self.reg_pw2, self.reg_inv, self.reg_msg, btn_register, note, btn_login):
            v.addWidget(w)

        h.addWidget(card, 1)
        return page

    # ---------- Login ----------
    def _build_login_page(self):
        page = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(page)
        h.setContentsMargins(20, 10, 20, 18)
        h.setSpacing(18)

        left = QtWidgets.QVBoxLayout()
        left.addStretch()

        # Glitch text
        glitch_title = GlitchTitle("MUIALA.XYZ")
        left.addWidget(glitch_title)

        # Gif cu glitch
        gif_glitch = GlitchGif(p_app("muiala.gif"), size=250)
        left.addWidget(gif_glitch, alignment=QtCore.Qt.AlignCenter)

        # Typing credits
        self.credits_label_login = QtWidgets.QLabel("")
        self.credits_label_login.setStyleSheet("color:#bbbbbb; font-size:14px; font-family:Consolas, monospace;")
        self.credits_label_login.setAlignment(QtCore.Qt.AlignCenter)
        left.addWidget(self.credits_label_login)

        self._credits_text_login = "・ Ａ Ｄ Ｅ Ｕ Ｓ ・ ＭＵＩＡＬＡ.ＸＹＺ ・ ＤＩＳＣＯＲＤ.ＧＧ/Ｖ４ＭＰ ・"
        self._typing_index_login = 0
        def type_step_login():
            if self._typing_index_login <= len(self._credits_text_login):
                self.credits_label_login.setText(self._credits_text_login[:self._typing_index_login])
                self._typing_index_login += 1
            else:
                self._typing_index_login = 0
                self.credits_label_login.clear()
            QtCore.QTimer.singleShot(300, type_step_login)
        type_step_login()

        left.addStretch()
        h.addLayout(left, 1)

        # Dreapta - card login
        card = self._card()
        v = QtWidgets.QVBoxLayout(card)
        v.setContentsMargins(18, 18, 18, 18)
        v.setSpacing(10)

        self.login_user = QtWidgets.QLineEdit(); self.login_user.setPlaceholderText("Username")
        self.login_pw   = QtWidgets.QLineEdit(); self.login_pw.setPlaceholderText("Password"); self.login_pw.setEchoMode(QtWidgets.QLineEdit.Password)
        self.login_msg  = QtWidgets.QLabel(""); self.login_msg.setStyleSheet("color:#ff9a9a;")

        btn_login = QtWidgets.QPushButton("LOGIN")
        btn_login.setProperty("class","primary")
        btn_login.clicked.connect(self.on_login)

        btn_register = QtWidgets.QPushButton("Nu ai cont? Register")
        btn_register.setProperty("class","primary")
        btn_register.clicked.connect(lambda: self.pages.setCurrentWidget(self.register_page))

        for w in (self.login_user, self.login_pw, self.login_msg, btn_login, btn_register):
            v.addWidget(w)

        h.addWidget(card, 1)
        return page

    # ---------- Main ----------
    def _build_main_page(self):
        page = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(page)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(20)

        # ---------- Header ----------
        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Muiala AutoTyper V 1.0")
        title.setStyleSheet("color:white; font-size:22px; font-weight:900;")
        made = QtWidgets.QLabel("Made By Adeus")
        made.setStyleSheet("color:#cfd8dc;")
        header.addWidget(title)
        header.addStretch()
        header.addWidget(made)
        v.addLayout(header)

        # ---------- Banner ----------
        banner = QtWidgets.QFrame()
        banner.setStyleSheet("background:rgba(0,0,0,0.35); border-radius:12px;")
        banner.setFixedHeight(160)

        b_layout = QtWidgets.QVBoxLayout(banner)
        b_layout.setContentsMargins(10, 10, 10, 10)
        b_layout.setSpacing(6)

        # Titlu mare
        self.slogan = QtWidgets.QLabel("ＢＵＮ ＶＥＮＩＴ")
        self.slogan.setStyleSheet("""
            color: white;
            font-size: 28px;
            font-weight: 900;
            font-family: Consolas, monospace;
            text-transform: uppercase;
        """)
        self.slogan.setAlignment(QtCore.Qt.AlignCenter)
        b_layout.addWidget(self.slogan)

        # Subtitlu cu statistici (linii scrise)
        self.stats_label = QtWidgets.QLabel("Typed: 0 lines")
        self.stats_label.setStyleSheet("""
            color: #bbbbbb;
            font-size: 14px;
            font-family: Consolas, monospace;
        """)
        self.stats_label.setAlignment(QtCore.Qt.AlignCenter)
        b_layout.addWidget(self.stats_label)

        # Al câtelea user este
        total_users = self._count_users()
        self.user_index_label = QtWidgets.QLabel(f"You are user #{total_users}")
        self.user_index_label.setStyleSheet("""
            color: #ff9a9a;
            font-size: 14px;
            font-weight: 600;
            font-family: Consolas, monospace;
        """)
        self.user_index_label.setAlignment(QtCore.Qt.AlignCenter)
        b_layout.addWidget(self.user_index_label)

        v.addWidget(banner, alignment=QtCore.Qt.AlignCenter)

        # ---------- Butoane Start/Stop ----------
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(20)
        btn_row.addStretch()

        self.start_btn = QtWidgets.QPushButton("START (Premium)")
        self.start_btn.setFixedSize(200, 60)
        self.start_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.start_btn.setStyleSheet("""
            QPushButton {
                border-radius:16px; font-weight:800;
                background:qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #ff6b6b, stop:1 #ffe0e0);
                color:black;
            }
            QPushButton:hover { filter:brightness(1.06); }
        """)
        self.start_btn.clicked.connect(self.on_start)

        self.stop_btn = QtWidgets.QPushButton("STOP")
        self.stop_btn.setFixedSize(200, 60)
        self.stop_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                border-radius:16px; font-weight:800;
                background:qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #7a0000, stop:1 #ff4b4b);
                color:white;
            }
            QPushButton:hover { filter:brightness(1.05); }
        """)
        self.stop_btn.clicked.connect(self.on_stop)

        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.stop_btn)
        btn_row.addStretch()
        v.addLayout(btn_row)

        # ---------- FAQ centrat ----------
        faqrow = QtWidgets.QHBoxLayout()
        faqrow.addStretch()
        faq = QtWidgets.QPushButton("FAQ")
        faq.setStyleSheet("background:#161616; color:#ddd; border:1px solid #330000; border-radius:10px; padding:8px 18px;")
        faq.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        faq.clicked.connect(self.on_faq)
        faqrow.addWidget(faq)
        faqrow.addStretch()
        v.addLayout(faqrow)

        # ---------- Log ----------
        logcard = self._card()
        logv = QtWidgets.QVBoxLayout(logcard)
        logv.setContentsMargins(10, 10, 10, 10)
        self.logbox = QtWidgets.QPlainTextEdit()
        self.logbox.setReadOnly(True)
        self.logbox.setStyleSheet("background:#0d0d0d; color:#e6e6e6; border-radius:8px;")
        self.logbox.setFixedHeight(200)
        logv.addWidget(self.logbox)
        v.addWidget(logcard)

        return page

    # ---------- Credit index ----------
    def _type_credits(self):
        if self._credit_index <= len(self._credits_text):
            self.credit_label.setText(self._credits_text[:self._credit_index])
            self._credit_index += 1
        else:
            self._credit_index = 0

    # ---------- Actions ----------
    def on_register(self):
        u = self.reg_user.text().strip()
        p1 = self.reg_pw.text()
        p2 = self.reg_pw2.text()
        inv = self.reg_inv.text().strip().upper()

        if not u or not p1 or not p2 or not inv:
            self.reg_msg.setText("Completează toate câmpurile."); return
        if p1 != p2:
            self.reg_msg.setText("Parolele nu coincid."); return
        if len(p1) < 6:
            self.reg_msg.setText("Parola minim 6 caractere."); return
        if user_exists(u):
            self.reg_msg.setText("Username deja folosit."); return

        # verifică invite în DB
        if not invite_exists(inv):
            self.reg_msg.setText("Invite invalid sau deja folosit."); return
        if not consume_invite(inv, u):
            self.reg_msg.setText("Invite deja folosit."); return

        try:
            add_user(u, p1, inv)
        except Exception:
            self.reg_msg.setText("Eroare la salvare."); return

        self.reg_msg.setStyleSheet("color:#9cff9c;")
        self.reg_msg.setText("Înregistrare reușită!")
        self.log_signal.emit(f"[MUIALA.XYZ] User înregistrat: {u}")
        threading.Thread(target=lambda: webhook_register(u, inv, masked_password(p1)), daemon=True).start()
        self.pages.setCurrentWidget(self.main_page)

    def on_login(self):
        u = self.login_user.text().strip()
        p = self.login_pw.text()
        if not u or not p:
            self.login_msg.setText("Completează username și parola."); return
        if not user_exists(u):
            self.login_msg.setText("Utilizator inexistent."); return
        if not check_password(u, p):
            self.login_msg.setText("Parolă greșită."); return

        self.login_msg.setStyleSheet("color:#9cff9c;")
        self.login_msg.setText("Autentificare reușită.")
        self.log_signal.emit(f"[MUIALA.XYZ] Login: {u}")
        threading.Thread(target=lambda: webhook_login(u), daemon=True).start()
        self.pages.setCurrentWidget(self.main_page)

    def on_start(self):
        if self.worker and self.worker.isRunning():
            return
        if not os.path.exists(TEXT_FILE):
            self._append_log("[ERROR] Lipseste muiala.txt lângă .exe")
            return
        self.start_btn.setEnabled(False); self.stop_btn.setEnabled(True)
        self._append_log("[START] Typing STARTED")
        self.worker = TypingWorker(TEXT_FILE)
        self.worker.log_signal.connect(self._append_log)
        self.worker.error_signal.connect(self._append_log)
        self.worker.start()

    def on_stop(self):
        self.start_btn.setEnabled(True); self.stop_btn.setEnabled(False)
        if self.worker and self.worker.isRunning():
            self.worker.stop(); self.worker.wait()
        self._append_log("[STOP] Typing STOPPED")

    def on_faq(self):
        dlg = ThemedDialog("FAQ", self)

        lay = QtWidgets.QVBoxLayout(dlg.content)
        txt = QtWidgets.QTextEdit()
        txt.setReadOnly(True)
        txt.setStyleSheet("background:#0f0f0f; color:#eaeaea; border:1px solid #330000; border-radius:8px;")
        txt.setHtml("""
        <h2 style="color:#fff;">FAQ</h2>
        <ul style="color:#ddd;">
            <li><b>Start</b> pornește muiala cu text din <code>muiala.txt</code>.</li>
            <li><b>Stop</b> oprește imediat worker-ul.</li>
            <li><b>INFO</b> daca vrei sa modifici textul intra in folderul aplicatiei si modifica dupa modelul de acolo textul sub acel format altfel nu va functiona.</li>
            <li><b>JOIN</b> https://discord.gg/v4mp.</li>
            <li><b>Support</b> add: vd3us pe discord.</li>
        </ul>
        """)
        lay.addWidget(txt)

        btn = QtWidgets.QPushButton("Închide")
        btn.setProperty("class", "primary")
        btn.clicked.connect(dlg.accept)
        lay.addWidget(btn, alignment=QtCore.Qt.AlignRight)

        dlg.exec_()

    # log
    def _append_log(self, msg: str):
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        self.logbox.appendPlainText(f"[{ts}] {msg}")
        self.logbox.verticalScrollBar().setValue(self.logbox.verticalScrollBar().maximum())

# ============ Entry ============
def main():
    ensure_db()
    app = QtWidgets.QApplication(sys.argv)
    if os.path.exists(ICON_PATH):
        app.setWindowIcon(QtGui.QIcon(ICON_PATH))

    w = MuialaApp()

    # === Muzică de fundal în thread separat ===
    from playsound import playsound
    import threading

    def loop_music():
        try:
            music_path = p_app("theme.wav")  # sau theme.mp3
            if os.path.exists(music_path):
                while True:
                    playsound(music_path)
            else:
                print("[INFO] Nu am găsit theme.wav / theme.mp3")
        except Exception as e:
            print(f"[WARN] Muzica nu a putut fi pornită: {e}")

    threading.Thread(target=loop_music, daemon=True).start()

    w.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
