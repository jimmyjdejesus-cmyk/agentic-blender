bl_info = {
    "name": "Agentic Blender AI",
    "author": "Antigravity Agent",
    "version": (2, 5, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Agentic AI (or Shift+Alt+A)",
    "description": "Prompt-driven 3D CAD, 3D printing validation, and Langmuir CNC manufacturing",
    "category": "3D View",
}

import bpy
import bmesh
import json
import threading
import queue
import time
import io
import re
import os
import math
import traceback
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

# ----------------- Configuration & Global State -----------------

BRIDGE_PORT = 9876
TASK_QUEUE = queue.Queue()
SERVER_INSTANCE = None
SERVER_THREAD = None
IS_SERVER_RUNNING = False
RECENT_LOGS = []

def add_log(msg):
    global RECENT_LOGS
    timestamp = time.strftime("%H:%M:%S")
    RECENT_LOGS.append(f"[{timestamp}] {msg}")
    if len(RECENT_LOGS) > 25:
        RECENT_LOGS.pop(0)

# ----------------- Addon Preferences -----------------

class AgenticAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    gemini_api_key: bpy.props.StringProperty(
        name="Gemini API Key",
        description="Google Gemini API key for in-Blender prompt generation (get free at aistudio.google.com)",
        subtype='PASSWORD',
        default=""
    )
    custom_endpoint_url: bpy.props.StringProperty(
        name="Local / Custom API URL",
        description="URL for Ollama, LM Studio, or OpenAI-compatible server",
        default="http://localhost:11434/v1/chat/completions"
    )
    local_model_name: bpy.props.StringProperty(
        name="Local Model Name",
        description="Model identifier for local Ollama / LM Studio (e.g., llama3.2, mistral)",
        default="llama3.2"
    )

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.label(text="AI Engine Settings:", icon='PREFERENCES')
        col.prop(self, "gemini_api_key")
        col.label(text="Get a free Gemini API key at: https://aistudio.google.com/apikey", icon='HELP')
        col.separator()
        col.label(text="Local / Offline LLM (Ollama or LM Studio):", icon='CONSOLE')
        col.prop(self, "custom_endpoint_url")
        col.prop(self, "local_model_name")

# ----------------- Scene Property Group -----------------

class AgenticSceneSettings(bpy.types.PropertyGroup):
    # Prompt settings
    prompt: bpy.props.StringProperty(
        name="Prompt",
        description="Describe what you want to create or modify in 3D",
        default="Create a modular canister with a twist-lock lid and filter base"
    )
    engine: bpy.props.EnumProperty(
        name="Engine",
        description="AI generation engine to use",
        items=[
            ('GEMINI', "Gemini AI (Cloud)", "Use Google Gemini API for high-level creative prompts", 'WORLD', 0),
            ('LOCAL_LLM', "Local LLM (Ollama/LM Studio)", "Use local Ollama or OpenAI compatible server", 'CONSOLE', 1),
            ('CAD_ENGINE', "Built-in CAD Engine (Instant)", "Offline parametric CAD generator without any API key", 'TOOL_SETTINGS', 2),
        ],
        default='CAD_ENGINE'
    )
    show_code: bpy.props.BoolProperty(
        name="Show Code",
        description="Show generated Python script",
        default=False
    )
    last_code: bpy.props.StringProperty(
        name="Last Code",
        default=""
    )
    status_msg: bpy.props.StringProperty(
        name="Status",
        default="Ready for prompt"
    )

    # Parametric CAD Controls
    shape: bpy.props.EnumProperty(
        name="Base Shape",
        items=[
            ('cylinder', "Cylinder", "Circular cylinder"),
            ('hexagon', "Hexagon", "Hexagonal prism"),
            ('rectangle', "Rectangle", "Square/rectangular base"),
        ],
        default='cylinder'
    )
    radius: bpy.props.FloatProperty(name="Radius", default=1.8, min=0.5, max=10.0)
    height: bpy.props.FloatProperty(name="Height", default=4.0, min=1.0, max=20.0)
    wall_thickness: bpy.props.FloatProperty(name="Wall", default=0.25, min=0.05, max=1.0)
    include_filter: bpy.props.BoolProperty(name="Dry Filter Base", default=True)
    include_holders: bpy.props.BoolProperty(name="Dosing Wells", default=True)
    include_lid: bpy.props.BoolProperty(name="Knurled Lid", default=True)

    # 3D Printing & Manufacturing Controls
    printer_profile: bpy.props.EnumProperty(
        name="3D Printer",
        items=[
            ('bambu_x1c', "Bambu Lab X1C (256mm)", "Bambu Lab X1/P1/A1"),
            ('prusa_mk4', "Prusa MK4 (250x210x220)", "Original Prusa MK4"),
            ('ender_3', "Ender 3 (220x220x250)", "Creality Ender 3"),
        ],
        default='bambu_x1c'
    )
    print_material: bpy.props.EnumProperty(
        name="Filament",
        items=[
            ('pla', "PLA (1.24 g/cm³)", "Polylactic Acid"),
            ('petg', "PETG (1.27 g/cm³)", "Polyethylene Terephthalate"),
            ('abs', "ABS (1.04 g/cm³)", "Acrylonitrile Butadiene Styrene"),
            ('resin', "Resin (1.15 g/cm³)", "Photopolymer Resin"),
        ],
        default='pla'
    )
    cnc_material: bpy.props.EnumProperty(
        name="CNC Metal",
        items=[
            ('14_gauge_mild_steel', "14ga Mild Steel (150 IPM)", "Standard mild steel sheet"),
            ('16_gauge_mild_steel', "16ga Mild Steel (180 IPM)", "Thin sheet steel"),
            ('11_gauge_mild_steel', "11ga Mild Steel (110 IPM)", "Heavy sheet steel"),
            ('3_16_inch_mild_steel', "3/16\" Steel Plate (75 IPM)", "Plate steel"),
            ('1_4_inch_mild_steel', "1/4\" Steel Plate (48 IPM)", "Heavy plate steel"),
            ('1_8_inch_aluminum', "1/8\" Aluminum (130 IPM)", "Aluminum sheet"),
            ('14_gauge_stainless', "14ga Stainless (140 IPM)", "Stainless steel"),
        ],
        default='14_gauge_mild_steel'
    )
    report_text: bpy.props.StringProperty(
        name="Report",
        default="No check run yet"
    )

# ----------------- Prompt AI Callers -----------------

SYSTEM_PROMPT = """You are an expert Blender 3D CAD and Python (bpy) automation engineer.
Generate clean, robust Python code using `bpy` that precisely fulfills the user's request.

CRITICAL RULES:
1. Return ONLY pure executable Python code inside a ```python ``` markdown block. Do not provide conversational filler.
2. The code will execute directly inside Blender.
3. Handle dimensions accurately: default to meters/millimeters. Ensure geometry has correct scale and thickness.
4. When creating modular mechanical parts (canisters, lids, holders, filters):
   - Create separate objects for modular components (e.g. Canister_Body, Canister_Lid, Modular_Base, Filter_Grate).
   - Position components neatly side-by-side or stacked so they don't awkwardly overlap.
   - Add appropriate bevels/chamfers for manufacturing realism.
5. Apply appropriate materials using Principled BSDF shaders with pleasant colors (e.g., anodized aluminum, matte polymer, silicone).
6. Always ensure transforms are applied (bpy.ops.object.transform_apply) if modifiers rely on dimensions.
"""

def call_gemini_api(prompt, api_key):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": f"{SYSTEM_PROMPT}\n\nUser Prompt: {prompt}"}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 4096}
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30.0) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        candidates = data.get("candidates", [])
        if not candidates:
            raise Exception("No response generated by Gemini API.")
        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            raise Exception("Empty content in Gemini response.")
        return parts[0].get("text", "")

