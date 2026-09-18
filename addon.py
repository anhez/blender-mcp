bl_info = {
    "name": "Blender MCP Server",
    "author": "Blender MCP",
    "version": (1, 2, 0),
    "blender": (4, 2, 0),
    "location": "3D Viewport > Sidebar > MCP",
    "description": "TCP server cho phép MCP client điều khiển Blender",
    "category": "Interface",
}

import bpy
import socket
import threading
import json
import queue
import sys
import io
import os
import math
import traceback

HOST = "127.0.0.1"
PORT = int(os.environ.get("BLENDER_MCP_ADDON_PORT", "9877"))
AUTOSTART = os.environ.get("BLENDER_MCP_AUTOSTART", "0") == "1"


class BlenderMCPServer:
    def __init__(self):
        self.sock = None
        self.running = False
        self.thread = None
        self.cmd_queue = queue.Queue()
        self.client = None
        self.client_lock = threading.Lock()

    def start(self):
        if self.running:
            return
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind((HOST, PORT))
            self.sock.listen(1)
            self.sock.settimeout(1.0)
        except OSError as e:
            print(f"[Blender MCP] Không thể mở cổng {HOST}:{PORT} — {e}")
            self.sock = None
            return
        self.running = True
        self.thread = threading.Thread(target=self._accept_loop, daemon=True)
        self.thread.start()
        print(f"[Blender MCP] Server listening on {HOST}:{PORT}")

    def stop(self):
        self.running = False
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None
        print("[Blender MCP] Server stopped")

    def _accept_loop(self):
        while self.running:
            try:
                client, addr = self.sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            print(f"[Blender MCP] Client connected: {addr}")
            with self.client_lock:
                if self.client is not None:
                    try:
                        client.sendall(
                            (json.dumps({"id": None, "status": "error", "error": "Another client is already connected"}) + "\n").encode("utf-8")
                        )
                    except OSError:
                        pass
                    client.close()
                    continue
                self.client = client
            client.settimeout(0.5)
            buf = b""
            try:
                while self.running:
                    try:
                        chunk = client.recv(65536)
                    except socket.timeout:
                        continue
                    except (ConnectionError, OSError):
                        break
                    if not chunk:
                        break
                    buf += chunk
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        self._dispatch(line.strip(), client)
            finally:
                with self.client_lock:
                    if self.client is client:
                        self.client = None
                try:
                    client.close()
                except OSError:
                    pass
                print("[Blender MCP] Client disconnected")

    def _dispatch(self, line, client):
        if not line:
            return
        try:
            cmd = json.loads(line.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return
        ctype = cmd.get("type")
        cid = cmd.get("id")
        if ctype == "execute_code":
            self.cmd_queue.put((cid, cmd.get("code", ""), client))
        elif ctype == "quit":
            self.stop()
        else:
            try:
                client.sendall(
                    (json.dumps({"id": cid, "status": "error", "error": f"Unknown type: {ctype}"}) + "\n").encode("utf-8")
                )
            except OSError:
                pass

    def pump(self):
        """Xử lý các lệnh đang chờ trên main thread. Gọi từ modal (UI) hoặc script (headless)."""
        while True:
            try:
                cid, code, client = self.cmd_queue.get_nowait()
            except queue.Empty:
                break
            resp = {"id": cid}
            resp.update(self._execute(code))
            try:
                client.sendall((json.dumps(resp) + "\n").encode("utf-8"))
            except OSError:
                pass

    def _execute(self, code):
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        old_stdout, old_stderr = sys.stdout, sys.stderr
        try:
            sys.stdout, sys.stderr = stdout_capture, stderr_capture
            exec(compile(code, "<blender_mcp>", "exec"), {"bpy": bpy, "C": bpy.context, "D": bpy.data, "json": json, "math": math})
            return {
                "status": "success",
                "output": stdout_capture.getvalue(),
                "stderr": stderr_capture.getvalue(),
                "addon_version": ".".join(str(p) for p in bl_info["version"]),
            }
        except Exception:
            return {
                "status": "error",
                "error": traceback.format_exc(),
                "output": stdout_capture.getvalue(),
                "addon_version": ".".join(str(p) for p in bl_info["version"]),
            }
        finally:
            sys.stdout, sys.stderr = old_stdout, old_stderr


_server = BlenderMCPServer()


def get_server():
    return _server


class BLENDERMCP_OT_start(bpy.types.Operator):
    bl_idname = "wm.blender_mcp_start"
    bl_label = "Start MCP Server"
    bl_description = "Bật TCP server để MCP client kết nối"

    _timer = None

    def modal(self, context, event):
        if event.type == "TIMER":
            _server.pump()
        return {"PASS_THROUGH"}

    def execute(self, context):
        _server.start()
        wm = context.window_manager
        if self._timer is None:
            try:
                self._timer = wm.event_timer_add(0.1, persistent=True)
            except TypeError:
                self._timer = wm.event_timer_add(0.1)
            wm.modal_handler_add(self)
        return {"FINISHED"}

    def cancel(self, context):
        if self._timer is not None:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None


class BLENDERMCP_OT_stop(bpy.types.Operator):
    bl_idname = "wm.blender_mcp_stop"
    bl_label = "Stop MCP Server"
    bl_description = "Tắt TCP server"

    def execute(self, context):
        _server.stop()
        return {"FINISHED"}


class BLENDERMCP_PT_panel(bpy.types.Panel):
    bl_label = "Blender MCP"
    bl_idname = "BLENDERMCP_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "MCP"

    def draw(self, context):
        layout = self.layout
        layout.label(text=f"Port: {PORT}")
        layout.label(text="Running" if _server.running else "Stopped")
        if _server.running:
            layout.operator("wm.blender_mcp_stop", icon="PAUSE")
        else:
            layout.operator("wm.blender_mcp_start", icon="PLAY")


def register():
    bpy.utils.register_class(BLENDERMCP_OT_start)
    bpy.utils.register_class(BLENDERMCP_OT_stop)
    bpy.utils.register_class(BLENDERMCP_PT_panel)
    if AUTOSTART:
        try:
            if not bpy.app.background and bpy.context.window_manager.windows:
                bpy.ops.wm.blender_mcp_start()
            else:
                _server.start()
        except Exception:
            _server.start()


def unregister():
    _server.stop()
    bpy.utils.unregister_class(BLENDERMCP_PT_panel)
    bpy.utils.unregister_class(BLENDERMCP_OT_stop)
    bpy.utils.unregister_class(BLENDERMCP_OT_start)
