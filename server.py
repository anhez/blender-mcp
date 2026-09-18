"""MCP server điều khiển Blender qua socket TCP.

Yêu cầu: addon.py đã được cài và bật trong Blender
(3D Viewport > Sidebar > MCP > Start MCP Server).

Chạy: python server.py
"""
import json
import os
import socket
import urllib.parse
import urllib.request

from mcp.server.fastmcp import FastMCP

HOST = os.environ.get("BLENDER_MCP_HOST", "127.0.0.1")
PORT = int(os.environ.get("BLENDER_MCP_PORT", "9877"))

mcp = FastMCP(
    "maket-blender",
    instructions="MCP server điều khiển Blender qua addon Blender MCP Server. "
    "Mọi thao tác 3D đều thông qua các tool ở đây. "
    "Hỗ trợ: tạo/chỉnh sửa object, vật liệu, camera, đèn, animation, world/HDRI, "
    "modifier, import/export, render và tải asset từ PolyHaven.",
)


def send_command(cmd: dict, timeout: float = 60.0) -> dict:
    try:
        with socket.create_connection((HOST, PORT), timeout=10.0) as sock:
            sock.sendall((json.dumps(cmd) + "\n").encode("utf-8"))
            sock.settimeout(timeout)
            buf = b""
            while b"\n" not in buf:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                buf += chunk
    except (ConnectionRefusedError, TimeoutError, socket.timeout, OSError) as e:
        raise ConnectionError(
            f"Không kết nối được Blender ({HOST}:{PORT}). "
            "Hãy mở Blender, vào Sidebar (N) > tab MCP > Start MCP Server, "
            f"hoặc chạy headless. Chi tiết: {e}"
        ) from e
    if not buf:
        raise ConnectionError(
            f"Blender đóng kết nối mà không phản hồi ({HOST}:{PORT}). "
            "Có thể Blender đang bận hoặc addon bị lỗi."
        )
    return json.loads(buf.decode("utf-8"))


def execute(code: str, timeout: float = 60.0) -> dict:
    resp = send_command({"type": "execute_code", "code": code, "id": 0}, timeout=timeout)
    if resp.get("status") == "error":
        raise RuntimeError(resp.get("error", "Unknown Blender error"))
    return resp


def _js(value) -> str:
    return json.dumps(value)


def _py(value) -> str:
    """Chuyển giá trị Python sang literal Python (xử lý None/True/False/dict)."""
    if value is None:
        return "None"
    if value is True:
        return "True"
    if value is False:
        return "False"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_py(v) for v in value) + "]"
    if isinstance(value, dict):
        return "{" + ", ".join(f"{json.dumps(k)}: {_py(v)}" for k, v in value.items()) + "}"
    return json.dumps(value)


@mcp.tool()
def ping() -> dict:
    """Kiểm tra kết nối tới Blender, trả về phiên bản Blender."""
    resp = execute(
        "import bpy; print(json.dumps({'blender_version': bpy.app.version_string, 'scene': bpy.context.scene.name}))",
        timeout=15,
    )
    return json.loads(resp["output"])


@mcp.tool()
def execute_blender_code(code: str) -> str:
    """Chạy code Python tùy ý trong Blender (biến bpy, C=bpy.context, D=bpy.data khả dụng).

    Args:
        code: Code Python chạy trong Blender. Output được capture và trả về.
    """
    resp = execute(code)
    out = resp.get("output", "")
    if resp.get("stderr"):
        out += "\n[stderr]\n" + resp["stderr"]
    return out


@mcp.tool()
def get_scene_info() -> dict:
    """Lấy thông tin tổng quan scene: danh sách objects, materials, camera, lights, render settings."""
    code = """
import json
s = bpy.context.scene
objects = []
for o in s.objects:
    objects.append({
        "name": o.name,
        "type": o.type,
        "location": list(o.location),
        "visible": not o.hide_viewport,
    })
materials = [m.name for m in bpy.data.materials]
result = {
    "scene": s.name,
    "engine": s.render.engine,
    "frame": s.frame_current,
    "camera": s.camera.name if s.camera else None,
    "objects": objects,
    "materials": materials,
    "lights": [o.name for o in s.objects if o.type == "LIGHT"],
}
print(json.dumps(result))
"""
    return json.loads(execute(code)["output"])


@mcp.tool()
def get_object_info(object_name: str) -> dict:
    """Lấy thông tin chi tiết của một object: transform, dimensions, material, data.

    Args:
        object_name: Tên object trong Blender.
    """
    code = """
import json
o = D.objects[%s]
result = {
    "name": o.name,
    "type": o.type,
    "location": list(o.location),
    "rotation_euler": list(o.rotation_euler),
    "scale": list(o.scale),
    "dimensions": list(o.dimensions),
    "materials": [m.name for m in o.data.materials if m] if o.type == "MESH" else [],
    "visible": not o.hide_viewport,
    "parent": o.parent.name if o.parent else None,
}
print(json.dumps(result))
""" % _js(object_name)
    return json.loads(execute(code)["output"])


