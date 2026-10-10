"""
Configures Blender with a 100% clean, blank, distraction-free Agentic Canvas:
- Removes default startup cube, lamp, and camera
- Removes all 10 cluttered workspace tabs, leaving only 'Agentic Canvas'
- Hides toolbar and sidebars
- Enables the Agentic Prompt Command Bar in the top header
- Saves permanently to startup.blend
"""

import sys

try:
    import bpy
    import addon_utils
except ImportError:
    print("Error: bpy or addon_utils not available.")
    sys.exit(1)

print("[Agentic Setup] Configuring Blank Agentic Canvas...")

# 1. Clear default objects
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

# 2. Clear extra default collections
for col in list(bpy.data.collections):
    bpy.data.collections.remove(col)

# 3. Consolidate workspaces to ONLY 'Agentic Canvas'
workspaces = list(bpy.data.workspaces)
layout_ws = next((w for w in workspaces if w.name in ['Layout', 'Agentic Canvas']), workspaces[0])
layout_ws.name = 'Agentic Canvas'

to_remove = [w for w in workspaces if w != layout_ws]
if to_remove:
    bpy.data.batch_remove(to_remove)

# 4. Viewport configuration: clean canvas, no toolbar/sidebar clutter
for area in layout_ws.screens[0].areas:
    if area.type == 'VIEW_3D':
        s = area.spaces.active
        s.show_region_toolbar = False
        s.show_region_ui = False
        s.shading.type = 'SOLID'
        s.shading.color_type = 'MATERIAL'

# 5. Enable agentic_blender add-on in user preferences
addon_utils.enable("agentic_blender", default_set=True)
bpy.ops.wm.save_userpref()

# 6. Save as default startup file
bpy.ops.wm.save_homefile()

print("[Agentic Setup] SUCCESS! Saved Blank Agentic Canvas to startup.blend.")
