"""MCP server điều khiển Blender qua socket TCP.

Yêu cầu: addon.py đã được cài và bật trong Blender
(3D Viewport > Sidebar > MCP > Start MCP Server).

Chạy: python server.py
"""
import json
import os
import socket

from mcp.server.fastmcp import FastMCP

HOST = os.environ.get("BLENDER_MCP_HOST", "127.0.0.1")
PORT = int(os.environ.get("BLENDER_MCP_PORT", "9877"))

mcp = FastMCP(
    "maket-blender",
    instructions="MCP server điều khiển Blender qua addon Blender MCP Server. "
    "Mọi thao tác 3D đều thông qua các tool ở đây.",
)


def send_command(cmd: dict, timeout: float = 60.0) -> dict:
    with socket.create_connection((HOST, PORT), timeout=10.0) as sock:
        sock.sendall((json.dumps(cmd) + "\n").encode("utf-8"))
        sock.settimeout(timeout)
        buf = b""
        while b"\n" not in buf:
            chunk = sock.recv(65536)
            if not chunk:
                break
            buf += chunk
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
def set_image_texture(object_name: str, image_path: str, material_name: str = "") -> dict:
    """Gán ảnh texture vào Base Color của material object (tạo material nếu chưa có).

    Args:
        object_name: Tên object.
        image_path: Đường dẫn file ảnh (png, jpg, hdr...).
        material_name: Tên material (mặc định <object>_mat).
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
tex = next((n for n in nt.nodes if n.type == "TEX_IMAGE"), None)
if tex is None:
    tex = nt.nodes.new("ShaderNodeTexImage")
tex.image = img
bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
print(json.dumps({"material": mat.name, "image": img.name}))
""" % (
        _js(object_name),
        _js(image_path),
        _js(material_name),
        bool(material_name),
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


if __name__ == "__main__":
    mcp.run()
