# Blender MCP (maket-blender)

An MCP server that controls Blender over a TCP socket. It consists of two parts:

- **`addon.py`** — A Blender addon that runs a TCP server inside Blender and executes bpy code on the main thread
- **`server.py`** — An MCP server (stdio) with 40 tools to create, edit, animate, render, and import/export scenes

```
MCP client (stdio) ──> server.py ──(TCP 127.0.0.1:9877)──> addon inside Blender ──> bpy
```

## Requirements

- Blender 4.2+ (tested with 5.2 LTS)
- Python 3.10+ to run the MCP server

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

**Auto-start (optional):** launch Blender with the environment variable `BLENDER_MCP_AUTOSTART=1` and the server starts on its own — no button click needed.

### 3. Install the MCP server

```bash
pip install -e .
```

This installs the `maket-blender` command. If you prefer not to install, run `python server.py` directly.

### 4. Register the MCP server with your client

**opencode** (`opencode.json`):

```json
{
  "mcp": {
    "maket-blender": {
      "type": "local",
      "command": ["python", "/path/to/blender-mcp/server.py"],
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
      "args": ["/path/to/blender-mcp/server.py"]
    }
  }
}
```

**Cursor / other MCP clients:** use the command `maket-blender` (or `python /path/to/blender-mcp/server.py`) with the `stdio` transport.

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `BLENDER_MCP_HOST` | `127.0.0.1` | Host of the addon (server.py side) |
| `BLENDER_MCP_PORT` | `9877` | Connection port (server.py side) |
| `BLENDER_MCP_ADDON_PORT` | `9877` | Listening port (addon side, set before launching Blender) |
| `BLENDER_MCP_AUTOSTART` | `0` | `1` = start the TCP server automatically when Blender launches |

## Running Blender headless (no UI)

```bash
blender -b --python headless_runner.py
```

Blender will run in the background and process commands from the MCP server as usual.

## WSL setup

If the server runs in WSL2 while Blender runs on Windows (the setup this repo is currently used with):

1. **Mirrored networking** — by default WSL2 NAT networking cannot reach `127.0.0.1` services on Windows. Add to `C:\Users\<you>\.wslconfig`:

   ```ini
   [wsl2]
   networkingMode=mirrored
   ```

   then restart WSL with `wsl --shutdown`.

2. **Dependencies** — Ubuntu's system Python has no pip. Install in user space:

   ```bash
   curl -sS https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
   python3 /tmp/get-pip.py --user --break-system-packages
   python3 -m pip install --user -r requirements.txt --break-system-packages
   ```

3. **Client config** — from a Windows MCP client, launch the server via WSL:

   ```json
   {
     "command": "wsl.exe",
     "args": ["-d", "Ubuntu-24.04", "--", "python3", "/home/anhez/projects/blender-mcp/server.py"]
   }
   ```

4. **Headless Blender** — start from PowerShell with the UNC path to the runner inside WSL:

   ```powershell
   & "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b --python "\\wsl$\Ubuntu-24.04\home\anhez\projects\blender-mcp\headless_runner.py"
   ```

## Tools (40)

| Group | Tools |
|---|---|
| Connection / free-form | `ping`, `execute_blender_code` |
| Scene info | `get_scene_info`, `get_object_info` |
| Create / delete | `create_primitive`, `create_empty`, `create_text`, `delete_object`, `clear_scene` |
| Transform | `set_transform`, `duplicate_object`, `rename_object`, `set_parent`, `set_origin` |
| Camera / lights | `add_camera`, `set_active_camera`, `camera_look_at`, `set_camera_fov`, `add_light` |
| World / render | `set_world_hdri`, `render_image`, `get_viewport_screenshot`, `save_blend` |
| Modifiers | `add_modifier`, `apply_modifiers`, `remove_modifier` |
| Materials / shading | `set_material_color`, `set_image_texture` (base_color/normal/roughness/metallic/emission), `set_emission`, `assign_material`, `shade_smooth` |
| Mesh | `join_objects` |
| Animation | `set_frame`, `insert_keyframe` |
| Collections | `create_collection`, `move_to_collection` |
| Import / export | `import_model`, `export_model` |
| Asset library (PolyHaven, no API key) | `search_polyhaven_assets`, `download_polyhaven_asset` |

`download_polyhaven_asset` applies the asset automatically:
- `hdris` → set as world environment
- `textures` → assigned as Base Color material of an object
- `models` → imported into the scene (glTF, sidecar files included)

Poly Pizza and Sketchfab integrations are not included because they require API keys.

## Testing

Enable the addon and start the server in Blender (or run it headless), then:

```bash
python test_client.py      # basic tools over the socket
python test_new_tools.py   # advanced tools
python test_v3_tools.py    # camera/world/animation/collections + PolyHaven
python test_stdio.py       # standard MCP stdio protocol
```

## Notes

- The `execute_blender_code` tool lets you run arbitrary Python code inside Blender with these variables available: `bpy`, `C` (= `bpy.context`), `D` (= `bpy.data`)
- All commands are executed on Blender's main thread, so they are safe to use with bpy
- The TCP server binds to `127.0.0.1` only (no authentication) — only local processes can send commands