def call_local_llm(prompt, endpoint_url, model_name):
    headers = {"Content-Type": "application/json"}
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2
    }
    req = urllib.request.Request(endpoint_url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=45.0) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        choices = data.get("choices", [])
        if not choices:
            raise Exception("No response from local LLM.")
        return choices[0].get("message", {}).get("content", "")

def extract_python_code(response_text):
    pattern = r"```(?:python)?\s*\n(.*?)```"
    matches = re.findall(pattern, response_text, re.DOTALL)
    if matches:
        return matches[0].strip()
    return response_text.strip()

# ----------------- Built-in Parametric CAD Engine -----------------

def run_builtin_cad_engine(prompt, settings=None):
    p = prompt.lower()
    
    # Check if settings provided
    radius = settings.radius if settings else 1.8
    height = settings.height if settings else 4.0
    wall = settings.wall_thickness if settings else 0.25
    shape = settings.shape if settings else "cylinder"
    
    v = 32
    if shape == "hexagon" or "hex" in p:
        v = 6
    elif shape == "rectangle" or "rect" in p or "square" in p:
        v = 4

    lines = [
        "import bpy, bmesh, math",
        "if bpy.context.object and bpy.context.object.mode != 'OBJECT':",
        "    bpy.ops.object.mode_set(mode='OBJECT')",
        "bpy.ops.object.select_all(action='SELECT')",
        "bpy.ops.object.delete(use_global=False)",
        """
def make_mat(name, color, roughness=0.3, metallic=0.0):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    if bsdf:
        bsdf.inputs['Base Color'].default_value = color
        bsdf.inputs['Roughness'].default_value = roughness
        bsdf.inputs['Metallic'].default_value = metallic
    return mat
mat_metal = make_mat('Anodized_Mat', (0.1, 0.45, 0.85, 1.0), roughness=0.25, metallic=0.85)
mat_lid = make_mat('Grip_Polymer', (0.15, 0.15, 0.18, 1.0), roughness=0.4, metallic=0.1)
mat_filter = make_mat('Filter_Mesh', (0.7, 0.7, 0.75, 1.0), roughness=0.3, metallic=0.9)
"""
    ]

    if any(k in p for k in ["powder", "dispenser", "canister", "holder", "filter", "modular"]):
        lines.append(f"""
# 1. Main Reservoir Body (Canister)
bpy.ops.mesh.primitive_cylinder_add(vertices={v}, radius={radius}, depth={height}, location=(0, 0, {height / 2.0}))
body = bpy.context.active_object
body.name = "Dispenser_Main_Body"
body.data.materials.append(mat_metal)

# Hollow out the interior
bpy.ops.mesh.primitive_cylinder_add(vertices={v}, radius={max(0.1, radius - wall)}, depth={max(0.1, height - wall)}, location=(0, 0, {(height / 2.0) + (wall / 2.0)}))
core = bpy.context.active_object
core.name = "Interior_Cavity"
bool_mod = body.modifiers.new(name="CavityBool", type='BOOLEAN')
bool_mod.object = core
bool_mod.operation = 'DIFFERENCE'
bpy.context.view_layer.objects.active = body
bpy.ops.object.modifier_apply(modifier="CavityBool")
bpy.data.objects.remove(core, do_unlink=True)

# 2. Dry Filter & Humidity Barrier Base (Perforated Desiccant Chamber)
bpy.ops.mesh.primitive_cylinder_add(vertices={v}, radius={radius}, depth=0.8, location=({radius * 2.5}, 0, 0.4))
filter_base = bpy.context.active_object
filter_base.name = "Dry_Filter_Chamber"
filter_base.data.materials.append(mat_filter)

# Perforations in the filter base
for i in range(8):
    angle = i * (2 * math.pi / 8)
    hx = {radius * 2.5} + ({radius * 0.55}) * math.cos(angle)
    hy = ({radius * 0.55}) * math.sin(angle)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.12, depth=1.0, location=(hx, hy, 0.4))
    hole = bpy.context.active_object
    hbool = filter_base.modifiers.new(name=f"Hole_{{i}}", type='BOOLEAN')
    hbool.object = hole
    hbool.operation = 'DIFFERENCE'
    bpy.context.view_layer.objects.active = filter_base
    bpy.ops.object.modifier_apply(modifier=f"Hole_{{i}}")
    bpy.data.objects.remove(hole, do_unlink=True)

# 3. Precision Dosing Holder (0.1g standard & micro well)
bpy.ops.mesh.primitive_cylinder_add(radius=1.2, depth=1.0, location=({-radius * 2.5}, -1.8, 0.5))
holder_std = bpy.context.active_object
holder_std.name = "Dosing_Holder_Standard_0.1g"
holder_std.data.materials.append(mat_metal)
bpy.ops.mesh.primitive_cylinder_add(radius=0.5, depth=0.6, location=({-radius * 2.5}, -1.8, 0.8))
well1 = bpy.context.active_object
wbool = holder_std.modifiers.new(name="WellBool", type='BOOLEAN')
wbool.object = well1
wbool.operation = 'DIFFERENCE'
bpy.context.view_layer.objects.active = holder_std
bpy.ops.object.modifier_apply(modifier="WellBool")
bpy.data.objects.remove(well1, do_unlink=True)

# 4. Knurled Screw-On Air-Tight Cap
bpy.ops.mesh.primitive_cylinder_add(radius={radius * 1.06}, depth=0.7, location=(0, {radius * 2.5}, 0.35))
cap = bpy.context.active_object
cap.name = "Modular_Airtight_Lid"
cap.data.materials.append(mat_lid)

# Knurling ridges
for i in range(24):
    angle = i * (2 * math.pi / 24)
    rx = {radius * 1.06} * math.cos(angle)
    ry = {radius * 2.5} + {radius * 1.06} * math.sin(angle)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.06, depth=0.7, location=(rx, ry, 0.35))
    ridge = bpy.context.active_object
    ridge.data.materials.append(mat_lid)

bpy.ops.object.camera_add(location=(10.0, -10.0, 8.0), rotation=(math.radians(60), 0, math.radians(45)))
bpy.context.scene.camera = bpy.context.active_object
bpy.ops.object.light_add(type='SUN', location=(5, -5, 10))
bpy.context.active_object.data.energy = 4.0
print("[CAD Engine] Built modular canister assembly.")
""")
    elif any(k in p for k in ["bracket", "mount", "langmuir", "cnc", "plate"]):
        lines.append("""
# Langmuir CNC Base Mounting Plate
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0.0625))
bracket = bpy.context.active_object
bracket.name = "Langmuir_CNC_Mounting_Plate"
bracket.scale = (6.0, 3.5, 0.125)
bpy.ops.object.transform_apply(scale=True)
bracket.data.materials.append(mat_metal)

# 4 Corner Bolt Holes
for pos in [(-2.5, -1.3), (2.5, -1.3), (-2.5, 1.3), (2.5, 1.3)]:
    bpy.ops.mesh.primitive_cylinder_add(radius=0.1875, depth=0.5, location=(pos[0], pos[1], 0))
    hole = bpy.context.active_object
    hmod = bracket.modifiers.new(name="BoltHole", type='BOOLEAN')
    hmod.object = hole
    hmod.operation = 'DIFFERENCE'
    bpy.context.view_layer.objects.active = bracket
    bpy.ops.object.modifier_apply(modifier="BoltHole")
    bpy.data.objects.remove(hole, do_unlink=True)

bev = bracket.modifiers.new(name="PlateBevel", type='BEVEL')
bev.width = 0.05
bev.segments = 3
bpy.ops.object.modifier_apply(modifier="PlateBevel")

bpy.ops.object.camera_add(location=(0, -8, 7), rotation=(math.radians(50), 0, 0))
bpy.context.scene.camera = bpy.context.active_object
bpy.ops.object.light_add(type='SUN', location=(2, -3, 8))
print("[CAD Engine] Built Langmuir CNC mounting bracket.")
""")
    else:
        lines.append(f"""
# Generic Parametric Generator for: {prompt}
bpy.ops.mesh.primitive_cylinder_add(radius=2.0, depth=3.0, location=(0, 0, 1.5))
obj = bpy.context.active_object
obj.name = "Generated_Part"
obj.data.materials.append(mat_metal)

bev = obj.modifiers.new(name="Bevel", type='BEVEL')
bev.width = 0.1
bev.segments = 3
bpy.ops.object.modifier_apply(modifier="Bevel")

bpy.ops.object.camera_add(location=(6, -6, 5), rotation=(math.radians(55), 0, math.radians(45)))
bpy.context.scene.camera = bpy.context.active_object
bpy.ops.object.light_add(type='SUN', location=(3, -3, 6))
print("[CAD Engine] Created parametric model.")
""")

    return "\n".join(lines)