@mcp.tool()
def create_primitive(
    primitive_type: str,
    name: str = "",
    location: list = (0.0, 0.0, 0.0),
    size: float = 2.0,
) -> dict:
    """Tạo mesh primitive (cube, uv_sphere, ico_sphere, cylinder, cone, torus, plane, circle, grid, monkey, round_cube...).

    Args:
        primitive_type: Loại primitive, tương ứng hậu tố của bpy.ops.mesh.primitive_*_add.
        name: Tên object (mặc định Blender tự đặt).
        location: Vị trí [x, y, z] (mặc định origin).
        size: Kích thước (mặc định 2m).
    """
    code = """
import json
op_name = "primitive_" + %s + "_add"
if not hasattr(bpy.ops.mesh, op_name):
    raise ValueError("Khong co primitive loai '" + %s + "' (vd: cube, uv_sphere, cylinder)")
op = getattr(bpy.ops.mesh, op_name)
loc = %s
s = %s
kwargs = {
    "cube": {"size": s},
    "round_cube": {"size": s},
    "plane": {"size": s},
    "grid": {"size": s},
    "monkey": {"size": s},
    "uv_sphere": {"radius": s},
    "ico_sphere": {"radius": s},
    "circle": {"radius": s},
    "cylinder": {"radius": s / 2, "depth": s},
    "cone": {"radius1": s / 2, "depth": s},
    "torus": {"major_radius": s / 2, "minor_radius": s / 4},
}.get(%s, {"size": s})
kwargs["location"] = loc
op(**kwargs)
o = bpy.context.active_object
if %s:
    o.name = %s
    o.data.name = %s
print(json.dumps({"name": o.name, "type": o.type, "location": list(o.location)}))
""" % (
        _js(primitive_type),
        _js(primitive_type),
        _js(list(location)),
        size,
        _js(primitive_type),
        bool(name),
        _js(name),
        _js(name),
    )
    return json.loads(execute(code)["output"])


@mcp.tool()
def delete_object(object_name: str) -> str:
    """Xóa object khỏi scene.

    Args:
        object_name: Tên object cần xóa.
    """
    code = """
o = D.objects[%s]
D.objects.remove(o, do_unlink=True)
print("deleted")
""" % _js(object_name)
    execute(code)
    return f"Đã xóa '{object_name}'"


@mcp.tool()
def set_material_color(
    object_name: str,
    color: list = (0.8, 0.8, 0.8),
    metallic: float = 0.0,
    roughness: float = 0.5,
) -> str:
    """Gán material màu cho object (tạo mới nếu chưa có).

    Args:
        object_name: Tên object.
        color: Màu RGB, mỗi kênh 0.0-1.0.
        metallic: Độ kim loại 0.0-1.0.
        roughness: Độ nhám 0.0-1.0.
    """
    code = """
o = D.objects[%s]
mat = bpy.data.materials.new(%s) if %s not in bpy.data.materials else bpy.data.materials[%s]
mat.use_nodes = True
bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
bsdf.inputs["Base Color"].default_value = (*%s, 1.0)
bsdf.inputs["Metallic"].default_value = %s
bsdf.inputs["Roughness"].default_value = %s
if o.data.materials:
    o.data.materials[0] = mat
else:
    o.data.materials.append(mat)
print("ok")
""" % (
        _js(object_name),
        _js(object_name + "_mat"),
        _js(object_name + "_mat"),
        _js(object_name + "_mat"),
        _js(list(color)),
        metallic,
        roughness,
    )
    execute(code)
    return f"Đã gán material cho '{object_name}'"


@mcp.tool()
def render_image(
    filepath: str,
    resolution_x: int = 1920,
    resolution_y: int = 1080,
) -> str:
    """Render scene từ camera hiện tại và lưu ảnh.

    Args:
        filepath: Đường dẫn file ảnh (.png, .jpg...).
        resolution_x: Chiều rộng render (px).
        resolution_y: Chiều cao render (px).
    """
    code = """
s = bpy.context.scene
s.render.filepath = %s
s.render.resolution_x = %s
s.render.resolution_y = %s
bpy.ops.render.render(write_still=True)
print(s.render.filepath)
""" % (
        _js(filepath),
        resolution_x,
        resolution_y,
    )
    resp = execute(code, timeout=600)
    return resp["output"].strip()


@mcp.tool()
def save_blend(filepath: str) -> str:
    """Lưu file .blend hiện tại.

    Args:
        filepath: Đường dẫn file .blend.
    """
    code = """
bpy.ops.wm.save_as_mainfile(filepath=%s)
print("saved")
""" % _js(filepath)
    execute(code)
    return f"Đã lưu '{filepath}'"


