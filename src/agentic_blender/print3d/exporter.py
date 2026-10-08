"""
3D Print Mesh Exporter & Headless Pipeline Script Generator for Blender.
"""

def generate_blender_export_script(
    output_path,
    object_name=None,
    format="stl",  # "stl" or "3mf"
    auto_repair=True,
    units_scale=1000.0  # Blender meters to mm for 3D printing
):
    """
    Produces Blender Python script to inspect mesh health, calculate metrics,
    and export high-resolution STL or 3MF.
    """
    return f'''import bpy, bmesh, json, os

output_path = r"{output_path}"
os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

# Find target mesh object
target = None
if "{object_name}" and "{object_name}" in bpy.data.objects:
    target = bpy.data.objects["{object_name}"]
elif bpy.context.active_object and bpy.context.active_object.type == 'MESH':
    target = bpy.context.active_object
else:
    for obj in bpy.data.objects:
        if obj.type == 'MESH':
            target = obj
            break

if not target:
    print(json.dumps({{"error": "No mesh object found in scene"}}))
    import sys; sys.exit(1)

bpy.context.view_layer.objects.active = target
bpy.ops.object.select_all(action='DESELECT')
target.select_set(True)

# Apply transforms for accurate dimensional export
bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)

# Topology evaluation via bmesh
bm = bmesh.new()
bm.from_mesh(target.data)

non_manifold_count = sum(1 for e in bm.edges if not e.is_manifold)

if {auto_repair} and non_manifold_count > 0:
    # Attempt automatic normal recalculation and degenerate dissolve
    bmesh.ops.dissolve_degenerate(bm, dist=0.0001, edges=bm.edges)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(target.data)
    non_manifold_count = sum(1 for e in bm.edges if not e.is_manifold)

# Compute dimensions in millimeters
dims = target.dimensions * {units_scale}
vol_cm3 = (bm.calc_volume() * ({units_scale}**3)) / 1000.0

bm.free()

# Export based on format
fmt = "{format.lower()}"
if fmt == "stl":
    if hasattr(bpy.ops.wm, "stl_export"):
        bpy.ops.wm.stl_export(filepath=output_path, export_selected_objects=True, global_scale={units_scale / 1000.0})
    else:
        bpy.ops.export_mesh.stl(filepath=output_path, use_selection=True, global_scale={units_scale / 1000.0})
elif fmt == "3mf":
    if hasattr(bpy.ops.wm, "threemf_export"):
        bpy.ops.wm.threemf_export(filepath=output_path, export_selected_objects=True)
    else:
        print("[Warning] 3MF operator not available in this Blender build, fallback to STL")
        fallback_stl = output_path.replace(".3mf", ".stl")
        bpy.ops.export_mesh.stl(filepath=fallback_stl, use_selection=True)
        output_path = fallback_stl

report = {{
    "object": target.name,
    "filepath": output_path,
    "format": fmt,
    "non_manifold_edges": non_manifold_count,
    "is_watertight": (non_manifold_count == 0),
    "dimensions_mm": [round(dims.x, 2), round(dims.y, 2), round(dims.z, 2)],
    "volume_cm3": round(abs(vol_cm3), 3)
}}

print("AGENTIC_3DPRINT_REPORT:" + json.dumps(report))
'''