# ----------------- Interactive Manufacturing Operators -----------------

class AGENTIC_OT_ExecutePrompt(bpy.types.Operator):
    bl_idname = "agentic.execute_prompt"
    bl_label = "Generate / Execute Prompt"
    bl_description = "Send prompt to AI and build the 3D model in Blender"

    def execute(self, context):
        settings = context.scene.agentic_settings
        prompt = settings.prompt.strip()

        if not prompt:
            self.report({'WARNING'}, "Please enter a prompt first.")
            return {'CANCELLED'}

        settings.status_msg = "Generating 3D model..."
        if hasattr(context, "area") and context.area:
            context.area.tag_redraw()

        try:
            try:
                bpy.ops.ed.undo_push(message=f"Agentic Prompt: {prompt[:30]}")
            except Exception:
                pass

            code = ""
            if settings.engine == 'GEMINI':
                prefs = context.preferences.addons[__name__].preferences
                api_key = prefs.gemini_api_key.strip() or os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")
                if not api_key:
                    self.report({'ERROR'}, "Please enter your Gemini API Key in preferences.")
                    settings.status_msg = "Error: Missing Gemini API Key."
                    return {'CANCELLED'}
                raw_resp = call_gemini_api(prompt, api_key)
                code = extract_python_code(raw_resp)

            elif settings.engine == 'LOCAL_LLM':
                prefs = context.preferences.addons[__name__].preferences
                raw_resp = call_local_llm(prompt, prefs.custom_endpoint_url, prefs.local_model_name)
                code = extract_python_code(raw_resp)

            elif settings.engine == 'CAD_ENGINE':
                code = run_builtin_cad_engine(prompt, settings)

            settings.last_code = code

            scope = {"bpy": bpy, "C": bpy.context, "D": bpy.data}
            exec(code, scope)

            settings.status_msg = "Success! 3D model generated."
            add_log(f"Prompt executed: '{prompt[:35]}...'")
            self.report({'INFO'}, "Model successfully created!")
            return {'FINISHED'}

        except Exception as e:
            err = str(e)
            settings.status_msg = f"Error: {err}"
            add_log(f"Execution Error: {err}")
            self.report({'ERROR'}, f"Agentic Error: {err}")
            return {'CANCELLED'}