@mcp.tool()
def set_transform(
    object_name: str,
    location: list | None = None,
    rotation_euler: list | None = None,
    scale: list | None = None,
) -> dict:
    """Đặt vị trí/xoay/tỷ lệ cho object (chỉ cập nhật thuộc tính được truyền).

    Args:
        object_name: Tên object.
        location: [x, y, z] mới.
        rotation_euler: [rx, ry, rz] theo radian.
        scale: [sx, sy, sz] mới.
    """
    code = """
import json
o = D.objects[%s]
if %s is not None:
    o.location = %s
if %s is not None:
    o.rotation_euler = %s
if %s is not None:
    o.scale = %s
print(json.dumps({"name": o.name, "location": list(o.location), "rotation_euler": list(o.rotation_euler), "scale": list(o.scale)}))
""" % (
        _js(object_name),
        _py(location),
        _py(list(location) if location else None),
        _py(rotation_euler),
        _py(list(rotation_euler) if rotation_euler else None),
        _py(scale),
        _py(list(scale) if scale else None),
    )
    return json.loads(execute(code)["output"])


@mcp.tool()
def duplicate_object(object_name: str, new_name: str = "") -> dict:
    """Nhân bản object (mesh data độc lập).

    Args:
        object_name: Tên object gốc.
        new_name: Tên bản sao (mặc định Blender tự đặt).
    """
    code = """
import json
o = D.objects[%s]
cp = o.copy()
cp.data = o.data.copy()
C.collection.objects.link(cp)
if %s:
    cp.name = %s
    cp.data.name = %s
print(json.dumps({"name": cp.name, "type": cp.type, "location": list(cp.location)}))
""" % (
        _js(object_name),
        bool(new_name),
        _js(new_name),
        _js(new_name),
    )
    return json.loads(execute(code)["output"])


@mcp.tool()
def rename_object(object_name: str, new_name: str) -> str:
    """Đổi tên object (và mesh data của nó).

    Args:
        object_name: Tên hiện tại.
        new_name: Tên mới.
    """
    code = """
o = D.objects[%s]
o.name = %s
o.data.name = %s
print(o.name)
""" % (_js(object_name), _js(new_name), _js(new_name))
    return execute(code)["output"].strip()


@mcp.tool()
def add_light(
    light_type: str = "POINT",
    name: str = "",
    location: list = (0.0, 0.0, 2.0),
    energy: float = 100.0,
    color: list = (1.0, 1.0, 1.0),
) -> dict:
    """Thêm đèn vào scene.

    Args:
        light_type: POINT, SUN, SPOT hoặc AREA.
        name: Tên đèn (mặc định Blender tự đặt).
        location: Vị trí [x, y, z].
        energy: Cường độ (W hoặc W/m2 với SUN).
        color: Màu RGB 0.0-1.0.
    """
    code = """
import json
lt = %s.upper()
if lt not in ("POINT", "SUN", "SPOT", "AREA"):
    raise ValueError("light_type phai la POINT, SUN, SPOT hoac AREA")
ld = D.lights.new(%s if %s else (lt + " Light"), lt)
ld.energy = %s
ld.color = %s
ob = D.objects.new(ld.name, ld)
C.collection.objects.link(ob)
ob.location = %s
print(json.dumps({"name": ob.name, "type": lt, "energy": ld.energy}))
""" % (
        _js(light_type),
        _js(name),
        bool(name),
        energy,
        _py(list(color)),
        _py(list(location)),
    )
    return json.loads(execute(code)["output"])


@mcp.tool()
def add_camera(
    name: str = "",
    location: list = (7.0, -7.0, 5.0),
    rotation_euler: list = (1.1, 0.0, 0.785),
) -> dict:
    """Thêm camera vào scene.

    Args:
        name: Tên camera (mặc định Blender tự đặt).
        location: Vị trí [x, y, z].
        rotation_euler: Góc xoay [rx, ry, rz] radian (mặc định nhìn về origin).
    """
    code = """
import json
cam_data = D.cameras.new(%s if %s else "Camera MCP")
cam = D.objects.new(cam_data.name, cam_data)
C.collection.objects.link(cam)
cam.location = %s
cam.rotation_euler = %s
print(json.dumps({"name": cam.name, "location": list(cam.location)}))
""" % (
        _js(name),
        bool(name),
        _py(list(location)),
        _py(list(rotation_euler)),
    )
    return json.loads(execute(code)["output"])


@mcp.tool()
def set_active_camera(camera_name: str) -> str:
    """Đặt camera render cho scene.

    Args:
        camera_name: Tên camera.
    """
    code = """
C.scene.camera = D.objects[%s]
print(C.scene.camera.name)
""" % _js(camera_name)
    return f"Camera active: {execute(code)['output'].strip()}"


