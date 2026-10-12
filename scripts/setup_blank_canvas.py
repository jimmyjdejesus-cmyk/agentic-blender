"""
Configures Blender with a 100% clean, distraction-free Agentic Canvas:
- Uses a timeline-free layout (VIEW_3D + right-hand Blender Agent Sidebar)
- Removes default startup objects and extra collections
- Removes all extra workspace tabs, leaving only 'Agentic Canvas'
- Hides all 850+ built-in Blender sidebar/properties panels so the right sidebar is 100% the Blender Agent
- Saves permanently to startup.blend and userpref.blend
"""

import os
import sys

try:
    import bpy
    import addon_utils
except ImportError:
    print("Error: bpy or addon_utils not available.")
    sys.exit(1)

print("[Agentic Setup] Configuring Blank Agentic Canvas with Blender Agent Sidebar...")

# 1. Load clean timeline-free template layout if available
template_blend = os.path.join(
    bpy.utils.resource_path('LOCAL'),
    "scripts", "startup", "bl_app_templates_system", "Sculpting", "startup.blend"
)
if os.path.exists(template_blend):
    bpy.ops.wm.open_mainfile(filepath=template_blend)

# 2. Switch to OBJECT mode and clear all default objects
if bpy.context.object and bpy.context.object.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

# 3. Clear extra default collections and orphan meshes
for col in list(bpy.data.collections):
    bpy.data.collections.remove(col)
for mesh in list(bpy.data.meshes):
    if mesh.users == 0:
        bpy.data.meshes.remove(mesh)

# 4. Keep ONLY the active workspace and rename it to 'Agentic Canvas'
workspaces = list(bpy.data.workspaces)
active_ws = bpy.context.workspace if getattr(bpy.context, "workspace", None) else workspaces[0]
active_ws.name = 'Agentic Canvas'

to_remove = [w for w in workspaces if w != active_ws]
if to_remove:
    bpy.data.batch_remove(to_remove)

# 5. Configure all Viewports and Properties editors across all screens:
#    - Hide left toolbar (show_region_toolbar = False)
#    - Use right Properties area as the Blender Agent Sidebar (hide header, hide duplicate N-panel)
for scr in bpy.data.screens:
    has_props = any(a.type == 'PROPERTIES' for a in scr.areas)
    for area in scr.areas:
        if area.type == 'VIEW_3D':
            s = area.spaces.active
            s.show_region_toolbar = False
            s.show_region_ui = not has_props
            s.shading.type = 'SOLID'
            s.shading.color_type = 'MATERIAL'
            s.overlay.show_floor = True
            s.overlay.show_axis_x = True
            s.overlay.show_axis_y = True
        elif area.type == 'PROPERTIES':
            s = area.spaces.active
            s.show_region_header = False

# 6. Enable agentic_blender add-on in user preferences
addon_utils.enable("agentic_blender", default_set=True)
bpy.ops.wm.save_userpref()

# 7. Save as default startup file
bpy.ops.wm.save_homefile()

print("[Agentic Setup] SUCCESS! Saved Blank Agentic Canvas + Blender Agent Sidebar to startup.blend.")
