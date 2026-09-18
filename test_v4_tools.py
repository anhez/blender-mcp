import asyncio
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import server as srv

HERE = os.path.dirname(os.path.abspath(__file__))
SHOT = os.path.join(os.path.dirname(HERE), "mcp_shot_v4.png")

print("== ping versions ==")
print(srv.ping())

print("== friendly error (object khong ton tai) ==")
try:
    srv.delete_object("Object_Khong_Ton_Tai_XYZ")
except Exception as e:
    print("OK friendly:", str(e)[:120])

print("== clear + create ==")
print(srv.clear_scene(keep_camera=True))
print(srv.create_primitive("cube", name="CubeA", location=(0, 0, 0), size=2.0))
print(srv.create_primitive("uv_sphere", name="SphereB", location=(0, 0, 0), size=1.2))

print("== boolean ==")
print(srv.boolean_objects("CubeA", "SphereB", "DIFFERENCE"))
print(srv.get_object_info("CubeA"))

print("== apply_transform ==")
print(srv.set_transform("CubeA", location=(3.0, 2.0, 0.0), rotation_euler=(0.5, 0.0, 0.0), scale=(2.0, 1.0, 1.0)))
print(srv.apply_transform("CubeA"))
info = srv.get_object_info("CubeA")
print("after apply:", info["location"], info["rotation_euler"], info["scale"])

print("== visibility ==")
print(srv.set_visibility("CubeA", False, render_visible=True))
info = srv.get_object_info("CubeA")
print("visible now:", info["visible"])
print(srv.set_visibility("CubeA", True))

print("== world color ==")
print(srv.set_world_color(color=(0.1, 0.2, 0.3), strength=1.5))

print("== frame range ==")
print(srv.set_frame_range(1, 10))

print("== extrude ==")
print(srv.create_primitive("plane", name="PlaneE", size=2.0))
print(srv.extrude("PlaneE", 0.5, "Z"))
info = srv.get_object_info("PlaneE")
print("dimensions:", info["dimensions"])

print("== render animation ==")
srv.set_frame(1)
print(srv.set_transform("PlaneE", location=(0.0, 0.0, 0.0)))
print(srv.insert_keyframe("PlaneE", "location", [0, 0, 0], 1))
print(srv.insert_keyframe("PlaneE", "location", [5, 0, 0], 4))
cam = srv.add_camera(name="V4Cam", location=(5, -10, 6))
srv.camera_look_at("V4Cam", "PlaneE")
srv.set_active_camera("V4Cam")
anim_dir = os.path.join(HERE, "render_v4")
os.makedirs(anim_dir, exist_ok=True)
pat = os.path.join(anim_dir, "frame_###.png").replace("\\", "/")
print(srv.render_animation(pat, start=1, end=3))
frames = sorted(f for f in os.listdir(anim_dir) if f.endswith(".png"))
print("frames rendered:", frames)

print("== asset cache (download 2 lan) ==")
r1 = srv.download_polyhaven_asset("blue_floor_tiles_01", "textures", "1k", object_name="PlaneE")
r2 = srv.download_polyhaven_asset("blue_floor_tiles_01", "textures", "1k", object_name="PlaneE")
print("same file:", r1["file"] == r2["file"])


async def check_resources():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(
        command=sys.executable,
        args=[os.path.join(HERE, "server.py")],
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            res = await session.list_resources()
            uris = sorted(str(r.uri) for r in res.resources)
            print("RESOURCES:", uris)
            scene = await session.read_resource("blender://scene")
            scene_data = json.loads(scene.contents[0].text)
            print("scene resource:", scene_data["scene"], "objects:", len(scene_data["objects"]))
            obj = await session.read_resource("blender://objects/CubeA")
            print("object resource:", json.loads(obj.contents[0].text)["name"])


print("== mcp resources ==")
asyncio.run(check_resources())

print("== clear ==")
print(srv.clear_scene(keep_camera=False))
print("ALL V4 TOOL TESTS DONE")