@mcp.tool()
def add_modifier(object_name: str, modifier_type: str, name: str = "", params: dict | None = None) -> dict:
    """Thêm modifier cho object (SUBSURF, BEVEL, SOLIDIFY, MIRROR, ARRAY, BOOLEAN, DECIMATE, WIREFRAME...).

    Args:
        object_name: Tên object.
        modifier_type: Loại modifier (tên không phân biệt hoa thường).
        name: Tên modifier (mặc định Blender tự đặt).
        params: Dict tham số, ví dụ {"levels": 2} cho SUBSURF, {"thickness": 0.1} cho SOLIDIFY.
                Với MIRROR/BOOLEAN có thể truyền {"object": "TênObjectKhac"}.
    """
    code = """
import json
o = D.objects[%s]
mtype = %s.upper()
try:
    m = o.modifiers.new(%s if %s else (mtype + "." + o.name), mtype)
except Exception:
    raise ValueError("Modifier loai '" + mtype + "' khong hop le. Cac loai thuong dung: SUBSURF, BEVEL, SOLIDIFY, MIRROR, ARRAY, BOOLEAN, DECIMATE, WIREFRAME, REMESH, SKIN, SMOOTH, TRIANGULATE")
params = %s or {}
for k, v in params.items():
    if k in ("object", "mirror_object") and isinstance(v, str):
        v = D.objects[v]
    setattr(m, k, v)
print(json.dumps({"name": m.name, "type": m.type}))
""" % (
        _js(object_name),
        _js(modifier_type),
        _js(name),
        bool(name),
        _py(params),
    )
    return json.loads(execute(code)["output"])


@mcp.tool()
def apply_modifiers(object_name: str) -> str:
    """Áp dụng (apply) toàn bộ modifier của object.

    Args:
        object_name: Tên object.
    """
    code = """
o = D.objects[%s]
C.view_layer.objects.active = o
bpy.ops.object.select_all(action="DESELECT")
o.select_set(True)
count = len(o.modifiers)
for m in list(o.modifiers):
    bpy.ops.object.modifier_apply(modifier=m.name)
print("applied " + str(count))
""" % _js(object_name)
    return execute(code)["output"].strip()


@mcp.tool()
def join_objects(object_names: list) -> dict:
    """Gộp nhiều object thành một (object đầu tiên giữ lại).

    Args:
        object_names: Danh sách tên object cần gộp.
    """
    code = """
import json
obs = [D.objects[n] for n in %s]
if len(obs) < 2:
    raise ValueError("Can it nhat 2 object de join")
C.view_layer.objects.active = obs[0]
bpy.ops.object.select_all(action="DESELECT")
for o in obs:
    o.select_set(True)
bpy.ops.object.join()
print(json.dumps({"joined_into": obs[0].name, "count": len(obs)}))
""" % _js(list(object_names))
    return json.loads(execute(code)["output"])


@mcp.tool()
def set_image_texture(
    object_name: str,
    image_path: str,
    material_name: str = "",
    map_type: str = "base_color",
) -> dict:
    """Gán ảnh texture vào material của object (tạo material nếu chưa có).

    Args:
        object_name: Tên object.
        image_path: Đường dẫn file ảnh (png, jpg, hdr...).
        material_name: Tên material (mặc định <object>_mat).
        map_type: Loại map: base_color, normal, roughness, metallic, emission.
    """
    code = """
import json
o = D.objects[%s]
img = D.images.load(%s)
mat_name = %s if %s else (o.name + "_mat")
mat = D.materials.get(mat_name)
if mat is None:
    mat = D.materials.new(mat_name)
if o.data.materials:
    o.data.materials[0] = mat
else:
    o.data.materials.append(mat)
mat.use_nodes = True
nt = mat.node_tree
map_type = %s
tex = next((n for n in nt.nodes if n.type == "TEX_IMAGE" and n.image == img), None)
if tex is None:
    tex = nt.nodes.new("ShaderNodeTexImage")
tex.image = img
bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
if map_type == "normal":
    tex.image.colorspace_settings.name = "Non-Color"
    nmap = next((n for n in nt.nodes if n.type == "NORMAL_MAP"), None)
    if nmap is None:
        nmap = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(tex.outputs["Color"], nmap.inputs["Color"])
    nt.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])
elif map_type == "roughness":
    tex.image.colorspace_settings.name = "Non-Color"
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Roughness"])
elif map_type == "metallic":
    tex.image.colorspace_settings.name = "Non-Color"
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Metallic"])
elif map_type == "emission":
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Emission Color"])
else:
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
print(json.dumps({"material": mat.name, "image": img.name, "map_type": map_type}))
""" % (
        _js(object_name),
        _js(image_path),
        _js(material_name),
        bool(material_name),
        _js(map_type),
    )
    return json.loads(execute(code)["output"])


@mcp.tool()
def set_emission(object_name: str, strength: float = 5.0, color: list = (1.0, 1.0, 1.0)) -> str:
    """Bật phát sáng (emission) cho object (tạo material nếu chưa có).

    Args:
        object_name: Tên object.
        strength: Cường độ phát sáng.
        color: Màu RGB 0.0-1.0.
    """
    code = """
o = D.objects[%s]
mat = o.data.materials[0] if o.data.materials else None
if mat is None:
    mat = D.materials.new(o.name + "_mat")
    o.data.materials.append(mat)
mat.use_nodes = True
bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
bsdf.inputs["Emission Color"].default_value = (*%s, 1.0)
bsdf.inputs["Emission Strength"].default_value = %s
print("ok")
""" % (
        _js(object_name),
        _py(list(color)),
        strength,
    )
    execute(code)
    return f"Đã bật emission cho '{object_name}'"


