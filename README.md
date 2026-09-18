# Blender MCP (maket-blender)

MCP server điều khiển Blender qua TCP socket. Gồm 2 phần:

- **`addon.py`** — Addon Blender: chạy TCP server bên trong Blender, thực thi code bpy trên main thread
- **`server.py`** — MCP server (stdio): 24 tool để tạo, chỉnh sửa, render và import/export scene

```
MCP client (stdio) ──> server.py ──(TCP 127.0.0.1:9877)──> addon trong Blender ──> bpy
```

## Yêu cầu

- Blender 4.2+ (đã test với 5.2 LTS)
- Python 3.10+ chạy MCP server (có thể dùng Python đi kèm Blender nếu máy không có Python riêng)

## Hướng dẫn cài đặt

### 1. Cài addon vào Blender

**Cách A (khuyên dùng):**
1. Mở Blender > `Edit` > `Preferences` > `Add-ons`
2. Nhấn `Install...` (nút mũi tên xuống góc phải trên) và chọn file `addon.py`
3. Tìm "Blender MCP Server" trong danh sách và bật checkbox

**Cách B:** chép `addon.py` vào thư mục addons của Blender, ví dụ:
`C:\Program Files\Blender Foundation\Blender 5.2\5.2\scripts\addons\`

### 2. Bật server trong Blender

Mở sidebar (phím `N` trong 3D Viewport) > tab **MCP** > nhấn **Start MCP Server**.

Server lắng nghe tại `127.0.0.1:9877`. Cổng mặc định khác với blender-mcp gốc (9876) để không xung đột nếu bạn cài cả hai.

### 3. Cài dependency cho MCP server

```bash
pip install -r requirements.txt
```

Nếu máy không có Python riêng, dùng Python đi kèm Blender:

```powershell
& "C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe" -m pip install -r requirements.txt
```

### 4. Đăng ký MCP với client

**opencode** (`opencode.json`):

```json
{
  "mcp": {
    "maket-blender": {
      "type": "local",
      "command": ["python", "C:/duong/dan/den/blender-mcp/server.py"],
      "enabled": true
    }
  }
}
```

**Claude Desktop** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "maket-blender": {
      "command": "python",
      "args": ["C:/duong/dan/den/blender-mcp/server.py"]
    }
  }
}
```

**Cursor / MCP client khác:** dùng lệnh `python C:/duong/dan/den/blender-mcp/server.py` với transport `stdio`.

### Biến môi trường (tùy chọn)

| Biến | Mặc định | Mô tả |
|---|---|---|
| `BLENDER_MCP_HOST` | `127.0.0.1` | Host của addon (phía server.py) |
| `BLENDER_MCP_PORT` | `9877` | Cổng kết nối (phía server.py) |
| `BLENDER_MCP_ADDON_PORT` | `9877` | Cổng lắng nghe (phía addon, đặt trước khi mở Blender) |

## Chạy Blender headless (không giao diện)

```bash
blender -b --python headless_runner.py
```

Blender sẽ chạy nền và xử lý lệnh từ MCP server bình thường.

## Danh sách tool (24)

| Nhóm | Tool |
|---|---|
| Kết nối / tự do | `ping`, `execute_blender_code` |
| Thông tin scene | `get_scene_info`, `get_object_info` |
| Tạo / xóa | `create_primitive`, `delete_object`, `clear_scene` |
| Transform | `set_transform`, `duplicate_object`, `rename_object` |
| Camera / đèn | `add_camera`, `set_active_camera`, `add_light` |
| Modifier | `add_modifier`, `apply_modifiers` |
| Vật liệu | `set_material_color`, `set_image_texture`, `set_emission` |
| Mesh | `join_objects` |
| Import / Export | `import_model`, `export_model` |
| Render / lưu | `render_image`, `get_viewport_screenshot`, `save_blend` |

## Kiểm tra

Bật addon + Start server trong Blender (hoặc chạy headless), sau đó:

```bash
python test_client.py      # test 9 tool cơ bản qua socket
python test_new_tools.py   # test 15 tool nâng cao
python test_stdio.py       # test giao thức MCP stdio chuẩn
```

## Ghi chú

- Tool `execute_blender_code` cho phép chạy code Python tùy ý trong Blender với các biến có sẵn: `bpy`, `C` (= `bpy.context`), `D` (= `bpy.data`)
- Mọi lệnh đều được thực thi trên main thread của Blender nên an toàn với bpy