class AGENTIC_OT_Check3DPrint(bpy.types.Operator):
    bl_idname = "agentic.check_3dprint"
    bl_label = "3D Print Pre-Flight Check"
    bl_description = "Check watertight manifold, calculate volume and mass"

    def execute(self, context):
        settings = context.scene.agentic_settings
        target = context.active_object
        if not target or target.type != 'MESH':
            self.report({'WARNING'}, "Please select a Mesh object first.")
            return {'CANCELLED'}

        bm = bmesh.new()
        bm.from_mesh(target.data)
        non_manifold = sum(1 for e in bm.edges if not e.is_manifold)
        vol = abs(bm.calc_volume()) * 1000.0  # cm3 approx if in meters
        dims = target.dimensions * 1000.0 # mm

        densities = {'pla': 1.24, 'petg': 1.27, 'abs': 1.04, 'resin': 1.15}
        density = densities.get(settings.print_material, 1.24)
        mass_g = round(vol * density, 1)

        is_solid = (non_manifold == 0)
        report = (
            f"Solid: {'PASS (Watertight)' if is_solid else f'FAIL ({non_manifold} open edges)'} | "
            f"Dim: {dims.x:.1f}x{dims.y:.1f}x{dims.z:.1f}mm | "
            f"Vol: {vol:.1f}cm³ | Mass: ~{mass_g}g ({settings.print_material.upper()})"
        )
        settings.report_text = report
        bm.free()

        if is_solid:
            self.report({'INFO'}, f"Watertight! Estimated Mass: {mass_g}g")
        else:
            self.report({'WARNING'}, f"Non-manifold: {non_manifold} open edges detected.")
        return {'FINISHED'}