@mcp.tool()
def import_model(filepath: str) -> dict:
    """Import model vào scene (.glb, .gltf, .fbx, .obj, .stl, .ply).

    Args:
        filepath: Đường dẫn file model.
    """
    code = """
import json
import sys as _sys
import io as _io
fp = %s
ext = fp.rsplit(".", 1)[-1].lower()
before = set(D.objects)
_outer = _sys.stdout
_sys.stdout = _io.StringIO()
try:
    if ext in ("glb", "gltf"):
        bpy.ops.import_scene.gltf(filepath=fp)
    elif ext == "fbx":
        bpy.ops.import_scene.fbx(filepath=fp)
    elif ext == "obj":
        bpy.ops.wm.obj_import(filepath=fp)
    elif ext == "stl":
        bpy.ops.wm.stl_import(filepath=fp)
    elif ext == "ply":
        bpy.ops.wm.ply_import(filepath=fp)
    else:
        raise ValueError("Khong ho tro format: " + ext)
finally:
    _sys.stdout = _outer
new = [o.name for o in D.objects if o.name not in before]
print(json.dumps({"filepath": fp, "imported": new}))
""" % _js(filepath)
    return json.loads(execute(code, timeout=300)["output"])


@mcp.tool()
def export_model(filepath: str, object_names: list | None = None) -> str:
    """Export model ra file (.glb, .gltf, .fbx, .obj).

    Args:
        filepath: Đường dẫn file xuất ra.
        object_names: Danh sách object cần export (mặc định toàn bộ scene).
    """
    code = """
import sys as _sys
import io as _io
fp = %s
names = %s
obs = [D.objects[n] for n in names] if names else list(D.objects)
bpy.ops.object.select_all(action="DESELECT")
for o in obs:
    o.select_set(True)
C.view_layer.objects.active = obs[0] if obs else None
ext = fp.rsplit(".", 1)[-1].lower()
_outer = _sys.stdout
_sys.stdout = _io.StringIO()
try:
    if ext in ("glb", "gltf"):
        bpy.ops.export_scene.gltf(filepath=fp, use_selection=bool(names))
    elif ext == "fbx":
        bpy.ops.export_scene.fbx(filepath=fp, use_selection=bool(names))
    elif ext == "obj":
        bpy.ops.wm.obj_export(filepath=fp, export_selected_objects=bool(names))
    else:
        raise ValueError("Khong ho tro format: " + ext)
finally:
    _sys.stdout = _outer
print(fp)
""" % (
        _js(filepath),
        _py(list(object_names) if object_names else None),
    )
    return execute(code, timeout=300)["output"].strip()


@mcp.tool()
def clear_scene(keep_camera: bool = False, purge_orphans: bool = True) -> str:
    """Xóa toàn bộ object trong scene.

    Args:
        keep_camera: Giữ lại camera active.
        purge_orphans: Dọn dữ liệu rác (mesh/material không dùng nữa).
    """
    code = """
import sys as _sys
import io as _io
cam = C.scene.camera.name if C.scene.camera else None
keep = [D.objects[cam]] if (%s and cam) else []
_outer = _sys.stdout
_sys.stdout = _io.StringIO()
try:
    bpy.ops.object.select_all(action="SELECT")
    for o in keep:
        o.select_set(False)
    bpy.ops.object.delete(use_global=False)
    if %s:
        try:
            bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
        except Exception:
            pass
finally:
    _sys.stdout = _outer
print("cleared")
""" % (bool(keep_camera), bool(purge_orphans))
    return execute(code)["output"].strip()


@mcp.tool()
def get_viewport_screenshot(
    filepath: str,
    resolution_x: int = 800,
    resolution_y: int = 600,
) -> str:
    """Chụp ảnh viewport (render nhanh với viewport settings) và lưu file.

    Args:
        filepath: Đường dẫn file ảnh .png.
        resolution_x: Chiều rộng (px).
        resolution_y: Chiều cao (px).
    """
    code = """
s = C.scene
s.render.filepath = %s
s.render.resolution_x = %s
s.render.resolution_y = %s
bpy.ops.render.render(write_still=True, use_viewport=True)
print(s.render.filepath)
""" % (
        _js(filepath),
        resolution_x,
        resolution_y,
    )
    resp = execute(code, timeout=600)
    return resp["output"].strip()


@mcp.tool()
def camera_look_at(camera_name: str, target_name: str) -> str:
    """Hướng camera nhìn về một object (dùng TRACK_TO constraint).

    Args:
        camera_name: Tên camera.
        target_name: Tên object cần nhìn tới.
    """
    code = """
o = D.objects[%s]
t = D.objects[%s]
if o.type != "CAMERA":
    raise ValueError("Object phai la camera")
con = o.constraints.get("MCP Look At")
if con is None:
    con = o.constraints.new("TRACK_TO")
    con.name = "MCP Look At"
con.target = t
con.track_axis = "TRACK_NEGATIVE_Z"
con.up_axis = "UP_Y"
print("ok")
""" % (_js(camera_name), _js(target_name))
    execute(code)
    return f"'{camera_name}' đang nhìn về '{target_name}'"


