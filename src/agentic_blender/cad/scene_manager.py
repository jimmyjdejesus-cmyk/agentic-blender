"""
Agentic Blender Scene & Asset Manager.
Gives AI agents full programmatic control over:
- Scene Collections (hierarchy, organization, visibility, isolation)
- External Libraries & Data-blocks (link, append, local conversions)
- Materials & PBR Shaders
- Cameras, Studio Lighting, and Viewport Presentation
- Manufacturing Export Pipelines
"""

import os
import math

try:
    import bpy
    import bmesh
except ImportError:
    bpy = None
    bmesh = None

def get_scene():
    """Return active scene safely."""
    if bpy and hasattr(bpy, "context") and bpy.context and bpy.context.scene:
        return bpy.context.scene
    return None

# ==============================================================================
# 1. COLLECTIONS MANAGEMENT (Full Hierarchy & Control)
# ==============================================================================

def ensure_collection(name, parent_name=None, color_tag=None):
    """
    Ensure a collection exists with the given name, optionally linked under parent.
    Color tags supported: 'COLOR_01' through 'COLOR_08' (Red, Orange, Yellow, Green, Blue, Violet, Pink, Brown).
    """
    if not bpy:
        return None

    # Check if collection already exists
    col = bpy.data.collections.get(name)
    if not col:
        col = bpy.data.collections.new(name)
        if color_tag and hasattr(col, "color_tag"):
            try:
                col.color_tag = color_tag
            except Exception:
                pass

    # Find parent collection
    if parent_name:
        parent = bpy.data.collections.get(parent_name)
        if not parent:
            parent = ensure_collection(parent_name)
    else:
        parent = bpy.context.scene.collection

    # Link if not already linked in this parent
    if col.name not in [c.name for c in parent.children]:
        parent.children.link(col)

    return col

def move_object_to_collection(obj_or_name, collection_name):
    """Move an object exclusively into the target collection."""
    if not bpy:
        return None
    obj = bpy.data.objects.get(obj_or_name) if isinstance(obj_or_name, str) else obj_or_name
    if not obj:
        return False

    target_col = ensure_collection(collection_name)

    # Unlink from all other collections
    for col in list(obj.users_collection):
        col.objects.unlink(obj)

    # Link to target
    target_col.objects.link(obj)
    return True

def organize_into_collections(mapping):
    """
    Batch organize objects into named collections.
    mapping: {"Collection_Name": ["Obj1", "Obj2"], ...} or {"ObjName": "Collection_Name"}
    """
    if not bpy:
        return {}
    results = {}
    for key, val in mapping.items():
        if isinstance(val, (list, tuple)):
            col_name = key
            for item in val:
                move_object_to_collection(item, col_name)
            results[col_name] = len(val)
        else:
            obj_name = key
            col_name = val
            move_object_to_collection(obj_name, col_name)
            results[obj_name] = col_name
    return results

def list_collections(include_objects=True):
    """List all collections with their objects, visibility, and hierarchy."""
    if not bpy:
        return []
    info = []
    for col in bpy.data.collections:
        c_data = {
            "name": col.name,
            "objects_count": len(col.objects),
            "hide_viewport": col.hide_viewport,
            "hide_render": col.hide_render,
        }
        if include_objects:
            c_data["objects"] = [o.name for o in col.objects]
        info.append(c_data)
    return info

def set_collection_visibility(name, hide_viewport=False, hide_render=False):
    """Set viewport and render visibility for a collection."""
    if not bpy:
        return False
    col = bpy.data.collections.get(name)
    if not col:
        return False
    col.hide_viewport = hide_viewport
    col.hide_render = hide_render
    return True

def isolate_collection(name):
    """Hide all collections except the target collection."""
    if not bpy:
        return False
    target = bpy.data.collections.get(name)
    if not target:
        return False
    for col in bpy.data.collections:
        col.hide_viewport = (col.name != target.name)
    return True

def clear_all_collections(delete_objects=True):
    """Remove all collections and optionally delete member objects."""
    if not bpy:
        return
    if delete_objects:
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)
    for col in list(bpy.data.collections):
        bpy.data.collections.remove(col)

# ==============================================================================
# 2. LIBRARIES & EXTERNAL ASSETS (Link, Append, Make Local)
# ==============================================================================

def list_libraries():
    """List all loaded external .blend libraries."""
    if not bpy:
        return []
    return [
        {
            "name": lib.name,
            "filepath": lib.filepath,
            "users": lib.users,
            "packed": lib.packed_file is not None
        }
        for lib in bpy.data.libraries
    ]

def link_or_append_library(filepath, datablock_type="objects", names=None, link=False):
    """
    Link or append datablocks from an external .blend file.
    datablock_type: 'objects', 'materials', 'collections', 'node_groups'
    names: list of names or None for all
    link: True to link (read-only reference), False to append (fully editable local copy)
    """
    if not bpy or not os.path.exists(filepath):
        return {"error": f"File not found: {filepath}"}

    imported_items = []
    with bpy.data.libraries.load(filepath, link=link) as (data_from, data_to):
        pool = getattr(data_from, datablock_type, [])
        if names:
            setattr(data_to, datablock_type, [n for n in pool if n in names])
        else:
            setattr(data_to, datablock_type, pool)

    # Link imported objects/collections into active scene if applicable
    imported = getattr(data_to, datablock_type, [])
    if datablock_type == "objects":
        for obj in imported:
            if obj and obj.name not in bpy.context.scene.collection.objects:
                bpy.context.scene.collection.objects.link(obj)
                imported_items.append(obj.name)
    elif datablock_type == "collections":
        for col in imported:
            if col and col.name not in bpy.context.scene.collection.children:
                bpy.context.scene.collection.children.link(col)
                imported_items.append(col.name)
    else:
        imported_items = [item.name for item in imported if item]

    return {
        "filepath": filepath,
        "type": datablock_type,
        "mode": "link" if link else "append",
        "imported": imported_items
    }

