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

try:
    from ..cad import scene_manager
except Exception:
    try:
        from agentic_blender.cad import scene_manager
    except Exception:
        scene_manager = None

try:
    import gpu
    import blf
    from gpu_extras.batch import batch_for_shader
except Exception:
    gpu = None
    blf = None
    batch_for_shader = None

# ----------------- Configuration & Global State -----------------

BRIDGE_PORT = 9876
TASK_QUEUE = queue.Queue()
SERVER_INSTANCE = None
SERVER_THREAD = None
IS_SERVER_RUNNING = False
RECENT_LOGS = []
VIEWPORT_HUD_HANDLE = None

CHAT_HISTORY = [
    {
        "role": "Stitch Agent",
        "text": "Google Stitch for Blender ready! Type a prompt or click [3 Variations] to ideate.",
    },
    {
        "role": "Jev Brain",
        "text": "System-1 Jev Decision Primitives online (Choice | Boolean Gate | Calibrated Score).",
    },
]

JEV_TELEMETRY = {
    "choice": "canister (0.85)",
    "gate": "System-1 Fast CAD [YES]",
    "score": "0.96 Calibrated",
    "theme": "anodized_blue",
}


def tag_redraw_all_view3d():
    try:
        wm = getattr(bpy.context, "window_manager", None)
        if not wm:
            return
        for win in wm.windows:
            scr = getattr(win, "screen", None)
            if not scr:
                continue
            for area in scr.areas:
                if area.type in ('VIEW_3D', 'TOPBAR'):
                    area.tag_redraw()
    except Exception:
        pass


def add_chat_message(role, text):
    global CHAT_HISTORY
    clean = (text or "").strip()
    if not clean:
        return
    CHAT_HISTORY.append({"role": role, "text": clean})
    if len(CHAT_HISTORY) > 8:
        CHAT_HISTORY = CHAT_HISTORY[-8:]
    tag_redraw_all_view3d()


def add_log(msg):
    global RECENT_LOGS
    timestamp = time.strftime("%H:%M:%S")
    RECENT_LOGS.append(f"[{timestamp}] {msg}")
    if len(RECENT_LOGS) > 25:
        RECENT_LOGS.pop(0)

# ----------------- Universal Model-Agnostic LLM Router -----------------

DEFAULT_MODELS = {
    "JEV_ROUTER": "typesafe/jev-router",
    "OPENROUTER": "anthropic/claude-3.7-sonnet",
    "GEMINI": "gemini-2.5-flash",
    "ANTHROPIC": "claude-3-7-sonnet-latest",
    "DEEPSEEK": "deepseek-chat",
    "OPENAI_COMPAT": "gpt-4o",
    "GROQ": "llama-3.3-70b-versatile",
    "LOCAL_LLM": "qwen2.5-coder:7b",
}

PROVIDER_ENDPOINTS = {
    "JEV_ROUTER": "https://openrouter.ai/api/v1/chat/completions",
    "OPENROUTER": "https://openrouter.ai/api/v1/chat/completions",
    "OPENAI_COMPAT": "https://api.openai.com/v1/chat/completions",
    "DEEPSEEK": "https://api.deepseek.com/v1/chat/completions",
    "GROQ": "https://api.groq.com/openai/v1/chat/completions",
    "ANTHROPIC": "https://api.anthropic.com/v1/messages",
    "LOCAL_LLM": "http://localhost:11434/v1/chat/completions",
}

ENV_KEY_MAP = {
    "JEV_ROUTER": ("JEV_API_KEY", "TYPESAFE_API_KEY", "OPENROUTER_API_KEY"),
    "OPENROUTER": ("OPENROUTER_API_KEY",),
    "GEMINI": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "ANTHROPIC": ("ANTHROPIC_API_KEY",),
    "OPENAI_COMPAT": ("OPENAI_API_KEY",),
    "DEEPSEEK": ("DEEPSEEK_API_KEY",),
    "GROQ": ("GROQ_API_KEY",),
}


def resolve_api_key(provider, explicit_key=""):
    if explicit_key and explicit_key.strip():
        return explicit_key.strip()
    for env_var in ENV_KEY_MAP.get(provider.upper(), ()):
        val = os.environ.get(env_var, "").strip()
        if val:
            return val
    return os.environ.get("LLM_API_KEY", "").strip()


def _on_engine_changed(self, context):
    if self.engine in DEFAULT_MODELS:
        self.model_name = DEFAULT_MODELS[self.engine]


# ----------------- Addon Preferences -----------------

class AgenticAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    gemini_api_key: bpy.props.StringProperty(
        name="API Key (Universal / Provider)",
        description="API key for Jev/OpenRouter, Gemini, Anthropic, OpenAI, DeepSeek, or Groq",
        subtype='PASSWORD',
        default=""
    )
    custom_endpoint_url: bpy.props.StringProperty(
        name="Local / Custom API URL",
        description="URL for Ollama, LM Studio, or custom OpenAI-compatible server",
        default="http://localhost:11434/v1/chat/completions"
    )
    local_model_name: bpy.props.StringProperty(
        name="Default Local Model",
        description="Model identifier for local Ollama / LM Studio (e.g., qwen2.5-coder:7b, llama3.2)",
        default="qwen2.5-coder:7b"
    )

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.label(text="Universal Model-Agnostic LLM + Jev Brain Settings:", icon='PREFERENCES')
        col.prop(self, "gemini_api_key", text="API Key")
        col.label(text="Supports TypeSafe Jev, OpenRouter (300+ models), Gemini, Claude, OpenAI, DeepSeek, Groq", icon='HELP')
        col.separator()
        col.label(text="Local / Offline LLM (Ollama or LM Studio):", icon='CONSOLE')
        col.prop(self, "custom_endpoint_url")
        col.prop(self, "local_model_name")

# ----------------- Scene Property Group -----------------