@mcp.tool()
def set_camera_fov(camera_name: str, fov_degrees: float = 50.0) -> str:
    """Đặt góc nhìn (FOV dọc, độ) cho camera.

    Args:
        camera_name: Tên camera.
        fov_degrees: Góc FOV theo độ (mặc định 50).
    """
    code = """
import math as _m
o = D.objects[%s]
if o.type != "CAMERA":
    raise ValueError("Object phai la camera")
o.data.angle = _m.radians(%s)
print(str(o.data.angle))
""" % (_js(camera_name), fov_degrees)
    execute(code)
    return f"FOV của '{camera_name}' = {fov_degrees} độ"


@mcp.tool()
def set_world_hdri(image_path: str, strength: float = 1.0) -> str:
    """Đặt ảnh HDRI làm môi trường (world) cho scene.

    Args:
        image_path: Đường dẫn file .hdr/.exr.
        strength: Cường độ ánh sáng môi trường (mặc định 1.0).
    """
    code = """
world = C.scene.world
if world is None:
    world = D.worlds.new("World MCP")
    C.scene.world = world
world.use_nodes = True
nt = world.node_tree
nt.nodes.clear()
env = nt.nodes.new("ShaderNodeTexEnvironment")
bg = nt.nodes.new("ShaderNodeBackground")
out = nt.nodes.new("ShaderNodeOutputWorld")
env.image = D.images.load(%s)
bg.inputs["Strength"].default_value = %s
nt.links.new(env.outputs["Color"], bg.inputs["Color"])
nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
print("ok")
""" % (_js(image_path), strength)
    execute(code)
    return f"Đã đặt world HDRI '{image_path}'"


@mcp.tool()
def set_frame(frame: int) -> int:
    """Chuyển scene tới frame chỉ định.

    Args:
        frame: Số frame.
    """
    code = """
C.scene.frame_set(%s)
print(C.scene.frame_current)
""" % frame
    return int(execute(code)["output"].strip())


@mcp.tool()
def insert_keyframe(
    object_name: str,
    property_path: str = "location",
    value: list | None = None,
    frame: int | None = None,
) -> str:
    """Chèn keyframe cho thuộc tính của object (animation).

    Args:
        object_name: Tên object.
        property_path: Đường dẫn thuộc tính: location, rotation_euler, scale...
        value: Giá trị tại frame này (list [x, y, z]); nếu bỏ qua dùng giá trị hiện tại.
        frame: Frame chèn keyframe; nếu bỏ qua dùng frame hiện tại.
    """
    code = """
o = D.objects[%s]
if %s is not None:
    C.scene.frame_set(%s)
if %s is not None:
    setattr(o, %s, %s)
ok = o.keyframe_insert(data_path=%s, index=-1)
print("keyframed " + str(ok) + " at frame " + str(C.scene.frame_current))
""" % (
        _js(object_name),
        _py(frame),
        _py(frame),
        _py(value),
        _js(property_path),
        _py(list(value) if value else None),
        _js(property_path),
    )
    return execute(code)["output"].strip()


@mcp.tool()
def set_parent(child_name: str, parent_name: str, keep_transform: bool = True) -> str:
    """Gán object làm con của object khác.

    Args:
        child_name: Tên object con.
        parent_name: Tên object cha.
        keep_transform: Giữ nguyên vị trí hiện tại của con (mặc định True).
    """
    code = """
c = D.objects[%s]
p = D.objects[%s]
mat = c.matrix_world.copy()
c.parent = p
if %s:
    c.matrix_world = mat
print("ok")
""" % (_js(child_name), _js(parent_name), bool(keep_transform))
    execute(code)
    return f"'{child_name}' là con của '{parent_name}'"


@mcp.tool()
def create_collection(name: str) -> str:
    """Tạo collection mới.

    Args:
        name: Tên collection.
    """
    code = """
col = D.collections.new(%s)
C.scene.collection.children.link(col)
print(col.name)
""" % _js(name)
    return execute(code)["output"].strip()


@mcp.tool()
def move_to_collection(object_names: list, collection_name: str) -> str:
    """Chuyển các object vào collection (tạo mới nếu chưa có).

    Args:
        object_names: Danh sách tên object.
        collection_name: Tên collection đích.
    """
    code = """
obs = [D.objects[n] for n in %s]
col = D.collections.get(%s)
if col is None:
    col = D.collections.new(%s)
    C.scene.collection.children.link(col)
for o in obs:
    for c2 in list(o.users_collection):
        c2.objects.unlink(o)
    col.objects.link(o)
print(col.name)
""" % (_js(list(object_names)), _js(collection_name), _js(collection_name))
    return f"Moved to '{execute(code)['output'].strip()}'"