class AGENTIC_OT_Export3DPrint(bpy.types.Operator):
    bl_idname = "agentic.export_3dprint"
    bl_label = "Export STL / 3MF"
    bl_description = "Export active object for 3D printing"

    def execute(self, context):
        target = context.active_object
        if not target or target.type != 'MESH':
            self.report({'WARNING'}, "Please select a Mesh object first.")
            return {'CANCELLED'}

        export_dir = os.path.join(os.path.expanduser("~"), ".gemini", "antigravity", "scratch", "langmuir-cnc", "exports")
        os.makedirs(export_dir, exist_ok=True)
        out_stl = os.path.join(export_dir, f"{target.name}.stl")

        # Select target only
        bpy.ops.object.select_all(action='DESELECT')
        target.select_set(True)

        if hasattr(bpy.ops.wm, "stl_export"):
            bpy.ops.wm.stl_export(filepath=out_stl, export_selected_objects=True)
        else:
            bpy.ops.export_mesh.stl(filepath=out_stl, use_selection=True)

        context.scene.agentic_settings.report_text = f"Exported: {os.path.basename(out_stl)}"
        self.report({'INFO'}, f"Saved STL to: {out_stl}")
        return {'FINISHED'}

class AGENTIC_OT_ExportCNC(bpy.types.Operator):
    bl_idname = "agentic.export_cnc"
    bl_label = "Export FireControl G-Code"
    bl_description = "Extract 2D contour and format Langmuir FireControl G-code"

    def execute(self, context):
        target = context.active_object
        if not target or target.type != 'MESH':
            self.report({'WARNING'}, "Please select a Mesh object first.")
            return {'CANCELLED'}

        gcode_dir = os.path.join(os.path.expanduser("~"), ".gemini", "antigravity", "scratch", "langmuir-cnc", "gcode")
        dxf_dir = os.path.join(os.path.expanduser("~"), ".gemini", "antigravity", "scratch", "langmuir-cnc", "dxf_svg")
        os.makedirs(gcode_dir, exist_ok=True)
        os.makedirs(dxf_dir, exist_ok=True)

        out_nc = os.path.join(gcode_dir, f"{target.name}.nc")
        out_dxf = os.path.join(dxf_dir, f"{target.name}.dxf")

        mat_name = context.scene.agentic_settings.cnc_material

        # Extract bottom planar face points
        bm = bmesh.new()
        bm.from_mesh(target.data)
        bmesh.ops.transform(bm, matrix=target.matrix_world)

        paths = []
        planar_faces = [f for f in bm.faces if abs(f.normal.z) > 0.8]
        if planar_faces:
            for face in planar_faces:
                if face.normal.z < 0:
                    pts = [(v.co.x, v.co.y) for v in face.verts]
                    if pts:
                        pts.append(pts[0])
                        paths.append(pts)
                    break
        if not paths:
            xs = [v.co.x for v in bm.verts]
            ys = [v.co.y for v in bm.verts]
            paths.append([(min(xs), min(ys)), (max(xs), min(ys)), (max(xs), max(ys)), (min(xs), max(ys)), (min(xs), min(ys))])
        bm.free()

        # Generate G-code with FireControl syntax
        feed = 150.0
        lines = [
            "( Langmuir Systems FireControl Export )",
            f"( Machine: CrossFire PRO | Material: {mat_name} )",
            "G90 G94",
            "G20",
            "G54",
            "G0 Z1.0000",
            ""
        ]
        for idx, path in enumerate(paths, 1):
            sx, sy = path[0]
            # Lead-in
            px, py = sx - 0.15, sy
            lines.append(f"( Profile {idx} )")
            lines.append(f"G0 X{px:.4f} Y{py:.4f}")
            lines.append("G38.2 Z-5.0000 F60.0 (IHS Touch)")
            lines.append("G92 Z0.0")
            lines.append("G0 Z0.0200")
            lines.append("G92 Z0.0")
            lines.append("G0 Z0.1500 (Pierce Height)")
            lines.append("M3 (Torch ON)")
            lines.append("G4 P0.60 (Pierce Delay)")
            lines.append("G1 Z0.0600 F60.0 (Cut Height)")
            lines.append("H1 (THC ON)")
            lines.append(f"G1 X{sx:.4f} Y{sy:.4f} F{feed:.1f} (Lead-in)")
            for pt in path[1:]:
                lines.append(f"G1 X{pt[0]:.4f} Y{pt[1]:.4f} F{feed:.1f}")
            lines.append("H0 (THC OFF)")
            lines.append("M5 (Torch OFF)")
            lines.append("G0 Z1.0000")
            lines.append("")
        lines.append("M30")

        with open(out_nc, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        # Minimal DXF export
        dxf_lines = ["0", "SECTION", "2", "ENTITIES"]
        for path in paths:
            for i in range(len(path) - 1):
                p1, p2 = path[i], path[i+1]
                dxf_lines.extend(["0", "LINE", "8", "0", "10", f"{p1[0]:.6f}", "20", f"{p1[1]:.6f}", "30", "0.0", "11", f"{p2[0]:.6f}", "21", f"{p2[1]:.6f}", "31", "0.0"])
        dxf_lines.extend(["0", "ENDSEC", "0", "EOF", ""])
        with open(out_dxf, "w", encoding="utf-8") as f:
            f.write("\n".join(dxf_lines))

        context.scene.agentic_settings.report_text = f"CNC Exported: {os.path.basename(out_nc)}"
        self.report({'INFO'}, f"Saved G-code: {out_nc}")
        return {'FINISHED'}

class AGENTIC_OT_PromptModal(bpy.types.Operator):
    bl_idname = "agentic.prompt_modal"
    bl_label = "Agentic 3D Prompt"
    bl_options = {'REGISTER', 'UNDO'}

    prompt: bpy.props.StringProperty(name="Prompt", default="")

    def invoke(self, context, event):
        if not self.prompt:
            self.prompt = context.scene.agentic_settings.prompt
        return context.window_manager.invoke_props_dialog(self, width=450)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Enter 3D Modeling Prompt:", icon='FORCE_BOID')
        layout.prop(self, "prompt", text="")
        layout.prop(context.scene.agentic_settings, "engine", text="Engine")

    def execute(self, context):
        context.scene.agentic_settings.prompt = self.prompt
        return bpy.ops.agentic.execute_prompt()

class AGENTIC_OT_SetQuickPrompt(bpy.types.Operator):
    bl_idname = "agentic.set_quick_prompt"
    bl_label = "Set Preset Prompt"
    preset_text: bpy.props.StringProperty()

    def execute(self, context):
        context.scene.agentic_settings.prompt = self.preset_text
        return bpy.ops.agentic.execute_prompt()

class AGENTIC_OT_ClearScene(bpy.types.Operator):
    bl_idname = "agentic.clear_scene"
    bl_label = "Clear Scene"

    def execute(self, context):
        if context.object and context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)
        context.scene.agentic_settings.status_msg = "Scene cleared."
        return {'FINISHED'}