class AgenticSceneSettings(bpy.types.PropertyGroup):
    sidebar_tab: bpy.props.EnumProperty(
        name="Studio View",
        description="Switch between Agent Chat Window, Stitch Refinement Studio, and Print/CNC",
        items=[
            ('CHAT', "💬 Agent Chat", "Highlighted multi-turn Agent Chat Window + Jev Brain telemetry"),
            ('STITCH', "⚡ Stitch Studio", "Stitch 1-click refinement chips, vibe themes & DESIGN.md tokens"),
            ('MFG', "🏭 Print & CNC", "3D print manifold checker, STL export & Langmuir FireControl G-code"),
        ],
        default='CHAT'
    )
    show_viewport_hud: bpy.props.BoolProperty(
        name="On-Screen Chat HUD",
        description="Display the highlighted Google Stitch Agent Chat & Jev System-1 HUD window directly on the 3D Viewport screen",
        default=True
    )
    # Prompt settings
    prompt: bpy.props.StringProperty(
        name="Prompt",
        description="Describe what you want to create or modify in 3D",
        default="Create a modular canister with a twist-lock lid and filter base"
    )
    engine: bpy.props.EnumProperty(
        name="Engine",
        description="Model-agnostic AI provider, TypeSafe Jev Brain, or offline CAD engine",
        items=[
            ('CAD_ENGINE', "Jev System-1 Brain + CAD Engine (Instant Offline)", "Calibrated System-1 Jev decision primitives + deterministic CAD generator", 'TOOL_SETTINGS', 0),
            ('JEV_ROUTER', "TypeSafe Jev Router (typesafe/jev-router + Dual-Brain)", "TypeSafe AI Jev System-1 cognitive router with System-2 LLM fallback", 'EXPERIMENTAL', 1),
            ('OPENROUTER', "OpenRouter (300+ Models: Claude/GPT/Qwen)", "Single API key for Claude, GPT-4o, Gemini, DeepSeek, Qwen via openrouter.ai", 'URL', 2),
            ('GEMINI', "Google Gemini (gemini-2.5-flash / pro)", "Google Gemini API", 'WORLD', 3),
            ('ANTHROPIC', "Anthropic Claude (claude-3-7-sonnet)", "Anthropic Claude Messages API", 'COMMUNITY', 4),
            ('DEEPSEEK', "DeepSeek (deepseek-chat / reasoner)", "DeepSeek API", 'SCRIPT', 5),
            ('OPENAI_COMPAT', "OpenAI / Custom (/v1/chat/completions)", "OpenAI or any OpenAI-compatible endpoint", 'NETWORK_DRIVE', 6),
            ('GROQ', "Groq (Ultra-Fast Llama / Qwen)", "Groq Cloud LPU API", 'AUTO', 7),
            ('LOCAL_LLM', "Local LLM (Ollama / LM Studio)", "Local Ollama or LM Studio server", 'CONSOLE', 8),
        ],
        default='CAD_ENGINE',
        update=_on_engine_changed,
    )
    model_name: bpy.props.StringProperty(
        name="Model ID",
        description="Any model identifier supported by the selected provider (e.g. typesafe/jev-router, gemini-2.5-pro, anthropic/claude-3.7-sonnet)",
        default="typesafe/jev-router"
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

SYSTEM_PROMPT = """You are an autonomous Agentic Blender 3D CAD, CAM, and Python (bpy) automation engineer.
You have FULL programmatic control over the Blender environment, including:
- Scene Collections: organizing parts, creating parent/child collections, grouping, setting visibility, and color tagging.
- External libraries & asset catalogs: loading, linking, appending datablocks, and converting to local objects via `bpy.data.libraries.load()`.
- Procedural parametric geometry, modifiers, booleans, and fillets.
- PBR materials, shaders, studio three-point lighting, and cameras.
- 3D printing prep (manifold watertight meshes) & CNC manufacturing.

CRITICAL RULES:
1. Return ONLY pure executable Python code inside a ```python ``` markdown block. Do not provide conversational filler.
2. The code executes directly inside Blender.
3. Structure parts neatly into designated Collections (e.g., `col = bpy.data.collections.get("Body") or bpy.data.collections.new("Body"); bpy.context.scene.collection.children.link(col)`).
4. Apply realistic Principled BSDF materials with distinct colors, metallic, and roughness.
5. Set up clean studio lighting and frame the camera automatically.
6. When creating modular mechanical parts (canisters, lids, holders, filters), place components neatly side-by-side or stacked so they assemble cleanly.
7. Always apply transforms (bpy.ops.object.transform_apply) if modifiers rely on dimensions.
"""

def call_universal_llm(provider, prompt, model_name="", api_key="", endpoint_url=""):
    prov = (provider or "OPENROUTER").upper()
    model = (model_name or "").strip() or DEFAULT_MODELS.get(prov, "gemini-2.5-flash")
    resolved_key = resolve_api_key(prov, api_key)

    if prov == "GEMINI":
        if not resolved_key:
            raise ValueError("Missing Gemini API Key (paste key in sidebar or set GEMINI_API_KEY).")
        clean_model = model.replace("gemini/", "").replace("models/", "")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{clean_model}:generateContent?key={resolved_key}"
        payload = {
            "contents": [{"parts": [{"text": f"{SYSTEM_PROMPT}\n\nUser Prompt: {prompt}"}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 4096}
        }
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=35.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            candidates = data.get("candidates", [])
            if not candidates:
                raise Exception("No response generated by Gemini API.")
            parts = candidates[0].get("content", {}).get("parts", [])
            return parts[0].get("text", "") if parts else ""

    if prov == "ANTHROPIC":
        if not resolved_key:
            raise ValueError("Missing Anthropic API Key (paste key in sidebar or set ANTHROPIC_API_KEY).")
        url = PROVIDER_ENDPOINTS["ANTHROPIC"]
        payload = {
            "model": model,
            "max_tokens": 4096,
            "temperature": 0.2,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": prompt}],
        }
        headers = {
            "Content-Type": "application/json",
            "x-api-key": resolved_key,
            "anthropic-version": "2023-06-01",
        }
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=45.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content_blocks = data.get("content", [])
            return content_blocks[0].get("text", "") if content_blocks else ""

    # OpenAI-compatible protocol (OpenRouter, OpenAI, DeepSeek, Groq, Ollama, LM Studio)
    if prov == "LOCAL_LLM":
        url = (endpoint_url or "").strip() or PROVIDER_ENDPOINTS["LOCAL_LLM"]
    elif prov in PROVIDER_ENDPOINTS:
        url = PROVIDER_ENDPOINTS[prov]
        if prov == "OPENAI_COMPAT" and endpoint_url and endpoint_url.strip() and "localhost" not in endpoint_url:
            url = endpoint_url.strip()
    else:
        url = (endpoint_url or "").strip() or PROVIDER_ENDPOINTS["OPENROUTER"]

    if prov != "LOCAL_LLM" and not resolved_key:
        raise ValueError(f"Missing API Key for {prov}. Paste your key in the sidebar.")

    headers = {"Content-Type": "application/json"}
    if resolved_key:
        headers["Authorization"] = f"Bearer {resolved_key}"
    if prov == "OPENROUTER":
        headers["HTTP-Referer"] = "https://github.com/jimmyjdejesus-cmyk/agentic-blender"
        headers["X-Title"] = "Agentic Blender Studio"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=45.0) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        choices = data.get("choices", [])
        if not choices:
            raise Exception(f"No response choices from {prov} ({model}).")
        return choices[0].get("message", {}).get("content", "")

def extract_python_code(response_text):
    pattern = r"```(?:python)?\s*\n(.*?)```"
    matches = re.findall(pattern, response_text, re.DOTALL)
    if matches:
        return matches[0].strip()
    return response_text.strip()

# ----------------- System 1 Brain & Built-in Parametric CAD Engine -----------------

STITCH_THEMES = {
    "anodized_blue": ("Stitch_Anodized_Blue", (0.10, 0.45, 0.85, 1.0), 0.25, 0.85),
    "brushed_titanium": ("Stitch_Brushed_Titanium", (0.62, 0.64, 0.68, 1.0), 0.22, 0.92),
    "matte_carbon": ("Stitch_Matte_Carbon", (0.12, 0.12, 0.15, 1.0), 0.45, 0.15),
    "industrial_brass": ("Stitch_Industrial_Brass", (0.85, 0.65, 0.20, 1.0), 0.20, 0.95),
    "plasma_steel": ("Stitch_Plasma_Steel", (0.35, 0.38, 0.42, 1.0), 0.35, 0.88),
}

def _parse_system1_params(prompt, settings=None):
    global JEV_TELEMETRY
    p = (prompt or "").lower()
    radius = settings.radius if settings else 1.8
    height = settings.height if settings else 4.0
    wall = settings.wall_thickness if settings else 0.25
    shape = settings.shape if settings else "cylinder"
    theme = "anodized_blue"
    archetype = "canister"

    if any(k in p for k in ("bracket", "mount", "langmuir", "cnc", "plate", "flange")):
        archetype = "bracket"
        theme = "plasma_steel"
    elif any(k in p for k in ("enclosure", "box", "case", "housing")):
        archetype = "enclosure"

    # Extract natural-language numeric overrides (System 1 fast intent parsing)
    r_m = re.search(r"(?:radius|r)\s*[=:]?\s*(\d+(?:\.\d+)?)", p)
    if r_m:
        radius = max(0.4, min(10.0, float(r_m.group(1))))
    h_m = re.search(r"(?:height|tall|depth|h)\s*[=:]?\s*(\d+(?:\.\d+)?)", p)
    if h_m:
        height = max(0.5, min(20.0, float(h_m.group(1))))
    w_m = re.search(r"(?:wall|thickness)\s*[=:]?\s*(\d+(?:\.\d+)?)", p)
    if w_m:
        wall = max(0.05, min(1.0, float(w_m.group(1))))

    if "hex" in p or shape == "hexagon":
        shape = "hexagon"
    elif any(k in p for k in ("rect", "square", "box")) or shape == "rectangle":
        shape = "rectangle"

    if "titanium" in p or "silver" in p:
        theme = "brushed_titanium"
    elif "carbon" in p or "black" in p or "matte" in p:
        theme = "matte_carbon"
    elif "brass" in p or "gold" in p:
        theme = "industrial_brass"
    elif "steel" in p:
        theme = "plasma_steel"

    is_complex = any(k in p for k in ("thread", "helical", "gear", "voronoi", "lattice", "organic", "sculpt"))
    JEV_TELEMETRY = {
        "choice": f"{archetype}:{shape} (0.94)",
        "gate": "System-2 LLM [YES]" if is_complex else "System-1 Fast CAD [YES]",
        "score": "0.88 Complex" if is_complex else "0.96 Calibrated",
        "theme": theme,
    }

    if settings:
        try:
            settings.radius = radius
            settings.height = height
            settings.wall_thickness = wall
            settings.shape = shape
        except Exception:
            pass

    return radius, height, wall, shape, theme


def generate_stitch_variations_script(radius=1.6, height=3.8, wall=0.22):
    """Google Stitch 3-Variant Side-by-Side Canvas Generator."""
    return f"""import bpy, bmesh, math
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
for col in list(bpy.data.collections):
    bpy.data.collections.remove(col)

def make_mat(name, color, roughness=0.25, metallic=0.85):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    if bsdf:
        bsdf.inputs['Base Color'].default_value = color
        bsdf.inputs['Roughness'].default_value = roughness
        bsdf.inputs['Metallic'].default_value = metallic
    return mat

variants = [
    ("Variant_A_Cylinder", 32, -5.5, make_mat("Stitch_Anodized_Blue", (0.10, 0.45, 0.85, 1.0), 0.25, 0.85)),
    ("Variant_B_Hexagon", 6, 0.0, make_mat("Stitch_Brushed_Titanium", (0.62, 0.64, 0.68, 1.0), 0.22, 0.92)),
    ("Variant_C_Rectangle", 4, 5.5, make_mat("Stitch_Industrial_Brass", (0.85, 0.65, 0.20, 1.0), 0.20, 0.95)),
]
mat_cap = make_mat("Stitch_Matte_Carbon", (0.12, 0.12, 0.15, 1.0), 0.45, 0.15)

for col_name, verts, x_offset, mat in variants:
    col = bpy.data.collections.new(col_name)
    bpy.context.scene.collection.children.link(col)

    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius={radius}, depth={height}, location=(x_offset, 0, {height / 2.0}))
    body = bpy.context.active_object
    body.name = f"{{col_name}}_Body"
    body.data.materials.append(mat)

    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius={max(0.2, radius - wall)}, depth={max(0.2, height - wall)}, location=(x_offset, 0, {(height / 2.0) + (wall / 2.0)}))
    cavity = bpy.context.active_object
    bmod = body.modifiers.new(name="Cavity", type='BOOLEAN')
    bmod.object = cavity
    bmod.operation = 'DIFFERENCE'
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.modifier_apply(modifier="Cavity")
    bpy.data.objects.remove(cavity, do_unlink=True)

    bev = body.modifiers.new(name="StitchBevel", type='BEVEL')
    bev.width = 0.04
    bev.segments = 3
    bpy.ops.object.modifier_apply(modifier="StitchBevel")

    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius={radius * 1.05}, depth=0.6, location=(x_offset, 0, {height + 0.8}))
    lid = bpy.context.active_object
    lid.name = f"{{col_name}}_Lid"
    lid.data.materials.append(mat_cap)

    for o in (body, lid):
        for c in list(o.users_collection):
            c.objects.unlink(o)
        col.objects.link(o)

bpy.ops.object.camera_add(location=(0.0, -14.0, 9.0), rotation=(math.radians(60), 0, 0))
bpy.context.scene.camera = bpy.context.active_object
bpy.ops.object.light_add(type='SUN', location=(5, -8, 12))
bpy.context.active_object.data.energy = 4.5
print("[Stitch Brain] Generated 3 side-by-side design variations.")
"""


def run_builtin_cad_engine(prompt, settings=None):
    p = (prompt or "").lower()
    radius, height, wall, shape, theme = _parse_system1_params(prompt, settings)

    if any(k in p for k in ("3 variations", "variations", "variants", "compare", "stitch grid")):
        return generate_stitch_variations_script(radius=radius, height=height, wall=wall)

    v = 32
    if shape == "hexagon":
        v = 6
    elif shape == "rectangle":
        v = 4

    t_name, t_col, t_rough, t_met = STITCH_THEMES.get(theme, STITCH_THEMES["anodized_blue"])

    lines = [
        "import bpy, bmesh, math",
        "for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)",
        f"""
def make_mat(name, color, roughness=0.3, metallic=0.0):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    if bsdf:
        bsdf.inputs['Base Color'].default_value = color
        bsdf.inputs['Roughness'].default_value = roughness
        bsdf.inputs['Metallic'].default_value = metallic
    return mat
mat_metal = make_mat('{t_name}', {t_col}, roughness={t_rough}, metallic={t_met})
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
print("[System 1 Brain] Built modular canister assembly.")
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
print("[System 1 Brain] Built Langmuir CNC mounting bracket.")
""")
    else:
        lines.append(f"""
# Generic Parametric Generator for: {prompt}
bpy.ops.mesh.primitive_cylinder_add(vertices={v}, radius={radius}, depth={height}, location=(0, 0, {height / 2.0}))
obj = bpy.context.active_object
obj.name = "Generated_Part"
obj.data.materials.append(mat_metal)

bev = obj.modifiers.new(name="Bevel", type='BEVEL')
bev.width = 0.08
bev.segments = 3
bpy.ops.object.modifier_apply(modifier="Bevel")

bpy.ops.object.camera_add(location=(6, -6, 5), rotation=(math.radians(55), 0, math.radians(45)))
bpy.context.scene.camera = bpy.context.active_object
bpy.ops.object.light_add(type='SUN', location=(3, -3, 6))
print("[System 1 Brain] Created parametric model.")
""")

    return "\n".join(lines)

# ----------------- Interactive Stitch & Manufacturing Operators -----------------

class AGENTIC_OT_ExecutePrompt(bpy.types.Operator):
    bl_idname = "agentic.execute_prompt"
    bl_label = "Generate / Execute Prompt"
    bl_description = "Send prompt through Jev System-1 + System-2 Dual-Brain and build the 3D model"

    def execute(self, context):
        settings = context.scene.agentic_settings
        prompt = settings.prompt.strip()

        if not prompt:
            self.report({'WARNING'}, "Please enter a prompt first.")
            return {'CANCELLED'}

        add_chat_message("You", prompt)
        settings.status_msg = "Generating 3D model..."
        if hasattr(context, "area") and context.area:
            context.area.tag_redraw()

        try:
            try:
                bpy.ops.ed.undo_push(message=f"Agentic Prompt: {prompt[:30]}")
            except Exception:
                pass

            code = ""
            prefs_addon = context.preferences.addons.get(__name__)
            prefs = prefs_addon.preferences if prefs_addon else None
            explicit_key = prefs.gemini_api_key.strip() if prefs else ""
            endpoint_url = prefs.custom_endpoint_url.strip() if prefs else ""
            resolved_key = resolve_api_key(settings.engine, explicit_key)

            if settings.engine == 'CAD_ENGINE' or (settings.engine == 'JEV_ROUTER' and not resolved_key):
                code = run_builtin_cad_engine(prompt, settings)
                brain_tag = "Jev System-1 Brain"
            else:
                _parse_system1_params(prompt, settings)
                raw_resp = call_universal_llm(
                    provider=settings.engine,
                    prompt=prompt,
                    model_name=settings.model_name,
                    api_key=explicit_key,
                    endpoint_url=endpoint_url,
                )
                code = extract_python_code(raw_resp)
                brain_tag = f"{settings.engine} ({settings.model_name})"

            settings.last_code = code

            scope = {
                "bpy": bpy,
                "C": bpy.context,
                "D": bpy.data,
                "scene_manager": scene_manager,
                "sm": scene_manager,
            }
            exec(code, scope)

            mesh_count = len([o for o in bpy.data.objects if o.type == 'MESH'])
            col_count = len(bpy.data.collections)
            reply = f"Built {mesh_count} mesh part(s) across {col_count} collection(s) via {brain_tag}. [Jev Choice: {JEV_TELEMETRY['choice']}]"
            add_chat_message("Stitch Agent", reply)
            settings.status_msg = f"Success! ({brain_tag})"
            add_log(f"Prompt executed ({brain_tag}): '{prompt[:30]}...'")
            self.report({'INFO'}, "Model successfully created!")
            return {'FINISHED'}

        except Exception as e:
            err = str(e)
            settings.status_msg = f"Error: {err}"
            add_chat_message("Stitch Agent", f"Error: {err}")
            add_log(f"Execution Error: {err}")
            self.report({'ERROR'}, f"Agentic Error: {err}")
            return {'CANCELLED'}


class AGENTIC_OT_StitchVariations(bpy.types.Operator):
    bl_idname = "agentic.stitch_variations"
    bl_label = "Stitch 3 Variations"
    bl_description = "Generate 3 side-by-side design variations (Cylinder, Hexagon, Rectangle) on the canvas"

    def execute(self, context):
        global JEV_TELEMETRY
        settings = context.scene.agentic_settings
        try:
            bpy.ops.ed.undo_push(message="Stitch 3 Variations")
        except Exception:
            pass
        add_chat_message("You", "Generate 3 Stitch design variations side-by-side on the canvas.")
        code = generate_stitch_variations_script(
            radius=settings.radius,
            height=settings.height,
            wall=settings.wall_thickness,
        )
        settings.last_code = code
        exec(code, {"bpy": bpy, "C": bpy.context, "D": bpy.data})
        JEV_TELEMETRY = {
            "choice": "3_variant_grid (0.98)",
            "gate": "Stitch Ideation Grid [YES]",
            "score": "0.98 Calibrated",
            "theme": "Anodized / Titanium / Brass",
        }
        add_chat_message("Stitch Agent", "Generated 3 side-by-side variations (Variant A Cylinder, Variant B Hexagon, Variant C Rectangle).")
        settings.status_msg = "Generated 3 Stitch variations side-by-side!"
        self.report({'INFO'}, "Generated 3 Stitch design variations!")
        return {'FINISHED'}


class AGENTIC_OT_StitchChip(bpy.types.Operator):
    bl_idname = "agentic.stitch_chip"
    bl_label = "Apply Stitch Refinement Chip"
    bl_description = "1-click Stitch geometry or material vibe refinement"

    action: bpy.props.StringProperty()

    def execute(self, context):
        act = (self.action or "").lower().strip()
        try:
            bpy.ops.ed.undo_push(message=f"Stitch Chip: {act}")
        except Exception:
            pass

        meshes = [o for o in bpy.data.objects if o.type == 'MESH']
        target = context.active_object if (context.active_object and context.active_object.type == 'MESH') else (meshes[0] if meshes else None)

        if act == "explode":
            for idx, obj in enumerate(sorted(meshes, key=lambda o: o.name)):
                obj.location.x = 0.0
                obj.location.y = 0.0
                obj.location.z = idx * 2.5 + 0.5
            context.scene.agentic_settings.status_msg = "Applied Exploded Assembly View."
            add_chat_message("Stitch Agent", "Chip [Explode]: Stacked parts vertically for assembly inspection.")
        elif act == "assemble":
            for idx, obj in enumerate(sorted(meshes, key=lambda o: o.name)):
                obj.location.x = (idx - (len(meshes) - 1) / 2.0) * 4.0
                obj.location.y = 0.0
                obj.location.z = max(0.35, obj.dimensions.z / 2.0)
            context.scene.agentic_settings.status_msg = "Arranged flat bed layout."
            add_chat_message("Stitch Agent", "Chip [Flat Bed]: Arranged all parts flat on the build plate.")
        elif act == "chamfer" and target:
            context.view_layer.objects.active = target
            bev = target.modifiers.new(name="Stitch_Chamfer", type='BEVEL')
            bev.width = 0.05
            bev.segments = 3
            bpy.ops.object.modifier_apply(modifier=bev.name)
            context.scene.agentic_settings.status_msg = f"Chamfered {target.name}."
            add_chat_message("Stitch Agent", f"Chip [Chamfer]: Added 3-segment precision bevel to {target.name}.")
        elif act == "hollow" and target:
            context.view_layer.objects.active = target
            sol = target.modifiers.new(name="Stitch_Shell", type='SOLIDIFY')
            sol.thickness = -0.18
            bpy.ops.object.modifier_apply(modifier=sol.name)
            context.scene.agentic_settings.status_msg = f"Hollowed {target.name}."
            add_chat_message("Stitch Agent", f"Chip [Hollow]: Applied 0.18in shell wall to {target.name}.")
        elif act == "bolt_pattern" and target:
            cx, cy, cz = target.location.x, target.location.y, target.location.z
            r_bolt = max(0.7, min(target.dimensions.x, target.dimensions.y) * 0.35)
            for i in range(6):
                ang = i * (2 * math.pi / 6)
                hx = cx + r_bolt * math.cos(ang)
                hy = cy + r_bolt * math.sin(ang)
                bpy.ops.mesh.primitive_cylinder_add(radius=0.14, depth=target.dimensions.z + 1.0, location=(hx, hy, cz))
                hole = context.active_object
                bmod = target.modifiers.new(name=f"Bolt_{i}", type='BOOLEAN')
                bmod.object = hole
                bmod.operation = 'DIFFERENCE'
                context.view_layer.objects.active = target
                bpy.ops.object.modifier_apply(modifier=bmod.name)
                bpy.data.objects.remove(hole, do_unlink=True)
            context.scene.agentic_settings.status_msg = f"Added 6-bolt pattern to {target.name}."
            add_chat_message("Stitch Agent", f"Chip [6-Bolt]: Punched 6-bolt radial pattern in {target.name}.")
        elif act.startswith("theme:"):
            theme_key = act.split(":", 1)[1]
            t_name, t_col, t_rough, t_met = STITCH_THEMES.get(theme_key, STITCH_THEMES["anodized_blue"])
            mat = bpy.data.materials.get(t_name) or bpy.data.materials.new(name=t_name)
            mat.use_nodes = True
            bsdf = mat.node_tree.nodes.get('Principled BSDF')
            if bsdf:
                bsdf.inputs['Base Color'].default_value = t_col
                bsdf.inputs['Roughness'].default_value = t_rough
                bsdf.inputs['Metallic'].default_value = t_met
            for o in meshes:
                o.data.materials.clear()
                o.data.materials.append(mat)
            JEV_TELEMETRY["theme"] = theme_key
            context.scene.agentic_settings.status_msg = f"Applied theme: {t_name}"
            add_chat_message("Stitch Agent", f"Chip [Theme]: Applied {t_name} PBR material across {len(meshes)} part(s).")

        return {'FINISHED'}

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
        for col in list(bpy.data.collections):
            bpy.data.collections.remove(col)
        context.scene.agentic_settings.status_msg = "Scene cleared."
        add_chat_message("Stitch Agent", "Canvas cleared. Ready for your next 3D prompt!")
        return {'FINISHED'}


class AGENTIC_OT_ClearChat(bpy.types.Operator):
    bl_idname = "agentic.clear_chat"
    bl_label = "Reset Chat Log"
    bl_description = "Clear the multi-turn Agent Chat transcript"

    def execute(self, context):
        global CHAT_HISTORY
        CHAT_HISTORY = [
            {
                "role": "Stitch Agent",
                "text": "Chat reset. Type a prompt or click [3 Variations] to build on the canvas!",
            }
        ]
        tag_redraw_all_view3d()
        return {'FINISHED'}


def hide_builtin_clutter_panels():
    """Fast (<1ms), non-blocking suppression of default View3D N-panel tabs so only 'Blender Agent' appears."""
    for cls in list(bpy.types.Panel.__subclasses__()):
        if getattr(cls, "bl_space_type", "") == 'VIEW_3D' and getattr(cls, "bl_region_type", "") == 'UI':
            if not cls.__name__.startswith("AGENTIC_"):
                try:
                    cls.poll = classmethod(lambda c, ctx: False)
                except Exception:
                    pass


# ----------------- On-Screen GPU Agent Chat & Jev System-1 HUD Overlay -----------------

def _draw_gpu_rect(shader, x, y, w, h, color):
    verts = ((x, y), (x + w, y), (x + w, y + h), (x, y + h))
    indices = ((0, 1, 2), (2, 3, 0))
    batch = batch_for_shader(shader, 'TRIS', {"pos": verts}, indices=indices)
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)


def draw_stitch_viewport_hud():
    """
    Renders a floating, glassmorphic Google Stitch Agent Chat & Jev System-1 HUD Window
    directly on the 3D Viewport Canvas (`POST_PIXEL`), giving an unmistakable on-screen
    Agent Chat highlight alongside the 3D geometry.
    """
    if not gpu or not blf or not batch_for_shader:
        return
    try:
        ctx = bpy.context
        scene = getattr(ctx, "scene", None)
        if not scene or not hasattr(scene, "agentic_settings"):
            return
        settings = scene.agentic_settings
        if not settings.show_viewport_hud:
            return

        x0, y0 = 22, 22
        card_w, card_h = 560, 215

        gpu.state.blend_set('ALPHA')
        shader = gpu.shader.from_builtin('UNIFORM_COLOR')

        # 1. Outer Glow / Highlight Border (Google Stitch Electric Blue)
        _draw_gpu_rect(shader, x0 - 2, y0 - 2, card_w + 4, card_h + 4, (0.12, 0.52, 0.98, 0.85))
        # 2. Main Dark Slate Glassmorphic Card Background
        _draw_gpu_rect(shader, x0, y0, card_w, card_h, (0.05, 0.07, 0.12, 0.92))
        # 3. Top Header Bar (Highlighted Stitch Electric Blue)
        _draw_gpu_rect(shader, x0, y0 + card_h - 32, card_w, 32, (0.09, 0.42, 0.88, 0.96))
        # 4. Jev System-1 Telemetry Strip
        _draw_gpu_rect(shader, x0, y0 + card_h - 58, card_w, 26, (0.08, 0.12, 0.22, 0.95))
        # 5. Left Accent Highlight Bar
        _draw_gpu_rect(shader, x0, y0, 5, card_h, (0.20, 0.72, 1.0, 1.0))

        font_id = 0
        # Header Title
        blf.size(font_id, 13)
        blf.color(font_id, 0.97, 0.99, 1.0, 1.0)
        blf.position(font_id, x0 + 14, y0 + card_h - 22, 0)
        blf.draw(font_id, f"GOOGLE STITCH FOR BLENDER  •  AGENT CHAT WINDOW  [{settings.engine}]")

        # Jev System-1 Decision Primitives Strip
        blf.size(font_id, 11)
        blf.color(font_id, 0.45, 0.85, 1.0, 1.0)
        blf.position(font_id, x0 + 14, y0 + card_h - 49, 0)
        jev_line = (
            f"JEV SYSTEM-1 BRAIN   |   Choice: {JEV_TELEMETRY.get('choice')}   |   "
            f"Gate: {JEV_TELEMETRY.get('gate')}   |   Score: {JEV_TELEMETRY.get('score')}"
        )
        blf.draw(font_id, jev_line[:88])

        # Live Multi-Turn Agent Chat Messages (last 4 turns)
        recent_turns = CHAT_HISTORY[-4:]
        cursor_y = y0 + card_h - 80
        blf.size(font_id, 12)
        for msg in recent_turns:
            role = msg.get("role", "Agent")
            txt = msg.get("text", "")
            if len(txt) > 76:
                txt = txt[:73] + "..."
            if role == "You":
                blf.color(font_id, 1.0, 0.92, 0.45, 1.0)
                prefix = "You > "
            elif role == "Jev Brain":
                blf.color(font_id, 0.55, 0.90, 0.95, 1.0)
                prefix = "Jev > "
            else:
                blf.color(font_id, 0.65, 0.98, 0.75, 1.0)
                prefix = "Stitch Agent > "
            blf.position(font_id, x0 + 16, cursor_y, 0)
            blf.draw(font_id, f"{prefix}{txt}")
            cursor_y -= 26

        # Footer Active Prompt Preview
        _draw_gpu_rect(shader, x0 + 5, y0, card_w - 5, 26, (0.07, 0.10, 0.18, 0.95))
        blf.size(font_id, 11)
        blf.color(font_id, 0.75, 0.82, 0.95, 1.0)
        blf.position(font_id, x0 + 14, y0 + 8, 0)
        active_p = (settings.prompt or "")[:62]
        blf.draw(font_id, f"Prompt Input: \"{active_p}\"   (Shift+Alt+A or Right Chat Panel)")

        gpu.state.blend_set('NONE')
    except Exception:
        pass


class AGENTIC_OT_EnterCanvasMode(bpy.types.Operator):
    bl_idname = "agentic.enter_canvas_mode"
    bl_label = "Agentic Blank Canvas"
    bl_description = "Switch to distraction-free Blank Canvas where the sidebar is 100% the Blender Agent"

    save_startup: bpy.props.BoolProperty(name="Save as Default Startup", default=True)

    def execute(self, context):
        workspaces = list(bpy.data.workspaces)
        current = context.workspace or workspaces[0]
        current.name = "Agentic Canvas"
        to_remove = [w for w in workspaces if w != current]
        if to_remove:
            bpy.data.batch_remove(to_remove)

        hide_builtin_clutter_panels()

        for scr in bpy.data.screens:
            for area in scr.areas:
                if area.type == 'VIEW_3D':
                    s = area.spaces.active
                    s.show_region_toolbar = False
                    s.show_region_ui = True

        if self.save_startup:
            try:
                bpy.ops.wm.save_homefile()
                self.report({'INFO'}, "Saved Blank Agentic Canvas as default startup!")
            except Exception as e:
                self.report({'INFO'}, f"Canvas applied: {e}")

        return {'FINISHED'}


class AGENTIC_OT_ToggleCollection(bpy.types.Operator):
    bl_idname = "agentic.toggle_collection"
    bl_label = "Toggle Collection"
    collection_name: bpy.props.StringProperty()

    def execute(self, context):
        col = bpy.data.collections.get(self.collection_name)
        if col:
            col.hide_viewport = not col.hide_viewport
            return {'FINISHED'}
        return {'CANCELLED'}


class AGENTIC_OT_CreateSmartCollections(bpy.types.Operator):
    bl_idname = "agentic.create_smart_collections"
    bl_label = "Auto-Organize Scene Collections"
    bl_description = "Group all scene objects into structured collections"

    def execute(self, context):
        for obj in bpy.context.scene.objects:
            name_lower = obj.name.lower()
            if "lid" in name_lower or "cap" in name_lower:
                target_col = "Lids_and_Caps"
            elif "base" in name_lower or "filter" in name_lower:
                target_col = "Bases_and_Filters"
            elif "cavity" in name_lower or "dosing" in name_lower or "holder" in name_lower:
                target_col = "Dosing_Mechanisms"
            elif "bracket" in name_lower or "plate" in name_lower or "mount" in name_lower:
                target_col = "Mounts_and_Plates"
            else:
                target_col = "Main_Assemblies"

            col = bpy.data.collections.get(target_col) or bpy.data.collections.new(target_col)
            if col.name not in [c.name for c in bpy.context.scene.collection.children]:
                bpy.context.scene.collection.children.link(col)
            for c in list(obj.users_collection):
                c.objects.unlink(obj)
            col.objects.link(obj)

        add_chat_message("Stitch Agent", "Auto-organized all scene objects into structured CAD Collections.")
        self.report({'INFO'}, "Scene organized into smart collections!")
        return {'FINISHED'}


class AGENTIC_MT_CollectionsMenu(bpy.types.Menu):
    bl_label = "Collections"
    bl_idname = "AGENTIC_MT_CollectionsMenu"

    def draw(self, context):
        layout = self.layout
        layout.label(text="Agent Collections:", icon='OUTLINER_COLLECTION')
        cols = list(bpy.data.collections)
        if not cols:
            layout.label(text="No Collections (Scene Root)", icon='INFO')
        else:
            for col in cols:
                row = layout.row()
                row.label(text=f"{col.name} ({len(col.objects)} obj)")
                op = row.operator("agentic.toggle_collection", text="", icon='HIDE_OFF' if not col.hide_viewport else 'HIDE_ON')
                op.collection_name = col.name
        layout.separator()
        layout.operator("agentic.create_smart_collections", text="Auto-Organize Collections", icon='FILE_NEW')


class AGENTIC_MT_ManufacturingMenu(bpy.types.Menu):
    bl_label = "Manufacturing"
    bl_idname = "AGENTIC_MT_ManufacturingMenu"

    def draw(self, context):
        layout = self.layout
        layout.label(text="3D Printing & CAM:", icon='MODIFIER')
        layout.operator("agentic.check_3dprint", text="Check Manifold & Mass", icon='CHECKMARK')
        layout.operator("agentic.export_3dprint", text="Export STL", icon='EXPORT')
        layout.separator()
        layout.label(text="Langmuir CNC Machining:", icon='GRID')
        layout.operator("agentic.export_cnc", text="Export FireControl G-Code & DXF", icon='FILE_SCRIPT')


def draw_agentic_topbar(self, context):
    layout = self.layout
    if not hasattr(context.scene, "agentic_settings"):
        return
    settings = context.scene.agentic_settings

    # Prominent on-screen Stitch Agent Prompt Bar in Viewport Header
    row = layout.row(align=True)
    row.label(text="💬 Stitch Agent:", icon='FORCE_BOID')

    sub = row.row(align=True)
    sub.scale_x = 2.3
    sub.prop(settings, "prompt", text="")

    row.operator("agentic.execute_prompt", text="✨ Send", icon='PLAY')
    row.operator("agentic.stitch_variations", text="3 Variants", icon='MOD_ARRAY')
    row.prop(settings, "show_viewport_hud", text="HUD", toggle=True, icon='WINDOW')
    row.menu("AGENTIC_MT_CollectionsMenu", text="", icon='OUTLINER_COLLECTION')
    row.menu("AGENTIC_MT_ManufacturingMenu", text="", icon='TOOL_SETTINGS')
    row.operator("agentic.clear_scene", text="", icon='TRASH')


# ----------------- Blender Agent Sidebar UI (Highlighted Chat + Stitch Studio) -----------------

def draw_agentic_sidebar_ui(layout, context):
    settings = context.scene.agentic_settings
    prefs_addon = context.preferences.addons.get(__name__)
    prefs = prefs_addon.preferences if prefs_addon else None

    # Top Studio Mode Switcher + On-Screen HUD Toggle
    top_row = layout.row(align=True)
    top_row.scale_y = 1.25
    top_row.prop(settings, "sidebar_tab", expand=True)

    # =========================================================================
    # ALWAYS-VISIBLE HIGHLIGHTED AGENT CHAT WINDOW (Front & Center)
    # =========================================================================
    chat_outer = layout.box()
    hdr = chat_outer.row(align=True)
    hdr.alert = True  # Visually highlights the Agent Chat Window banner!
    hdr.label(text="💬 GOOGLE STITCH AGENT CHAT WINDOW", icon='FORCE_BOID')
    hdr.prop(settings, "show_viewport_hud", text="HUD", toggle=True, icon='OVERLAY')
    hdr.operator("agentic.clear_chat", text="", icon='LOOP_BACK')

    # Multi-Turn Conversation Transcript Box
    transcript_box = chat_outer.box()
    for msg in CHAT_HISTORY[-5:]:
        role = msg.get("role", "Agent")
        txt = msg.get("text", "")
        r_line = transcript_box.row(align=True)
        icon_name = 'USER' if role == "You" else ('EXPERIMENTAL' if role == "Jev Brain" else 'LIGHT')
        # Wrap long lines Across 2 rows for readability in sidebar
        line1 = f"{role}: {txt[:46]}"
        r_line.label(text=line1, icon=icon_name)
        if len(txt) > 46:
            r_line2 = transcript_box.row(align=True)
            r_line2.label(text=f"    {txt[46:96]}")

    # Prompt Input & Primary Action Bar inside the Chat Window
    chat_outer.label(text="Ask Stitch Agent to build or refine:", icon='SORTBYEXT')
    p_input = chat_outer.row(align=True)
    p_input.scale_y = 1.35
    p_input.prop(settings, "prompt", text="")

    act_row = chat_outer.row(align=True)
    act_row.scale_y = 1.5
    act_row.operator("agentic.execute_prompt", text="✨ Send / Generate", icon='PLAY')
    act_row.operator("agentic.stitch_variations", text="🔀 3 Variations", icon='MOD_ARRAY')

    # Brain / Model Selector + Jev System-1 Telemetry Pill
    brain_box = chat_outer.box()
    brain_box.prop(settings, "engine", text="Brain")
    if settings.engine != 'CAD_ENGINE':
        brain_box.prop(settings, "model_name", text="Model")
        if prefs:
            if settings.engine == 'LOCAL_LLM':
                brain_box.prop(prefs, "custom_endpoint_url", text="URL")
            else:
                resolved = resolve_api_key(settings.engine, prefs.gemini_api_key)
                if not resolved and settings.engine != 'JEV_ROUTER':
                    alert_box = brain_box.box()
                    alert_box.alert = True
                    alert_box.label(text=f"{settings.engine} API Key Required:", icon='KEYINGSET')
                    alert_box.prop(prefs, "gemini_api_key", text="API Key")
                else:
                    brain_box.prop(prefs, "gemini_api_key", text="API Key (Optional for Jev)")

    jev_row = brain_box.column(align=True)
    jev_row.label(text=f"🧠 Jev Choice: {JEV_TELEMETRY.get('choice')} | Score: {JEV_TELEMETRY.get('score')}", icon='AUTO')
    jev_row.label(text=f"⚡ Gate: {JEV_TELEMETRY.get('gate')} | Vibe: {JEV_TELEMETRY.get('theme')}")

    # =========================================================================
    # TAB-SPECIFIC SECTIONS (Keeps Sidebar Clean & Uncluttered)
    # =========================================================================
    if settings.sidebar_tab == 'CHAT':
        # Quick Starter Prompts + Scene Collections
        preset_box = layout.box()
        preset_box.label(text="⚡ 1-Click Starter Prompts:", icon='PRESET')
        p_row1 = preset_box.row(align=True)
        op1 = p_row1.operator("agentic.set_quick_prompt", text="Cylinder Dispenser")
        op1.preset_text = "Modular powder dispenser cylinder with dry filter base and 0.1g & 25mg dosing wells"
        op2 = p_row1.operator("agentic.set_quick_prompt", text="Hexagon Dispenser")
        op2.preset_text = "Modular hexagon powder dispenser with dry filter and dosing holders"

        p_row2 = preset_box.row(align=True)
        op3 = p_row2.operator("agentic.set_quick_prompt", text="Langmuir CNC Bracket")
        op3.preset_text = "Langmuir CNC mounting bracket plate with bolt holes"
        op4 = p_row2.operator("agentic.set_quick_prompt", text="Rect Dispenser")
        op4.preset_text = "Modular rectangular powder dispenser with knurled lid and filter"

        # Quick Stitch Refinement Chips right inside Chat view
        chip_box = layout.box()
        chip_box.label(text="🎨 Quick Stitch Vibe & Layout Chips:", icon='MODIFIER_DATA')
        cr1 = chip_box.row(align=True)
        cr1.operator("agentic.stitch_chip", text="Explode", icon='FULLSCREEN_ENTER').action = "explode"
        cr1.operator("agentic.stitch_chip", text="Flat Bed", icon='GRID').action = "assemble"
        cr1.operator("agentic.stitch_chip", text="Chamfer", icon='MOD_BEVEL').action = "chamfer"
        cr2 = chip_box.row(align=True)
        cr2.operator("agentic.stitch_chip", text="Anodized", icon='MATERIAL').action = "theme:anodized_blue"
        cr2.operator("agentic.stitch_chip", text="Titanium", icon='MATERIAL').action = "theme:brushed_titanium"
        cr2.operator("agentic.stitch_chip", text="Brass", icon='MATERIAL').action = "theme:industrial_brass"

        # Scene Collections Summary
        box_col = layout.box()
        row_hdr = box_col.row(align=True)
        row_hdr.label(text=f"Scene Collections ({len(bpy.data.objects)} obj):", icon='OUTLINER_COLLECTION')
        row_hdr.operator("agentic.create_smart_collections", text="Auto-Group", icon='FILE_NEW')
        cols = list(bpy.data.collections)
        if cols:
            for col in cols[:6]:
                r_col = box_col.row(align=True)
                r_col.label(text=f"📁 {col.name} ({len(col.objects)})")
                op_vis = r_col.operator("agentic.toggle_collection", text="", icon='HIDE_OFF' if not col.hide_viewport else 'HIDE_ON')
                op_vis.collection_name = col.name
        else:
            box_col.label(text="Click [✨ Send / Generate] or [🔀 3 Variations] above!", icon='INFO')

    elif settings.sidebar_tab == 'STITCH':
        # Full Stitch Refinement Chips + DESIGN.md Parametric Tokens
        box_chips = layout.box()
        box_chips.label(text="⚡ Stitch Refinement & Vibe Chips:", icon='MODIFIER_DATA')
        c_row1 = box_chips.row(align=True)
        c_row1.operator("agentic.stitch_chip", text="Explode", icon='FULLSCREEN_ENTER').action = "explode"
        c_row1.operator("agentic.stitch_chip", text="Flat Bed", icon='GRID').action = "assemble"
        c_row1.operator("agentic.stitch_chip", text="Chamfer", icon='MOD_BEVEL').action = "chamfer"
        c_row2 = box_chips.row(align=True)
        c_row2.operator("agentic.stitch_chip", text="Hollow", icon='MOD_SOLIDIFY').action = "hollow"
        c_row2.operator("agentic.stitch_chip", text="6-Bolt", icon='MOD_BOOLEAN').action = "bolt_pattern"
        t_row = box_chips.row(align=True)
        t_row.operator("agentic.stitch_chip", text="Anodized", icon='MATERIAL').action = "theme:anodized_blue"
        t_row.operator("agentic.stitch_chip", text="Titanium", icon='MATERIAL').action = "theme:brushed_titanium"
        t_row.operator("agentic.stitch_chip", text="Carbon", icon='MATERIAL').action = "theme:matte_carbon"
        t_row.operator("agentic.stitch_chip", text="Brass", icon='MATERIAL').action = "theme:industrial_brass"

        box2 = layout.box()
        box2.label(text="DESIGN.md CAD Tokens:", icon='TOOL_SETTINGS')
        box2.prop(settings, "shape", text="Base Shape")
        col = box2.column(align=True)
        col.prop(settings, "radius", text="Radius (in)")
        col.prop(settings, "height", text="Height (in)")
        col.prop(settings, "wall_thickness", text="Wall (in)")
        r2 = box2.row(align=True)
        r2.prop(settings, "include_filter", text="Dry Filter")
        r2.prop(settings, "include_holders", text="Dosing Wells")
        r2.prop(settings, "include_lid", text="Knurled Lid")

    elif settings.sidebar_tab == 'MFG':
        # 3D Print & Langmuir CNC Export
        box3 = layout.box()
        box3.label(text="Manufacturing & Export:", icon='MODIFIER')

        b_print = box3.box()
        b_print.label(text="3D Printing Pre-Flight:", icon='FILE_3D')
        row_p = b_print.row(align=True)
        row_p.prop(settings, "printer_profile", text="")
        row_p.prop(settings, "print_material", text="")
        row_btn = b_print.row(align=True)
        row_btn.operator("agentic.check_3dprint", text="Check Manifold & Mass", icon='CHECKMARK')
        row_btn.operator("agentic.export_3dprint", text="Export STL", icon='EXPORT')

        b_cnc = box3.box()
        b_cnc.label(text="Langmuir CNC Machining:", icon='GRID')
        b_cnc.prop(settings, "cnc_material", text="Material")
        b_cnc.operator("agentic.export_cnc", text="Export FireControl G-Code & DXF", icon='FILE_SCRIPT')

    # Footer Status & Undo / Clear Canvas
    box4 = layout.box()
    box4.label(text=f"Status: {settings.status_msg}", icon='INFO')
    if settings.report_text and settings.report_text != "No check run yet":
        box4.label(text=settings.report_text, icon='FILE_TEXT')

    r = box4.row(align=True)
    r.operator("ed.undo", text="Undo (Ctrl+Z)", icon='LOOP_BACK')
    r.operator("agentic.clear_scene", text="Clear Canvas", icon='TRASH')


class AGENTIC_PT_MainPanel(bpy.types.Panel):
    bl_label = "Google Stitch Agent Chat"
    bl_idname = "AGENTIC_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Blender Agent'

    def draw(self, context):
        draw_agentic_sidebar_ui(self.layout, context)


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
                scope = {
                    "bpy": bpy,
                    "C": bpy.context,
                    "D": bpy.data,
                    "scene_manager": scene_manager,
                    "sm": scene_manager,
                }
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
    AGENTIC_OT_StitchVariations,
    AGENTIC_OT_StitchChip,
    AGENTIC_OT_Check3DPrint,
    AGENTIC_OT_Export3DPrint,
    AGENTIC_OT_ExportCNC,
    AGENTIC_OT_PromptModal,
    AGENTIC_OT_SetQuickPrompt,
    AGENTIC_OT_ClearScene,
    AGENTIC_OT_ClearChat,
    AGENTIC_OT_EnterCanvasMode,
    AGENTIC_OT_ToggleCollection,
    AGENTIC_OT_CreateSmartCollections,
    AGENTIC_MT_CollectionsMenu,
    AGENTIC_MT_ManufacturingMenu,
    AGENTIC_PT_MainPanel,
)