@mcp.tool()
def remove_modifier(object_name: str, modifier_name: str) -> str:
    """Xóa modifier khỏi object.

    Args:
        object_name: Tên object.
        modifier_name: Tên modifier cần xóa.
    """
    code = """
o = D.objects[%s]
m = o.modifiers.get(%s)
if m is None:
    raise ValueError("Khong tim thay modifier '" + %s + "'")
o.modifiers.remove(m)
print("removed")
""" % (_js(object_name), _js(modifier_name), _js(modifier_name))
    execute(code)
    return f"Đã xóa modifier '{modifier_name}'"


@mcp.tool()
def shade_smooth(object_name: str, smooth: bool = True) -> str:
    """Bật/tắt smooth shading cho mesh.

    Args:
        object_name: Tên object.
        smooth: True = smooth shading, False = flat.
    """
    code = """
o = D.objects[%s]
if o.type != "MESH":
    raise ValueError("Object phai la mesh")
for p in o.data.polygons:
    p.use_smooth = %s
o.data.update()
print("ok")
""" % (_js(object_name), bool(smooth))
    execute(code)
    return f"shade_smooth={smooth} cho '{object_name}'"


@mcp.tool()
def set_origin(object_name: str, origin_type: str = "ORIGIN_GEOMETRY") -> str:
    """Đặt origin (gốc tọa độ) của object.

    Args:
        object_name: Tên object.
        origin_type: ORIGIN_GEOMETRY, ORIGIN_CURSOR, ORIGIN_CENTER_OF_MASS, ORIGIN_CENTER_OF_VOLUME.
    """
    code = """
o = D.objects[%s]
C.view_layer.objects.active = o
bpy.ops.object.select_all(action="DESELECT")
o.select_set(True)
bpy.ops.object.origin_set(type=%s)
print("ok")
""" % (_js(object_name), _js(origin_type))
    execute(code)
    return f"Đã set origin '{origin_type}' cho '{object_name}'"


@mcp.tool()
def create_empty(
    name: str = "Empty MCP",
    location: list = (0.0, 0.0, 0.0),
    display_type: str = "PLAIN_AXES",
) -> dict:
    """Tạo object Empty (thường dùng làm target cho camera_look_at).

    Args:
        name: Tên empty.
        location: Vị trí [x, y, z].
        display_type: PLAIN_AXES, ARROWS, SPHERE, CUBE, CIRCLE...
    """
    code = """
import json
ob = D.objects.new(%s, None)
C.collection.objects.link(ob)
ob.location = %s
ob.empty_display_type = %s.upper()
print(json.dumps({"name": ob.name, "location": list(ob.location)}))
""" % (_js(name), _py(list(location)), _js(display_type))
    return json.loads(execute(code)["output"])


@mcp.tool()
def create_text(
    text: str,
    name: str = "",
    location: list = (0.0, 0.0, 0.0),
    size: float = 1.0,
    extrude: float = 0.0,
) -> dict:
    """Tạo object chữ (Text/Font).

    Args:
        text: Nội dung chữ.
        name: Tên object (mặc định Text MCP).
        location: Vị trí [x, y, z].
        size: Cỡ chữ.
        extrude: Độ dày 3D (0 = phẳng).
    """
    code = """
import json
f = D.curves.new(%s if %s else "Text MCP", "FONT")
f.body = %s
f.size = %s
f.extrude = %s
ob = D.objects.new(f.name, f)
C.collection.objects.link(ob)
ob.location = %s
print(json.dumps({"name": ob.name, "location": list(ob.location)}))
""" % (
        _js(name),
        bool(name),
        _js(text),
        size,
        extrude,
        _py(list(location)),
    )
    return json.loads(execute(code)["output"])


@mcp.tool()
def assign_material(object_name: str, material_name: str) -> str:
    """Gán material có sẵn (hoặc tạo mới) cho object.

    Args:
        object_name: Tên object.
        material_name: Tên material; nếu chưa tồn tại sẽ tạo material Principled BSDF mới.
    """
    code = """
o = D.objects[%s]
mat = D.materials.get(%s)
if mat is None:
    mat = D.materials.new(%s)
if o.data.materials:
    o.data.materials[0] = mat
else:
    o.data.materials.append(mat)
print(mat.name)
""" % (_js(object_name), _js(material_name), _js(material_name))
    return f"Đã gán material '{execute(code)['output'].strip()}'"


