import os
import sys
import json

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import server as srv

TMP = r"C:\Users\ducan\AppData\Local\Temp\opencode"
os.makedirs(TMP, exist_ok=True)

print("== tools count ==", len(srv.mcp._tool_manager.list_tools()))
print(sorted(t.name for t in srv.mcp._tool_manager.list_tools()))

print("\n== clear_scene ==")
print(srv.clear_scene(keep_camera=True))

print("\n== create cubes ==")
print(json.dumps(srv.create_primitive("cube", "CubeA", [0, 0, 0], size=2.0), ensure_ascii=False))
print(json.dumps(srv.create_primitive("cube", "CubeB", [3, 0, 0], size=1.0), ensure_ascii=False))

print("\n== set_transform ==")
print(json.dumps(srv.set_transform("CubeB", location=[3, 1, 0], scale=[2, 1, 1]), ensure_ascii=False))
print(json.dumps(srv.set_transform("CubeA", rotation_euler=[0, 0, 0.785]), ensure_ascii=False))

print("\n== duplicate_object ==")
print(json.dumps(srv.duplicate_object("CubeA", "CubeACopy"), ensure_ascii=False))

print("\n== rename_object ==")
print(srv.rename_object("CubeACopy", "CubeRenamed"))

print("\n== add_light ==")
print(json.dumps(srv.add_light("SUN", "SunLight", [0, 0, 10], energy=50, color=[1.0, 0.9, 0.8]), ensure_ascii=False))
print(json.dumps(srv.add_light("AREA", "AreaLight", [2, 2, 4], energy=200, color=[0.5, 0.7, 1.0]), ensure_ascii=False))

print("\n== add_camera / set_active_camera ==")
print(json.dumps(srv.add_camera("McpCam", [8, -8, 6]), ensure_ascii=False))
print(srv.set_active_camera("McpCam"))

print("\n== add_modifier ==")
print(json.dumps(srv.add_modifier("CubeB", "SUBSURF", params={"levels": 2, "render_levels": 2}), ensure_ascii=False))
print(json.dumps(srv.add_modifier("CubeB", "SOLIDIFY", params={"thickness": 0.1}), ensure_ascii=False))

print("\n== apply_modifiers ==")
print(srv.apply_modifiers("CubeB"))

print("\n== set_material_color + set_emission ==")
print(srv.set_material_color("CubeA", [0.2, 0.5, 0.9], metallic=0.2, roughness=0.3))
print(srv.set_emission("CubeA", strength=8.0, color=[0.2, 0.5, 0.9]))

print("\n== render + set_image_texture ==")
png = os.path.join(TMP, "mcp_tex.png")
print(srv.render_image(png, 320, 240))
print(json.dumps(srv.set_image_texture("CubeRenamed", png), ensure_ascii=False))

print("\n== join_objects ==")
print(json.dumps(srv.join_objects(["CubeA", "CubeRenamed"]), ensure_ascii=False))

print("\n== export_model / import_model ==")
glb = os.path.join(TMP, "mcp_export.glb")
print(srv.export_model(glb, ["CubeA"]))
print(json.dumps(srv.import_model(glb), ensure_ascii=False))

print("\n== get_viewport_screenshot ==")
shot = os.path.join(TMP, "mcp_viewport.png")
print(srv.get_viewport_screenshot(shot, 400, 300))
print("exists:", os.path.exists(shot))

print("\n== error case: bad modifier ==")
try:
    srv.add_modifier("CubeB", "NOT_A_MODIFIER")
except RuntimeError as e:
    print("RuntimeError caught (OK):", str(e).splitlines()[-1])

print("\n== clear_scene ==")
print(srv.clear_scene())
info = srv.get_scene_info()
print("objects after clear:", [o["name"] for o in info["objects"]])

print("\nALL NEW TOOL TESTS DONE")
