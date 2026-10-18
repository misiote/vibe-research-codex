#!/usr/bin/env python3
"""Linux GTK/WebKitGTK companion for Vibe Research."""
import argparse
import fcntl
import json
import math
import os
import signal
import time
import webbrowser
from pathlib import Path

try:
    import cairo
    import gi
    gi.require_version("Gtk", "3.0")
    try:
        gi.require_version("WebKit2", "4.1")
    except ValueError:
        gi.require_version("WebKit2", "4.0")
    from gi.repository import Gdk, GLib, Gtk, WebKit2
except (ImportError, ValueError) as exc:
    raise SystemExit(
        "缺少 Linux 研究伴侣依赖。Debian/Ubuntu 安装："
        "sudo apt install python3-cairo python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.1\n" + str(exc)
    )


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--url")
    parser.add_argument("--title", default="Vibe Research · 研究现场")
    parser.add_argument("--ui-state")
    parser.add_argument("--pid-file")
    return parser.parse_args()


class Companion:
    BUTTON_SIZE = 62

    def __init__(self, url, title, ui_state, pid_file):
        self.url = url
        self.title = title
        self.ui_state = Path(ui_state) if ui_state else None
        self.pid_file = Path(pid_file) if pid_file else None
        self.instance_lock = self.acquire_instance_lock()
        self.initial_state = self.saved_state()
        self.expanded = False
        self.loaded = False
        self.pointer_start = None
        self.window_start = None
        self.dragged = False
        settings = Gtk.Settings.get_default()
        self.motion_enabled = bool(settings.get_property("gtk-enable-animations")) if settings else True
        self.motion_phase = 0.0
        self.status_color = (0.12, 0.88, 0.59)
        self.entrance_frame = 0
        self.entrance_target = None
        badge_path = Path(__file__).resolve().parents[1] / "assets" / "host-badge.png"
        self.host_badge = cairo.ImageSurface.create_from_png(str(badge_path)) if badge_path.is_file() else None

        self.button_window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        self.button_window.set_name("vr-button-window")
        self.button_window.set_decorated(False)
        self.button_window.set_keep_above(True)
        self.button_window.set_skip_taskbar_hint(True)
        self.button_window.set_skip_pager_hint(True)
        self.button_window.set_resizable(False)
        self.button_window.set_default_size(self.BUTTON_SIZE, self.BUTTON_SIZE)
        self.button_window.set_size_request(self.BUTTON_SIZE, self.BUTTON_SIZE)
        self.button_window.set_title("Vibe Research Companion")
        self.button_window.set_app_paintable(True)
        visual = self.button_window.get_screen().get_rgba_visual()
        if visual:
            self.button_window.set_visual(visual)
        self.button_window.connect("destroy", self.quit)
        self.button_window.connect("configure-event", self.button_configured)

        self.button = Gtk.EventBox()
        self.button.set_name("vr-companion-button")
        self.button.set_visible_window(False)
        self.button.set_tooltip_text("Vibe Research · 点击打开，拖拽移动")
        self.button.set_size_request(52, 52)
        self.button.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
        )
        self.button.connect("button-press-event", self.button_press)
        self.button.connect("motion-notify-event", self.button_motion)
        self.button.connect("button-release-event", self.button_release)
        self.button_canvas = Gtk.DrawingArea()
        self.button_canvas.set_size_request(52, 52)
        self.button_canvas.connect("draw", self.draw_button)
        self.button.add(self.button_canvas)
        button_box = Gtk.Box()
        button_box.set_margin_start(5)
        button_box.set_margin_end(5)
        button_box.set_margin_top(5)
        button_box.set_margin_bottom(5)
        button_box.pack_start(self.button, True, True, 0)
        self.button_window.add(button_box)

        self.workbench_window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        self.workbench_window.set_decorated(False)
        self.workbench_window.set_keep_above(True)
        self.workbench_window.set_skip_taskbar_hint(True)
        self.workbench_window.set_skip_pager_hint(True)
        self.workbench_window.set_resizable(False)
        self.workbench_window.set_title(title)
        self.workbench_window.connect("delete-event", self.workbench_close)
        self.workbench_window.connect("configure-event", self.workbench_configured)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        root.set_name("vr-workbench")
        self.workbench_window.add(root)
        header = Gtk.EventBox()
        header.set_name("vr-header")
        header.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        header.connect("button-press-event", self.drag_workbench)
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        header_box.set_border_width(14)
        header.add(header_box)
        title_label = Gtk.Label(label=title, xalign=0)
        title_label.set_name("vr-title")
        header_box.pack_start(title_label, True, True, 6)
        collapse = Gtk.Button(label="收起")
        collapse.set_name("vr-collapse")
        collapse.connect("clicked", lambda _button: self.collapse())
        header_box.pack_end(collapse, False, False, 0)
        root.pack_start(header, False, False, 0)

        web_host = Gtk.Box()
        web_host.set_border_width(10)
        self.web = WebKit2.WebView()
        self.web.connect("create", self.open_new_window)
        self.web.connect("load-changed", self.web_load_changed)
        self.web.connect("load-failed", self.web_load_failed)
        web_host.pack_start(self.web, True, True, 0)
        root.pack_start(web_host, True, True, 0)

        style = Gtk.CssProvider()
        style.load_from_data(b"""
            #vr-button-window { background-color: transparent; }
            #vr-companion-button { background-color: transparent; }
            #vr-workbench { background: #eff4fc; }
            #vr-header { background: #1a2438; }
            #vr-title { color: #f4f7fb; font-size: 15px; font-weight: 600; }
            #vr-collapse { color: white; background: #2f4463; border-radius: 8px; }
        """)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), style, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        self.menu = Gtk.Menu()
        open_item = Gtk.MenuItem(label="打开研究现场")
        open_item.connect("activate", lambda _item: self.expand())
        self.menu.append(open_item)
        quit_item = Gtk.MenuItem(label="退出研究伴侣")
        quit_item.connect("activate", lambda _item: self.quit())
        self.menu.append(quit_item)
        self.menu.show_all()

        self.button_window.show_all()
        GLib.idle_add(self.place_button)
        if self.motion_enabled:
            GLib.timeout_add(50, self.animate_presence)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR1, self.signal_toggle)
        if self.pid_file:
            self.pid_file.parent.mkdir(parents=True, exist_ok=True)
            self.pid_file.write_text(str(os.getpid()) + "\n", encoding="utf-8")

    def saved_state(self):
        if not self.ui_state:
            return {}
        try:
            return json.loads(self.ui_state.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def open_new_window(self, _webview, navigation_action):
        try:
            uri = navigation_action.get_request().get_uri()
            if uri and uri.startswith(("http://", "https://")):
                webbrowser.open(uri)
        except Exception:
            pass
        return None

    def animate_presence(self):
        self.motion_phase = (self.motion_phase + 0.08) % (math.pi * 2)
        self.button_canvas.queue_draw()
        return GLib.SOURCE_CONTINUE

    def draw_button(self, _widget, ctx):
        ctx.set_operator(cairo.OPERATOR_CLEAR)
        ctx.paint()
        ctx.set_operator(cairo.OPERATOR_OVER)
        cx = cy = 26.0
        red, green, blue = self.status_color
        for index in range(24):
            distance = (index / 24.0 - self.motion_phase / (math.pi * 2)) % 1.0
            alpha = 0.18 + 0.82 * (1 - distance) ** 3
            start = index * math.pi * 2 / 24 - math.pi / 2
            ctx.set_source_rgba(red, green, blue, alpha)
            ctx.set_line_width(3.2)
            ctx.arc(cx, cy, 23.8, start, start + math.pi * 2 / 21)
            ctx.stroke()

        gradient = cairo.LinearGradient(10, 42, 42, 10)
        gradient.add_color_stop_rgb(0, 0.27, 0.31, 0.86)
        gradient.add_color_stop_rgb(1, 0.04, 0.63, 0.71)
        ctx.set_source(gradient)
        ctx.arc(cx, cy, 20.5, 0, math.pi * 2)
        ctx.fill_preserve()
        ctx.set_source_rgba(1, 1, 1, 0.42)
        ctx.set_line_width(1.1)
        ctx.stroke()

        points = ((26.0, 38.0), (14.0, 17.0), (39.0, 20.0))
        ctx.set_source_rgba(1, 1, 1, 0.88)
        ctx.set_line_width(2.1)
        ctx.move_to(*points[0])
        ctx.line_to(*points[1])
        ctx.line_to(*points[2])
        ctx.close_path()
        ctx.stroke()
        for index, (x, y) in enumerate(points):
            pulse = max(0.0, math.sin(self.motion_phase * 1.45 - index * 1.25))
            ctx.set_source_rgba(0.54, 0.93, 1, pulse * 0.55)
            ctx.arc(x, y, 6 + pulse * 4, 0, math.pi * 2)
            ctx.fill()
            ctx.set_source_rgb(1, 1, 1)
            ctx.arc(x, y, 3.6, 0, math.pi * 2)
            ctx.fill()

        if self.host_badge is not None:
            ctx.set_source_rgba(0, 0, 0, 0.32)
            ctx.arc(43.0, 44.0, 10.0, 0, math.pi * 2)
            ctx.fill()
            ctx.set_source_rgba(0.98, 0.99, 1.0, 0.98)
            ctx.arc(43.0, 43.0, 10.0, 0, math.pi * 2)
            ctx.fill()
            ctx.save()
            ctx.arc(43.0, 43.0, 7.8, 0, math.pi * 2)
            ctx.clip()
            ctx.translate(35.2, 35.2)
            ctx.scale(15.6 / self.host_badge.get_width(), 15.6 / self.host_badge.get_height())
            ctx.set_source_surface(self.host_badge, 0, 0)
            ctx.paint()
            ctx.restore()
            ctx.set_source_rgba(1, 1, 1, 0.72)
            ctx.set_line_width(0.8)
            ctx.arc(43.0, 43.0, 9.6, 0, math.pi * 2)
            ctx.stroke()
        return False

    def set_status(self, color):
        self.status_color = color
        self.button_canvas.queue_draw()

    def web_load_changed(self, _webview, event):
        if event == WebKit2.LoadEvent.STARTED:
            self.set_status((1.0, 0.67, 0.17))
        elif event == WebKit2.LoadEvent.FINISHED:
            self.set_status((0.12, 0.88, 0.59))

    def web_load_failed(self, *_args):
        self.set_status((0.96, 0.29, 0.34))
        return False

    def animate_entrance(self):
        if not self.entrance_target:
            return GLib.SOURCE_REMOVE
        self.entrance_frame += 1
        progress = min(1.0, self.entrance_frame / 28.0)
        eased = 1 - (1 - progress) ** 3
        x, y = self.entrance_target
        self.button_window.set_opacity(eased)
        self.button_window.move(x, int(y + (1 - eased) * 12))
        if progress < 1:
            return GLib.SOURCE_CONTINUE
        self.button_window.set_opacity(1)
        self.button_window.move(x, y)
        self.entrance_target = None
        return GLib.SOURCE_REMOVE

    def place_with_entrance(self, x, y):
        if not self.motion_enabled:
            self.button_window.move(x, y)
            return
        self.entrance_target = (x, y)
        self.entrance_frame = 0
        self.button_window.set_opacity(0)
        self.button_window.move(x, y + 12)
        GLib.timeout_add(16, self.animate_entrance)

    def monitor_area(self, window=None):
        screen = Gdk.Screen.get_default()
        gdk_window = (window or self.button_window).get_window()
        monitor = screen.get_monitor_at_window(gdk_window) if gdk_window else screen.get_primary_monitor()
        return screen.get_monitor_workarea(max(0, monitor))

    def place_button(self):
        area = self.monitor_area()
        saved = self.initial_state
        x = saved.get("button_x")
        y = saved.get("button_y")
        if isinstance(x, (int, float)) and isinstance(y, (int, float)):
            center = (int(x) + self.BUTTON_SIZE // 2, int(y) + self.BUTTON_SIZE // 2)
            screen = Gdk.Screen.get_default()
            for monitor in range(screen.get_n_monitors()):
                monitor_area = screen.get_monitor_workarea(monitor)
                if (
                    monitor_area.x <= center[0] < monitor_area.x + monitor_area.width
                    and monitor_area.y <= center[1] < monitor_area.y + monitor_area.height
                ):
                    self.place_with_entrance(int(x), int(y))
                    GLib.idle_add(self.persist)
                    return False
        self.place_with_entrance(area.x + area.width - self.BUTTON_SIZE - 18, area.y + 18)
        GLib.idle_add(self.persist)
        return False

    def button_press(self, _widget, event):
        if event.button == 3:
            self.menu.popup_at_pointer(event)
            return True
        if event.button != 1:
            return False
        self.pointer_start = (event.x_root, event.y_root)
        self.window_start = self.button_window.get_position()
        self.dragged = False
        return True

    def button_motion(self, _widget, event):
        if not self.pointer_start or not self.window_start:
            return False
        dx = event.x_root - self.pointer_start[0]
        dy = event.y_root - self.pointer_start[1]
        if math.hypot(dx, dy) > 3:
            self.dragged = True
        if self.dragged:
            target_x = int(self.window_start[0] + dx)
            target_y = int(self.window_start[1] + dy)
            screen = Gdk.Screen.get_default()
            monitor = screen.get_monitor_at_point(
                target_x + self.BUTTON_SIZE // 2,
                target_y + self.BUTTON_SIZE // 2,
            )
            area = screen.get_monitor_workarea(max(0, monitor))
            target_x = min(max(target_x, area.x), area.x + area.width - self.BUTTON_SIZE)
            target_y = min(max(target_y, area.y), area.y + area.height - self.BUTTON_SIZE)
            self.button_window.move(target_x, target_y)
        return True

    def button_release(self, _widget, event):
        if event.button != 1 or not self.pointer_start:
            return False
        was_dragged = self.dragged
        self.pointer_start = None
        self.window_start = None
        self.dragged = False
        if was_dragged:
            self.persist()
        else:
            self.toggle()
        return True

    def workbench_size(self):
        area = self.monitor_area()
        return area, min(1120, max(760, area.width - 120)), min(780, max(560, area.height - 100))

    def collapse(self):
        self.expanded = False
        self.workbench_window.hide()
        self.button.set_tooltip_text("Vibe Research · 点击打开，拖拽移动")
        self.button_window.present()
        self.persist()

    def acquire_instance_lock(self):
        if not self.pid_file:
            return None
        lock_path = Path(str(self.pid_file) + ".lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = lock_path.open("a+")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            handle.close()
            raise SystemExit(0)
        return handle

    def expand(self):
        if self.expanded:
            return
        self.expanded = True
        area, width, height = self.workbench_size()
        self.workbench_window.set_size_request(width, height)
        self.workbench_window.resize(width, height)
        self.workbench_window.move(area.x + (area.width - width) // 2, area.y + (area.height - height) // 2)
        self.workbench_window.show_all()
        if not self.loaded:
            self.web.load_uri(self.url)
            self.loaded = True
        self.button.set_tooltip_text("Vibe Research · 点击收起，拖拽移动")
        self.workbench_window.present()
        self.button_window.present()
        self.persist(width, height)

    def toggle(self):
        self.collapse() if self.expanded else self.expand()

    def signal_toggle(self):
        self.toggle()
        return GLib.SOURCE_CONTINUE

    def drag_workbench(self, _widget, event):
        if event.button == 1:
            self.workbench_window.begin_move_drag(event.button, int(event.x_root), int(event.y_root), event.time)
            return True
        return False

    def workbench_close(self, *_args):
        self.collapse()
        return True

    def button_configured(self, *_args):
        if not self.pointer_start:
            self.persist()
        return False

    def workbench_configured(self, *_args):
        if self.expanded:
            self.persist()
        return False

    def persist(self, width=None, height=None):
        if not self.ui_state or not self.button_window.get_window():
            return
        button_x, button_y = self.button_window.get_position()
        if width is None or height is None:
            _area, width, height = self.workbench_size()
        payload = {
            "expanded": self.expanded,
            "separate_windows": True,
            "button_x": button_x,
            "button_y": button_y,
            "button_width": self.BUTTON_SIZE,
            "button_height": self.BUTTON_SIZE,
            "panel_width": width,
            "panel_height": height,
            "content_width": width,
            "web_x": 10,
            "web_width": max(1, width - 20),
            "web_height": max(1, height - 82),
            "web_right_gap": 10,
            "updated_at": int(time.time()),
        }
        self.ui_state.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.ui_state.with_suffix(self.ui_state.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.ui_state)

    def quit(self, *_args):
        if self.pid_file:
            try:
                self.pid_file.unlink()
            except FileNotFoundError:
                pass
        if self.workbench_window:
            self.workbench_window.destroy()
        Gtk.main_quit()


def main():
    args = arguments()
    if args.check:
        print(json.dumps({"ok": True, "gtk": 3, "webkit": "4.x"}))
        return 0
    if not args.url:
        raise SystemExit("missing --url")
    Companion(args.url, args.title, args.ui_state, args.pid_file)
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