def _ph_api(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "maket-blender/1.1"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


@mcp.tool()
def search_polyhaven_assets(asset_type: str = "all", categories: str = "", limit: int = 20) -> list:
    """Tìm asset miễn phí trên PolyHaven.

    Args:
        asset_type: hdris, textures, models hoặc all.
        categories: Lọc theo danh mục (vd: "outdoor, skys"), bỏ trống = không lọc.
        limit: Số kết quả tối đa.
    """
    q = {"type": asset_type}
    if categories:
        q["categories"] = categories
    data = _ph_api("https://api.polyhaven.com/assets?" + urllib.parse.urlencode(q))
    out = []
    for aid, info in list(data.items())[:limit]:
        out.append(
            {
                "id": aid,
                "name": info.get("name"),
                "type": info.get("type"),
                "categories": info.get("categories", []),
                "description": (info.get("description") or "")[:200],
            }
        )
    return out


def _polyhaven_files(asset_id: str, asset_type: str, resolution: str) -> dict:
    """Trả về manifest: {'main': url, 'files': {relpath: url}}."""
    try:
        files = _ph_api(f"https://api.polyhaven.com/files/{asset_id}")
        if asset_type == "hdris":
            return {"main": files["hdri"][resolution]["hdr"]["url"], "files": {}}
        if asset_type == "textures":
            return {"main": files["Diffuse"][resolution]["jpg"]["url"], "files": {}}
        if asset_type == "models":
            g = files["gltf"][resolution]["gltf"]
            return {"main": g["url"], "files": {k: v["url"] for k, v in g.get("include", {}).items()}}
    except Exception:
        pass
    if asset_type == "hdris":
        return {
            "main": f"https://dl.polyhaven.org/file/ph-assets/HDRIs/hdr/{resolution}/{asset_id}_{resolution}.hdr",
            "files": {},
        }
    if asset_type == "textures":
        return {
            "main": f"https://dl.polyhaven.org/file/ph-assets/Textures/jpg/{resolution}/{asset_id}/{asset_id}_diff_{resolution}.jpg",
            "files": {},
        }
    raise ValueError("Không tìm được URL download cho model (thử lại files API)")


@mcp.tool()
def download_polyhaven_asset(
    asset_id: str,
    asset_type: str,
    resolution: str = "1k",
    object_name: str = "",
    strength: float = 1.0,
) -> dict:
    """Tải asset PolyHaven về và áp thẳng vào scene (không cần API key).

    Args:
        asset_id: ID asset (lấy từ search_polyhaven_assets).
        asset_type: hdris, textures hoặc models.
        resolution: 1k, 2k, 4k...
        object_name: Với textures: object được gán texture (bỏ trống = object đang active).
        strength: Với hdris: cường độ môi trường.
    """
    manifest = _polyhaven_files(asset_id, asset_type, resolution)
    code = """
import json
import os as _os
import tempfile as _tmp
import urllib.request as _ur
manifest = %s
base = _os.path.join(_tmp.gettempdir(), "maket_" + %s)
_os.makedirs(base, exist_ok=True)
for rel, u in manifest["files"].items():
    dst = _os.path.join(base, rel.replace("/", _os.sep))
    _os.makedirs(_os.path.dirname(dst), exist_ok=True)
    _ur.urlretrieve(u, dst)
ext = manifest["main"].rsplit(".", 1)[-1].lower().split("?")[0]
if ext not in ("hdr", "exr", "jpg", "png", "gltf", "glb"):
    ext = "bin"
main_file = _os.path.join(base, %s + "." + ext)
_ur.urlretrieve(manifest["main"], main_file)
result = {"asset_id": %s, "type": %s, "file": main_file}
if %s == "hdris":
    world = C.scene.world
    if world is None:
        world = D.worlds.new("World " + %s)
        C.scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    bg = nt.nodes.new("ShaderNodeBackground")
    out = nt.nodes.new("ShaderNodeOutputWorld")
    env.image = D.images.load(main_file)
    bg.inputs["Strength"].default_value = %s
    nt.links.new(env.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
elif %s == "textures":
    o = D.objects[%s] if %s else C.object
    if o is None:
        raise ValueError("Khong co object de gan texture")
    img = D.images.load(main_file)
    mat_name = o.name + "_polyhaven"
    mat = D.materials.get(mat_name)
    if mat is None:
        mat = D.materials.new(mat_name)
    if o.data.materials:
        o.data.materials[0] = mat
    else:
        o.data.materials.append(mat)
    mat.use_nodes = True
    nt = mat.node_tree
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    result["object"] = o.name
elif %s == "models":
    import sys as _sys
    import io as _io
    _outer = _sys.stdout
    _sys.stdout = _io.StringIO()
    try:
        before = set(D.objects)
        bpy.ops.import_scene.gltf(filepath=main_file)
        result["imported"] = [o.name for o in D.objects if o.name not in before]
    finally:
        result["import_log"] = _sys.stdout.getvalue().strip()
        _sys.stdout = _outer
print(json.dumps(result))
""" % (
        _js(manifest),
        _js(asset_id),
        _js(asset_id),
        _js(asset_id),
        _js(asset_type),
        _js(asset_type),
        _js(asset_id),
        strength,
        _js(asset_type),
        _js(object_name),
        bool(object_name),
        _js(asset_type),
    )
    return json.loads(execute(code, timeout=600)["output"])


def main():
    mcp.run()


if __name__ == "__main__":
    main()
