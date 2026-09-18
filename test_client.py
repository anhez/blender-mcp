import os
import sys
import json

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import server as srv

print("== tools ==")
print([t.name for t in srv.mcp._tool_manager.list_tools()])

print("== ping ==")
print(json.dumps(srv.ping(), ensure_ascii=False))

print("== scene info ==")
info = srv.get_scene_info()
print(json.dumps(info, ensure_ascii=False))

print("== create cube ==")
print(json.dumps(srv.create_primitive("cube", "MyCube", [1, 0, 0], size=1.0), ensure_ascii=False))

print("== set material ==")
print(srv.set_material_color("MyCube", [1.0, 0.2, 0.2], metallic=0.3, roughness=0.4))

print("== object info ==")
print(json.dumps(srv.get_object_info("MyCube"), ensure_ascii=False))

print("== raw code ==")
print(repr(srv.execute_blender_code("print('hello from blender', bpy.app.version_string)")))

print("== error path ==")
try:
    srv.execute_blender_code("D.objects['DoesNotExist'].name")
except RuntimeError as e:
    print("RuntimeError caught (OK):", str(e).splitlines()[-1])

print("== delete ==")
print(srv.delete_object("MyCube"))
print(json.dumps(srv.get_scene_info()["objects"], ensure_ascii=False))

print("ALL TESTS PASSED")