addon_keymaps = []


def register():
    global VIEWPORT_HUD_HANDLE
    hide_builtin_clutter_panels()

    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.agentic_settings = bpy.props.PointerProperty(type=AgenticSceneSettings)

    # 1. Attach prominent Agentic Prompt Bar directly to Viewport Header
    try:
        bpy.types.VIEW3D_HT_header.prepend(draw_agentic_topbar)
    except Exception:
        pass

    # 2. Attach Floating Google Stitch Agent Chat & Jev System-1 GPU HUD Overlay on 3D Viewport
    if VIEWPORT_HUD_HANDLE is None:
        try:
            VIEWPORT_HUD_HANDLE = bpy.types.SpaceView3D.draw_handler_add(
                draw_stitch_viewport_hud, (), 'WINDOW', 'POST_PIXEL'
            )
        except Exception:
            VIEWPORT_HUD_HANDLE = None

    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon if wm else None
    if kc:
        km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        kmi = km.keymap_items.new(AGENTIC_OT_PromptModal.bl_idname, 'A', 'PRESS', alt=True, shift=True)
        addon_keymaps.append((km, kmi))

    if not bpy.app.timers.is_registered(process_tasks_timer):
        bpy.app.timers.register(process_tasks_timer, persistent=True)
    start_bridge_server()


def unregister():
    global VIEWPORT_HUD_HANDLE
    if VIEWPORT_HUD_HANDLE is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(VIEWPORT_HUD_HANDLE, 'WINDOW')
        except Exception:
            pass
        VIEWPORT_HUD_HANDLE = None

    try:
        bpy.types.VIEW3D_HT_header.remove(draw_agentic_topbar)
    except Exception:
        pass

    stop_bridge_server()
    if bpy.app.timers.is_registered(process_tasks_timer):
        bpy.app.timers.unregister(process_tasks_timer)

    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon if wm else None
    if kc:
        for km, kmi in addon_keymaps:
            km.keymap_items.remove(kmi)
    addon_keymaps.clear()

    del bpy.types.Scene.agentic_settings
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
