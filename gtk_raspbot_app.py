import os
import json
import threading
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib, Gio

from raspdbot_bot import RaspDbotEngine

APP_ID = "com.raspdbot.car.chat"
APP_NAME = "RaspDbot-Car Chatbot"

# nơi lưu lịch sử mặc định
DATA_DIR = Path(GLib.get_user_data_dir()) / "raspdbot"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_HISTORY_PATH = DATA_DIR / "history.json"


def scan_models(project_dir: Path) -> list[str]:
    # Scan *.gguf ngay trong thư mục project (không scan sâu)
    return sorted([str(p) for p in project_dir.glob("*.gguf")])


class ChatWindow(Gtk.ApplicationWindow):
    def __init__(self, app: Gtk.Application):
        super().__init__(application=app)
        self.set_title(APP_NAME)
        self.set_default_size(880, 600)

        self.project_dir = Path(__file__).resolve().parent
        self.models = scan_models(self.project_dir)
        if not self.models:
            self.models = ["(Không tìm thấy .gguf trong thư mục project)"]

        self.engine = None
        self.busy = False

        # ===== Root =====
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        root.set_margin_top(12)
        root.set_margin_bottom(12)
        root.set_margin_start(12)
        root.set_margin_end(12)
        self.set_child(root)

        # ===== HeaderBar + Model dropdown + Menu =====
        header = Gtk.HeaderBar()
        self.set_titlebar(header)

        title = Gtk.Label(label=APP_NAME)
        title.set_xalign(0)
        header.set_title_widget(title)

        # Model dropdown
        self.model_list = Gtk.StringList.new(self.models)
        self.model_dd = Gtk.DropDown(model=self.model_list)
        self.model_dd.set_tooltip_text("Chọn model (.gguf)")
        header.pack_start(self.model_dd)

        # Menu button (App menu)
        menu_btn = Gtk.MenuButton()
        menu_btn.set_icon_name("open-menu-symbolic")
        menu_btn.set_tooltip_text("Menu")
        header.pack_end(menu_btn)

        menu_model = Gio.Menu()
        menu_model.append("New chat", "app.new_chat")
        menu_model.append("Load history…", "app.load_history")
        menu_model.append("Save history as…", "app.save_history")
        menu_model.append("Export chat as text…", "app.export_text")
        menu_model.append("Quit", "app.quit")
        menu_btn.set_menu_model(menu_model)

        # ===== Chat area =====
        self.buffer = Gtk.TextBuffer()
        self.textview = Gtk.TextView(buffer=self.buffer)
        self.textview.set_editable(False)
        self.textview.set_cursor_visible(False)
        self.textview.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)

        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        scroller.set_child(self.textview)
        root.append(scroller)

        # ===== Status row =====
        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        root.append(top_row)

        self.status = Gtk.Label(label="Đang tải model…")
        self.status.set_xalign(0)
        self.status.set_hexpand(True)
        top_row.append(self.status)

        self.reset_btn = Gtk.Button(label="New chat")
        self.reset_btn.set_sensitive(False)
        self.reset_btn.connect("clicked", lambda *_: self.on_reset())
        top_row.append(self.reset_btn)

        # ===== Input row =====
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        root.append(row)

        self.entry = Gtk.Entry(placeholder_text="Nhập câu hỏi… (Enter để gửi)")
        self.entry.set_hexpand(True)
        self.entry.set_sensitive(False)
        self.entry.connect("activate", self.on_send)
        row.append(self.entry)

        self.send_btn = Gtk.Button(label="Gửi")
        self.send_btn.set_sensitive(False)
        self.send_btn.connect("clicked", self.on_send)
        row.append(self.send_btn)

        self.append_text("🤖 Tôi: Xin chào! Đợi tôi tải model một chút nhé…\n")

        # ===== Events =====
        self.model_dd.connect("notify::selected", self.on_model_changed)
        self.connect("close-request", self.on_close_request)

        # ===== Init =====
        self.set_busy(True)
        threading.Thread(target=self.load_engine_for_selected_model, daemon=True).start()

    # ---------------- UI helpers ----------------
    def append_text(self, text: str):
        end = self.buffer.get_end_iter()
        self.buffer.insert(end, text)
        mark = self.buffer.create_mark(None, self.buffer.get_end_iter(), False)
        self.textview.scroll_mark_onscreen(mark)

    def set_busy(self, busy: bool):
        self.busy = busy
        can_use = (self.engine is not None) and (not busy)
        self.entry.set_sensitive(can_use)
        self.send_btn.set_sensitive(can_use)
        self.reset_btn.set_sensitive((self.engine is not None) and (not busy))
        self.model_dd.set_sensitive(not busy)

    def rebuild_view_from_history(self):
        self.buffer.set_text("")
        if not self.engine:
            return
        for m in self.engine.history:
            if m["role"] == "user":
                self.append_text(f"\n👤 Bạn: {m['content']}\n")
            else:
                self.append_text(f"🤖 Tôi: {m['content']}\n")

    # ---------------- Model loading ----------------
    def get_selected_model_path(self) -> str:
        idx = self.model_dd.get_selected()
        if idx < 0 or idx >= len(self.models):
            return ""
        return self.models[idx]

    def on_model_changed(self, *_):
        if self.busy:
            return
        threading.Thread(target=self.load_engine_for_selected_model, daemon=True).start()

    def load_engine_for_selected_model(self):
        model_path = self.get_selected_model_path()

        def start():
            self.status.set_text("Đang tải model…")
            self.append_text("\nℹ️ Đang tải model mới…\n")
            self.set_busy(True)
            return False

        GLib.idle_add(start)

        if not model_path or model_path.startswith("("):
            def no_model():
                self.status.set_text("Chưa có model .gguf")
                self.append_text("❌ Không tìm thấy file .gguf trong thư mục project.\n")
                self.engine = None
                self.set_busy(True)
                return False
            GLib.idle_add(no_model)
            return

        try:
            engine = RaspDbotEngine(model_path=model_path, n_ctx=2048)
        except Exception as e:
            def fail():
                self.status.set_text("Lỗi tải model")
                self.append_text(f"❌ Lỗi: {e}\n")
                self.engine = None
                self.set_busy(True)
                return False
            GLib.idle_add(fail)
            return

        # Load default history (nếu có) cho model mới
        if DEFAULT_HISTORY_PATH.exists():
            try:
                data = json.loads(DEFAULT_HISTORY_PATH.read_text(encoding="utf-8"))
                engine.load_json(data)
            except Exception:
                pass

        def ok():
            self.engine = engine
            self.status.set_text("Sẵn sàng ✅")
            self.append_text(f"✅ Model đã tải: {os.path.basename(model_path)}\n")
            self.rebuild_view_from_history()
            self.set_busy(False)
            self.entry.grab_focus()
            return False

        GLib.idle_add(ok)

    # ---------------- History IO ----------------
    def autosave_history(self):
        if not self.engine:
            return
        try:
            DEFAULT_HISTORY_PATH.write_text(
                json.dumps(self.engine.to_json(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def on_close_request(self, *_):
        self.autosave_history()
        return False

    # ---------------- Actions ----------------
    def on_send(self, *_):
        if self.engine is None or self.busy:
            return

        msg = self.entry.get_text().strip()
        if not msg:
            return

        self.entry.set_text("")
        self.append_text(f"\n👤 Bạn: {msg}\n")
        self.status.set_text("Đang trả lời…")
        self.set_busy(True)

        def worker():
            try:
                reply = self.engine.ask(msg)
            except Exception as e:
                reply = f"Lỗi khi chạy bot: {e}"

            def update_ui():
                self.append_text(f"🤖 Tôi: {reply}\n")
                self.status.set_text("Sẵn sàng ✅")
                self.set_busy(False)
                self.entry.grab_focus()
                self.autosave_history()
                return False

            GLib.idle_add(update_ui)

        threading.Thread(target=worker, daemon=True).start()

    def on_reset(self):
        if self.engine is None or self.busy:
            return
        self.engine.reset()
        self.buffer.set_text("")
        self.append_text("🤖 Tôi: Bắt đầu cuộc chat mới ✅\n")
        self.autosave_history()
        self.entry.grab_focus()

    # ---------------- File dialogs (GTK4) ----------------
    def action_load_history(self, *_):
        if self.busy:
            return
        dialog = Gtk.FileDialog(title="Load history", modal=True)
        dialog.open(self, None, self._on_open_done)

    def _on_open_done(self, dialog: Gtk.FileDialog, result):
        try:
            file = dialog.open_finish(result)
            if not file:
                return
            path = file.get_path()
            if not path:
                return
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception as e:
            self.append_text(f"\n❌ Load history lỗi: {e}\n")
            return

        if self.engine is None:
            self.append_text("\n❌ Chưa load model nên không nạp history được.\n")
            return

        try:
            self.engine.load_json(data)
            self.rebuild_view_from_history()
            self.append_text("\n✅ Đã load history.\n")
            self.autosave_history()
        except Exception as e:
            self.append_text(f"\n❌ Nạp history lỗi: {e}\n")

    def action_save_history(self, *_):
        if self.busy or self.engine is None:
            return
        dialog = Gtk.FileDialog(title="Save history as", modal=True)
        dialog.save(self, None, self._on_save_done)

    def _on_save_done(self, dialog: Gtk.FileDialog, result):
        try:
            file = dialog.save_finish(result)
            if not file:
                return
            path = file.get_path()
            if not path:
                return
            Path(path).write_text(
                json.dumps(self.engine.to_json(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self.append_text(f"\n✅ Đã lưu history: {path}\n")
        except Exception as e:
            self.append_text(f"\n❌ Save history lỗi: {e}\n")

    def action_export_text(self, *_):
        if self.busy or self.engine is None:
            return
        dialog = Gtk.FileDialog(title="Export chat as text", modal=True)
        dialog.save(self, None, self._on_export_done)

    def _on_export_done(self, dialog: Gtk.FileDialog, result):
        try:
            file = dialog.save_finish(result)
            if not file:
                return
            path = file.get_path()
            if not path:
                return
            Path(path).write_text(self.engine.export_text(), encoding="utf-8")
            self.append_text(f"\n✅ Đã export text: {path}\n")
        except Exception as e:
            self.append_text(f"\n❌ Export lỗi: {e}\n")


class ChatApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.win = None

    def do_startup(self):
        Gtk.Application.do_startup(self)

        act_new = Gio.SimpleAction.new("new_chat", None)
        act_new.connect("activate", self._new_chat)
        self.add_action(act_new)

        act_load = Gio.SimpleAction.new("load_history", None)
        act_load.connect("activate", self._load_history)
        self.add_action(act_load)

        act_save = Gio.SimpleAction.new("save_history", None)
        act_save.connect("activate", self._save_history)
        self.add_action(act_save)

        act_export = Gio.SimpleAction.new("export_text", None)
        act_export.connect("activate", self._export_text)
        self.add_action(act_export)

        act_quit = Gio.SimpleAction.new("quit", None)
        act_quit.connect("activate", lambda *_: self.quit())
        self.add_action(act_quit)

        self.set_accels_for_action("app.quit", ["<Ctrl>Q"])
        self.set_accels_for_action("app.new_chat", ["<Ctrl>N"])

    def do_activate(self):
        self.win = ChatWindow(self)
        self.win.present()

    def _new_chat(self, *_):
        if self.win:
            self.win.on_reset()

    def _load_history(self, *_):
        if self.win:
            self.win.action_load_history()

    def _save_history(self, *_):
        if self.win:
            self.win.action_save_history()

    def _export_text(self, *_):
        if self.win:
            self.win.action_export_text()


if __name__ == "__main__":
    app = ChatApp()
    raise SystemExit(app.run(None))
