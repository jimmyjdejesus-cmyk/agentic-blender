"""
Configures Blender with a 100% clean, distraction-free "Google Stitch for Blender" Agentic Canvas:
- Configures VIEW_3D with right-hand Blender Agent Sidebar (show_region_ui = True, show_region_toolbar = False)
- Closes Outliner, Properties, and Timeline areas so ONLY the 3D Viewport + Agent Sidebar remain
- Removes default startup objects and extra collections
- Removes all extra workspace tabs, leaving only 'Agentic Canvas'
- Installs the 'Agentic_Stitch' Blender Application Template in bl_app_templates_user
- Saves permanently to startup.blend and userpref.blend
"""

import os
import shutil
import sys

try:
    import bpy
    import addon_utils
except ImportError:
    print("Error: bpy or addon_utils not available.")
    sys.exit(1)

print("[Agentic Setup] Configuring Stitch-style Blank Agentic Canvas...")

# 1. In background mode, load clean timeline-free template layout if needed
template_blend = os.path.join(
    bpy.utils.resource_path('LOCAL'),
    "scripts", "startup", "bl_app_templates_system", "Sculpting", "startup.blend"
)
if bpy.app.background and os.path.exists(template_blend):
    bpy.ops.wm.open_mainfile(filepath=template_blend)

# 2. Clear all default objects directly via bpy.data.objects
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

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

# 5. Configure VIEW_3D BEFORE closing other areas (prevents ED_region_visibility_change_update crash)
windows = list(bpy.context.window_manager.windows) if bpy.context.window_manager else []
active_screens = [w.screen for w in windows if getattr(w, "screen", None)]
if not active_screens and getattr(bpy.context, "screen", None):
    active_screens = [bpy.context.screen]

for scr in active_screens:
    for area in scr.areas:
        if area.type == 'VIEW_3D':
            s = area.spaces.active
            s.show_region_toolbar = False
            s.show_region_ui = True
            s.shading.type = 'SOLID'
            s.shading.color_type = 'MATERIAL'
            s.overlay.show_floor = True
            s.overlay.show_axis_x = True
            s.overlay.show_axis_y = True

# 6. If running with a window context, close Outliner & Properties areas so ONLY VIEW_3D remains
if windows and windows[0] is not None:
    win = windows[0]
    scr = win.screen
    for area in list(scr.areas):
        if area.type != 'VIEW_3D':
            try:
                with bpy.context.temp_override(window=win, screen=scr, area=area):
                    bpy.ops.screen.area_close()
            except Exception as e:
                print(f"[Agentic Setup] Area close note ({area.type}): {e}")

# 7. Enable agentic_blender add-on in user preferences
addon_utils.enable("agentic_blender", default_set=True)
bpy.ops.wm.save_userpref()

# 8. Save as default startup file
bpy.ops.wm.save_homefile()

# 9. Also install as a native Blender Application Template ('Agentic_Stitch')
try:
    user_path = bpy.utils.resource_path('USER')
    startup_src = os.path.join(user_path, "config", "startup.blend")
    userpref_src = os.path.join(user_path, "config", "userpref.blend")
    app_template_dir = os.path.join(user_path, "scripts", "startup", "bl_app_templates_user", "Agentic_Stitch")
    os.makedirs(app_template_dir, exist_ok=True)
    if os.path.exists(startup_src):
        shutil.copy2(startup_src, os.path.join(app_template_dir, "startup.blend"))
    if os.path.exists(userpref_src):
        shutil.copy2(userpref_src, os.path.join(app_template_dir, "userpref.blend"))
    template_init = os.path.join(app_template_dir, "__init__.py")
    with open(template_init, "w", encoding="utf-8") as f:
        f.write(
            'import bpy\n'
            'from bpy.app.handlers import persistent\n\n'
            '@persistent\n'
            'def _on_load(dummy):\n'
            '    try:\n'
            '        import addon_utils\n'
            '        addon_utils.enable("agentic_blender", default_set=True)\n'
            '    except Exception:\n'
            '        pass\n\n'
            'def register():\n'
            '    if _on_load not in bpy.app.handlers.load_post:\n'
            '        bpy.app.handlers.load_post.append(_on_load)\n\n'
            'def unregister():\n'
            '    if _on_load in bpy.app.handlers.load_post:\n'
            '        bpy.app.handlers.load_post.remove(_on_load)\n'
        )
    print(f"[Agentic Setup] Installed 'Agentic_Stitch' App Template at: {app_template_dir}")
except Exception as e:
    print(f"[Agentic Setup] Template install note: {e}")

print("[Agentic Setup] SUCCESS! Areas:", [(a.type, a.width, a.height) for a in active_screens[0].areas] if active_screens else [])
sys.stdout.flush()
if not bpy.app.background:
    os._exit(0)