def make_all_local():
    """Convert all linked library datablocks into independent local datablocks."""
    if not bpy:
        return
    for obj in bpy.data.objects:
        if obj.library:
            obj.make_local()
    for mat in bpy.data.materials:
        if mat.library:
            mat.make_local()

# ==============================================================================
# 3. PROCEDURAL PBR MATERIALS & SHADING
# ==============================================================================

def create_pbr_material(
    name,
    base_color=(0.8, 0.8, 0.8, 1.0),
    metallic=0.0,
    roughness=0.4,
    emission_color=None,
    emission_strength=1.0,
    transmission=0.0
):
    """Create or update a Principled BSDF procedural PBR material."""
    if not bpy:
        return None
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()

    output = nodes.new(type='ShaderNodeOutputMaterial')
    output.location = (300, 0)
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.location = (0, 0)

    # Inputs in Blender 4.x / 5.x Principled BSDF
    bsdf.inputs['Base Color'].default_value = base_color
    bsdf.inputs['Metallic'].default_value = metallic
    bsdf.inputs['Roughness'].default_value = roughness
    if 'Transmission Weight' in bsdf.inputs:
        bsdf.inputs['Transmission Weight'].default_value = transmission
    elif 'Transmission' in bsdf.inputs:
        bsdf.inputs['Transmission'].default_value = transmission

    if emission_color:
        if 'Emission Color' in bsdf.inputs:
            bsdf.inputs['Emission Color'].default_value = emission_color
            bsdf.inputs['Emission Strength'].default_value = emission_strength
        elif 'Emission' in bsdf.inputs:
            bsdf.inputs['Emission'].default_value = emission_color

    mat.node_tree.links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
    return mat

def assign_material(obj_or_name, material_or_name):
    """Assign material to an object's primary slot."""
    if not bpy:
        return False
    obj = bpy.data.objects.get(obj_or_name) if isinstance(obj_or_name, str) else obj_or_name
    mat = bpy.data.materials.get(material_or_name) if isinstance(material_or_name, str) else material_or_name
    if not obj or not mat:
        return False

    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)
    return True

# ==============================================================================
# 4. STUDIO LIGHTING & CAMERA FRAMING
# ==============================================================================

def setup_studio_scene(camera_distance=8.0, collection_name="Agent_Studio"):
    """
    Creates a clean 3-point studio lighting setup (Key, Fill, Rim)
    and an angled camera framed directly on the center of the scene.
    """
    if not bpy:
        return
    col = ensure_collection(collection_name, color_tag='COLOR_04')

    # Remove existing studio lights if present
    for o in list(col.objects):
        bpy.data.objects.remove(o, do_unlink=True)

    # 1. Key Light (Warm, high intensity)
    key_light = bpy.data.lights.new(name="Studio_Key", type='AREA')
    key_light.energy = 500.0
    key_light.color = (1.0, 0.96, 0.92)
    key_light.size = 2.0
    key_obj = bpy.data.objects.new("Studio_Key", key_light)
    key_obj.location = (4.0, -4.0, 5.0)
    col.objects.link(key_obj)

    # 2. Fill Light (Cool, soft intensity)
    fill_light = bpy.data.lights.new(name="Studio_Fill", type='AREA')
    fill_light.energy = 200.0
    fill_light.color = (0.92, 0.95, 1.0)
    fill_light.size = 3.0
    fill_obj = bpy.data.objects.new("Studio_Fill", fill_light)
    fill_obj.location = (-4.0, -3.0, 3.5)
    col.objects.link(fill_obj)

    # 3. Rim Light (Back light for silhouette definition)
    rim_light = bpy.data.lights.new(name="Studio_Rim", type='POINT')
    rim_light.energy = 300.0
    rim_light.color = (1.0, 1.0, 1.0)
    rim_obj = bpy.data.objects.new("Studio_Rim", rim_light)
    rim_obj.location = (0.0, 4.0, 4.0)
    col.objects.link(rim_obj)

    # 4. Studio Camera
    cam_data = bpy.data.cameras.new(name="Agentic_Camera")
    cam_data.lens = 50.0
    cam_obj = bpy.data.objects.new("Agentic_Camera", cam_data)
    cam_obj.location = (camera_distance * 0.7, -camera_distance * 0.7, camera_distance * 0.6)
    cam_obj.rotation_euler = (math.radians(58.0), 0.0, math.radians(45.0))
    col.objects.link(cam_obj)
    bpy.context.scene.camera = cam_obj

    return {
        "camera": cam_obj.name,
        "lights": [key_obj.name, fill_obj.name, rim_obj.name]
    }
