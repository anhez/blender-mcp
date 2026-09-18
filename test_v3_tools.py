import os
import sys
import json

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import server as srv

TMP_WIN = r"C:\Users\ducan\AppData\Local\Temp\opencode"

def to_local(p):
    if os.path.exists("/mnt/c"):
        return "/mnt/c/" + p.replace("\\", "/")[3:]
    return p

os.makedirs(to_local(TMP_WIN), exist_ok=True)

print("== tools count ==", len(srv.mcp._tool_manager.list_tools()))
print(sorted(t.name for t in srv.mcp._tool_manager.list_tools()))

print("\n== clear_scene ==")
print(srv.clear_scene(keep_camera=True))

print("\n== camera: empty target + look_at + fov ==")
print(json.dumps(srv.create_empty("Target", [1, 1, 1], "SPHERE"), ensure_ascii=False))
print(json.dumps(srv.add_camera("Cam2", [8, -8, 6]), ensure_ascii=False))
print(srv.camera_look_at("Cam2", "Target"))
print(srv.set_camera_fov("Cam2", 35.0))
print(srv.set_active_camera("Cam2"))

print("\n== world HDRI (set_world_hdri) ==")
png = os.path.join(TMP_WIN, "mcp_world.png")
print(srv.render_image(png, 160, 120))

print("\n== animation: set_frame + insert_keyframe ==")
print(json.dumps(srv.create_primitive("cube", "AnimCube", [0, 0, 0], size=1.0), ensure_ascii=False))
print("frame:", srv.set_frame(10))
print(srv.insert_keyframe("AnimCube", "location", value=[0, 2, 0], frame=20))
print(srv.insert_keyframe("AnimCube", "rotation_euler", value=[0, 0, 1.57], frame=40))
print("frame back:", srv.set_frame(1))

print("\n== parent ==")
print(json.dumps(srv.create_primitive("cube", "ChildCube", [3, 0, 0], size=0.5), ensure_ascii=False))
print(srv.set_parent("ChildCube", "AnimCube", keep_transform=True))

print("\n== collections ==")
print(srv.create_collection("MyCol"))
print(srv.move_to_collection(["ChildCube", "Target"], "MyCol"))

print("\n== modifiers: add + remove ==")
print(json.dumps(srv.add_modifier("AnimCube", "BEVEL", params={"width": 0.05}), ensure_ascii=False))
print(json.dumps(srv.add_modifier("AnimCube", "SOLIDIFY", params={"thickness": 0.05}), ensure_ascii=False))
print(srv.remove_modifier("AnimCube", "SOLIDIFY.AnimCube"))

print("\n== shade_smooth + set_origin ==")
print(srv.shade_smooth("AnimCube", smooth=True))
print(srv.set_origin("AnimCube", "ORIGIN_GEOMETRY"))

print("\n== create_text + assign_material ==")
print(json.dumps(srv.create_text("MCP", name="Txt", location=[-2, 0, 0], extrude=0.2), ensure_ascii=False))
print(srv.assign_material("Txt", "TextMat"))
print(srv.set_material_color("Txt", [0.9, 0.2, 0.2]))

print("\n== set_image_texture map_type ==")
png2 = os.path.join(TMP_WIN, "mcp_tex2.png")
print(srv.render_image(png2, 160, 120))
print(json.dumps(srv.set_image_texture("AnimCube", png2, map_type="base_color"), ensure_ascii=False))
print(json.dumps(srv.set_image_texture("AnimCube", png2, map_type="normal"), ensure_ascii=False))

print("\n== polyhaven search ==")
try:
    res = srv.search_polyhaven_assets("hdris", categories="skies", limit=3)
    print("hdris:", [r["id"] for r in res])
except Exception as e:
    print("SKIP search (no network?):", str(e)[:120])

print("\n== polyhaven download hdri ==")
try:
    print(json.dumps(srv.download_polyhaven_asset("aarfontein_dusk", "hdris", "1k", strength=0.8), ensure_ascii=False))
except Exception as e:
    print("SKIP hdri download:", str(e)[:200])

print("\n== polyhaven download texture ==")
try:
    print(json.dumps(srv.download_polyhaven_asset("blue_floor_tiles_01", "textures", "1k", object_name="AnimCube"), ensure_ascii=False))
except Exception as e:
    print("SKIP texture download:", str(e)[:200])

print("\n== polyhaven download model ==")
try:
    print(json.dumps(srv.download_polyhaven_asset("ArmChair_01", "models", "1k"), ensure_ascii=False))
except Exception as e:
    print("SKIP model download:", str(e)[:200])

print("\n== clear_scene ==")
print(srv.clear_scene())
info = srv.get_scene_info()
print("objects after clear:", [o["name"] for o in info["objects"]])

print("\nALL V3 TOOL TESTS DONE")