# ----------------- 3D Viewport UI Panel -----------------

class AGENTIC_PT_MainPanel(bpy.types.Panel):
    bl_label = "Agentic AI & Manufacturing"
    bl_idname = "AGENTIC_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Agentic AI'

    def draw(self, context):
        layout = self.layout
        settings = context.scene.agentic_settings
        prefs = context.preferences.addons[__name__].preferences

        # 1. Main Prompt Section
        box1 = layout.box()
        box1.label(text="Prompt-to-3D:", icon='FORCE_BOID')
        box1.prop(settings, "prompt", text="")
        box1.prop(settings, "engine", text="Engine")

        if settings.engine == 'GEMINI' and not prefs.gemini_api_key.strip():
            alert_box = box1.box()
            alert_box.alert = True
            alert_box.label(text="Gemini Key Required:", icon='KEYINGSET')
            alert_box.prop(prefs, "gemini_api_key", text="API Key")

        row = box1.row(align=True)
        row.scale_y = 1.4
        row.operator("agentic.execute_prompt", text="✨ Generate 3D Model", icon='PLAY')

        # 2. Parametric Modular Assembly Builder
        box2 = layout.box()
        box2.label(text="Modular CAD Controls:", icon='TOOL_SETTINGS')
        box2.prop(settings, "shape", text="Shape")
        col = box2.column(align=True)
        col.prop(settings, "radius", text="Radius (in)")
        col.prop(settings, "height", text="Height (in)")
        col.prop(settings, "wall_thickness", text="Wall (in)")
        r2 = box2.row(align=True)
        r2.prop(settings, "include_filter", text="Filter")
        r2.prop(settings, "include_holders", text="Dosing")
        r2.prop(settings, "include_lid", text="Lid")

        # 3. Manufacturing Action Bar
        box3 = layout.box()
        box3.label(text="Manufacturing & Export:", icon='MODIFIER')
        
        # 3D Print row
        b_print = box3.box()
        b_print.label(text="3D Printing Pre-Flight:", icon='PRINTER')
        row_p = b_print.row(align=True)
        row_p.prop(settings, "printer_profile", text="")
        row_p.prop(settings, "print_material", text="")
        row_btn = b_print.row(align=True)
        row_btn.operator("agentic.check_3dprint", text="Check Manifold & Mass", icon='CHECKMARK')
        row_btn.operator("agentic.export_3dprint", text="Export STL", icon='EXPORT')

        # CNC row
        b_cnc = box3.box()
        b_cnc.label(text="Langmuir CNC Machining:", icon='GRID')
        b_cnc.prop(settings, "cnc_material", text="Material")
        b_cnc.operator("agentic.export_cnc", text="Export FireControl G-Code & DXF", icon='FILE_SCRIPT')

        # 4. Status / Report Display
        box4 = layout.box()
        box4.label(text=f"Status: {settings.status_msg}", icon='INFO')
        if settings.report_text:
            box4.label(text=settings.report_text, icon='FILE_TEXT')

        # 5. Quick Tools & Undo
        box5 = layout.box()
        r = box5.row(align=True)
        r.operator("ed.undo", text="Undo (Ctrl+Z)", icon='LOOP_BACK')
        r.operator("agentic.clear_scene", text="Clear Scene", icon='TRASH')

