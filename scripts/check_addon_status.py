from agentic_blender.bridge.client import BlenderBridgeClient

client = BlenderBridgeClient()
code = """
import bpy
import addon_utils

installed = [a.__name__ for a in addon_utils.modules()]
enabled = list(bpy.context.preferences.addons.keys())
print("INSTALLED_AGENTIC:", "agentic_blender" in installed)
print("ENABLED_AGENTIC:", "agentic_blender" in enabled)
print("ENABLED_ADDONS:", enabled)

if "agentic_blender" not in enabled:
    try:
        addon_utils.enable("agentic_blender", default_set=True)
        bpy.ops.wm.save_userpref()
        print("ACTION: Successfully enabled agentic_blender and saved user preferences.")
    except Exception as e:
        print("ACTION_ERROR:", str(e))
"""
res = client.execute_bpy(code)
print("Execute result:", res)
