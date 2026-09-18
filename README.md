# Blender MCP (maket-blender)

An MCP server that controls Blender over a TCP socket. It consists of two parts:

- **`addon.py`** — A Blender addon that runs a TCP server inside Blender and executes bpy code on the main thread
- **`server.py`** — An MCP server (stdio) with 24 tools to create, edit, render, and import/export scenes

```
MCP client (stdio) ──> server.py ──(TCP 127.0.0.1:9877)──> addon inside Blender ──> bpy
```

## Requirements

- Blender 4.2+ (tested with 5.2 LTS)
- Python 3.10+ to run the MCP server (you can use the Python bundled with Blender if you don't have a standalone Python)

## Installation

### 1. Install the addon in Blender

**Option A (recommended):**
1. Open Blender > `Edit` > `Preferences` > `Add-ons`
2. Click `Install...` (arrow-down button in the top-right corner) and select `addon.py`
3. Search for "Blender MCP Server" in the list and enable its checkbox

**Option B:** copy `addon.py` into Blender's addons folder, e.g.:
`C:\Program Files\Blender Foundation\Blender 5.2\5.2\scripts\addons\`

### 2. Start the server in Blender

Open the sidebar (press `N` in the 3D Viewport) > **MCP** tab > click **Start MCP Server**.

The server listens on `127.0.0.1:9877`. The default port differs from the original blender-mcp (9876) so you can have both installed without conflicts.

### 3. Install the MCP server dependencies

```bash
pip install -r requirements.txt
```

If you don't have a standalone Python, use the Python bundled with Blender:

```powershell
& "C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe" -m pip install -r requirements.txt
```

### 4. Register the MCP server with your client

**opencode** (`opencode.json`):

```json
{
  "mcp": {
    "maket-blender": {
      "type": "local",
      "command": ["python", "C:/path/to/blender-mcp/server.py"],
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
      "args": ["C:/path/to/blender-mcp/server.py"]
    }
  }
}
```

**Cursor / other MCP clients:** use the command `python C:/path/to/blender-mcp/server.py` with the `stdio` transport.

### Environment variables (optional)

| Variable | Default | Description |
|---|---|---|
| `BLENDER_MCP_HOST` | `127.0.0.1` | Host of the addon (server.py side) |
| `BLENDER_MCP_PORT` | `9877` | Connection port (server.py side) |
| `BLENDER_MCP_ADDON_PORT` | `9877` | Listening port (addon side, set before launching Blender) |

## Running Blender headless (no UI)

```bash
blender -b --python headless_runner.py
```

Blender will run in the background and process commands from the MCP server as usual.

## Tools (24)

| Group | Tools |
|---|---|
| Connection / free-form | `ping`, `execute_blender_code` |
| Scene info | `get_scene_info`, `get_object_info` |
| Create / delete | `create_primitive`, `delete_object`, `clear_scene` |
| Transform | `set_transform`, `duplicate_object`, `rename_object` |
| Camera / lights | `add_camera`, `set_active_camera`, `add_light` |
| Modifiers | `add_modifier`, `apply_modifiers` |
| Materials | `set_material_color`, `set_image_texture`, `set_emission` |
| Mesh | `join_objects` |
| Import / export | `import_model`, `export_model` |
| Render / save | `render_image`, `get_viewport_screenshot`, `save_blend` |

## Testing

Enable the addon and start the server in Blender (or run it headless), then:

```bash
python test_client.py      # tests the 9 basic tools over the socket
python test_new_tools.py   # tests the 15 advanced tools
python test_stdio.py       # tests the standard MCP stdio protocol
```

## Notes

- The `execute_blender_code` tool lets you run arbitrary Python code inside Blender with these variables available: `bpy`, `C` (= `bpy.context`), `D` (= `bpy.data`)
- All commands are executed on Blender's main thread, so they are safe to use with bpy