# ----------------- HTTP Bridge Server (for External Agents) -----------------

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

class AgentBridgeHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path == "/status":
            active_obj_name = None
            try:
                if hasattr(bpy.context, "active_object") and bpy.context.active_object:
                    active_obj_name = bpy.context.active_object.name
            except Exception:
                pass
            self.send_json({
                "status": "online",
                "blender_version": list(bpy.app.version),
                "objects_count": len(bpy.data.objects),
                "active_object": active_obj_name
            })
        elif self.path == "/scene":
            objs = []
            try:
                for obj in bpy.data.objects:
                    objs.append({
                        "name": obj.name,
                        "type": obj.type,
                        "location": [round(c, 4) for c in obj.location],
                        "dimensions": [round(c, 4) for c in obj.dimensions]
                    })
            except Exception:
                pass
            self.send_json({"objects": objs})
        else:
            self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)
        try:
            req = json.loads(post_data.decode("utf-8")) if post_data else {}
        except Exception as e:
            self.send_json({"error": str(e)}, 400)
            return

        if self.path == "/execute":
            code = req.get("code", "")
            res_box = {}
            evt = threading.Event()
            TASK_QUEUE.put({"action": "execute", "code": code, "event": evt, "result": res_box})
            evt.wait(timeout=30.0)
            self.send_json(res_box)
        elif self.path == "/clear":
            res_box = {}
            evt = threading.Event()
            TASK_QUEUE.put({"action": "clear", "event": evt, "result": res_box})
            evt.wait(timeout=5.0)
            self.send_json(res_box)
        else:
            self.send_json({"error": "Unknown endpoint"}, 404)

def process_tasks_timer():
    global TASK_QUEUE
    while not TASK_QUEUE.empty():
        try:
            task = TASK_QUEUE.get_nowait()
        except queue.Empty:
            break
        action = task.get("action")
        evt = task.get("event")
        res = task.get("result", {})
        try:
            if action == "execute":
                code = task.get("code")
                scope = {"bpy": bpy, "C": bpy.context, "D": bpy.data}
                exec(code, scope)
                res["success"] = True
            elif action == "clear":
                if bpy.context.object and bpy.context.object.mode != 'OBJECT':
                    bpy.ops.object.mode_set(mode='OBJECT')
                bpy.ops.object.select_all(action='SELECT')
                bpy.ops.object.delete(use_global=False)
                res["success"] = True
        except Exception as e:
            res["success"] = False
            res["error"] = str(e)
            res["traceback"] = traceback.format_exc()
        finally:
            if evt:
                evt.set()
    return 0.05

def start_bridge_server():
    global SERVER_INSTANCE, SERVER_THREAD, IS_SERVER_RUNNING
    if IS_SERVER_RUNNING:
        return
    try:
        SERVER_INSTANCE = ThreadedHTTPServer(("127.0.0.1", BRIDGE_PORT), AgentBridgeHandler)
        SERVER_THREAD = threading.Thread(target=SERVER_INSTANCE.serve_forever, daemon=True)
        SERVER_THREAD.start()
        IS_SERVER_RUNNING = True
    except Exception as e:
        print(f"[Agentic Blender] Server failed: {e}")

def stop_bridge_server():
    global SERVER_INSTANCE, IS_SERVER_RUNNING
    if not IS_SERVER_RUNNING:
        return
    try:
        if SERVER_INSTANCE:
            SERVER_INSTANCE.shutdown()
            SERVER_INSTANCE.server_close()
        IS_SERVER_RUNNING = False
    except Exception:
        pass

# ----------------- Registration -----------------

classes = (
    AgenticAddonPreferences,
    AgenticSceneSettings,
    AGENTIC_OT_ExecutePrompt,
    AGENTIC_OT_Check3DPrint,
    AGENTIC_OT_Export3DPrint,
    AGENTIC_OT_ExportCNC,
    AGENTIC_OT_PromptModal,
    AGENTIC_OT_SetQuickPrompt,
    AGENTIC_OT_ClearScene,
    AGENTIC_PT_MainPanel,
)

addon_keymaps = []

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.agentic_settings = bpy.props.PointerProperty(type=AgenticSceneSettings)

    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        kmi = km.keymap_items.new(AGENTIC_OT_PromptModal.bl_idname, 'A', 'PRESS', alt=True, shift=True)
        addon_keymaps.append((km, kmi))

    if not bpy.app.timers.is_registered(process_tasks_timer):
        bpy.app.timers.register(process_tasks_timer, persistent=True)
    start_bridge_server()

def unregister():
    stop_bridge_server()
    if bpy.app.timers.is_registered(process_tasks_timer):
        bpy.app.timers.unregister(process_tasks_timer)

    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        for km, kmi in addon_keymaps:
            km.keymap_items.remove(kmi)
    addon_keymaps.clear()

    del bpy.types.Scene.agentic_settings
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
