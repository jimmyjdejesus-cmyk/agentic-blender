"""
2.5D Planar Contour Slicer & Vector Exporter for Blender.
Extracts boundary profiles from 3D models for plasma cutting and CNC milling.
"""

def generate_planar_slice_script(
    output_gcode_path,
    output_svg_path,
    machine_name="crossfire_pro",
    material_name="14_gauge_mild_steel",
    target_object_name=None
):
    """
    Generates a Blender Python script to project planar 2D contours and
    export both SVG and FireControl-ready G-code.
    """
    return f'''import bpy, bmesh, json, os

output_gcode = r"{output_gcode_path}"
output_svg = r"{output_svg_path}"

os.makedirs(os.path.dirname(os.path.abspath(output_gcode)), exist_ok=True)
os.makedirs(os.path.dirname(os.path.abspath(output_svg)), exist_ok=True)

# Select target
target = None
if "{target_object_name}" and "{target_object_name}" in bpy.data.objects:
    target = bpy.data.objects["{target_object_name}"]
elif bpy.context.active_object and bpy.context.active_object.type == 'MESH':
    target = bpy.context.active_object
else:
    for obj in bpy.data.objects:
        if obj.type == 'MESH':
            target = obj
            break

if not target:
    print("[Error] No mesh found for planar slicing.")
    import sys; sys.exit(1)

# Evaluate geometry
depsgraph = bpy.context.evaluated_depsgraph_get()
eval_obj = target.evaluated_get(depsgraph)
mesh = eval_obj.to_mesh()

bm = bmesh.new()
bm.from_mesh(mesh)
bmesh.ops.transform(bm, matrix=target.matrix_world)

# Extract 2D boundary loops
paths = []
planar_faces = [f for f in bm.faces if abs(f.normal.z) > 0.8]

if planar_faces:
    for face in planar_faces:
        if face.normal.z < 0: # Bottom planar face
            pts = [(v.co.x, v.co.y) for v in face.verts]
            if pts:
                pts.append(pts[0]) # Closed loop
                paths.append(pts)
            break

if not paths:
    # Bounding box fallback
    xs = [v.co.x for v in bm.verts]
    ys = [v.co.y for v in bm.verts]
    if xs and ys:
        paths.append([
            (min(xs), min(ys)),
            (max(xs), min(ys)),
            (max(xs), max(ys)),
            (min(xs), max(ys)),
            (min(xs), min(ys))
        ])

bm.free()
eval_obj.to_mesh_clear()

# 1. Export SVG
scale = 50.0
with open(output_svg, "w", encoding="utf-8") as f:
    f.write('<svg xmlns="http://www.w3.org/2000/svg" version="1.1">\\n')
    f.write('  <g fill="none" stroke="red" stroke-width="2">\\n')
    for loop in paths:
        pts_str = " ".join([f"{{pt[0]*scale}},{{pt[1]*scale}}" for pt in loop])
        f.write(f'    <polyline points="{{pts_str}}" />\\n')
    f.write('  </g>\\n</svg>\\n')

# 2. Generate FireControl G-Code
from agentic_blender.cnc.post_processor import format_firecontrol_plasma_gcode
gcode_str = format_firecontrol_plasma_gcode(
    paths=paths,
    machine_name="{machine_name}",
    material_name="{material_name}"
)

with open(output_gcode, "w", encoding="utf-8") as f:
    f.write(gcode_str)

print("[Slicer] Successfully generated SVG: " + output_svg)
print("[Slicer] Successfully generated G-Code: " + output_gcode)
'''

def export_dxf_from_paths(paths, output_dxf_path, units="inch"):
    """
    Exports 2D paths to an AutoCAD DXF file for SheetCAM or CAD packages.
    Uses ezdxf to create closed LWPOLYLINE entities with proper units.
    """
    import os
    os.makedirs(os.path.dirname(os.path.abspath(output_dxf_path)), exist_ok=True)
    try:
        import ezdxf
        doc = ezdxf.new("R2000")
        if units == "inch":
            doc.header["$INSUNITS"] = 1  # Inches
        else:
            doc.header["$INSUNITS"] = 4  # Millimeters
        msp = doc.modelspace()
        for path in paths:
            if not path or len(path) < 2:
                continue
            pts_2d = [(pt[0], pt[1]) for pt in path]
            msp.add_lwpolyline(pts_2d, close=True)
        doc.saveas(output_dxf_path)
        return True
    except ImportError:
        return _write_minimal_dxf_r12(paths, output_dxf_path)

def _write_minimal_dxf_r12(paths, output_dxf_path):
    """Fallback minimal ASCII DXF R12 writer when ezdxf is not installed."""
    lines = [
        "0", "SECTION",
        "2", "ENTITIES",
    ]
    for path in paths:
        if not path or len(path) < 2:
            continue
        for i in range(len(path) - 1):
            p1 = path[i]
            p2 = path[i + 1]
            lines.extend([
                "0", "LINE",
                "8", "0",
                "10", f"{p1[0]:.6f}",
                "20", f"{p1[1]:.6f}",
                "30", "0.000000",
                "11", f"{p2[0]:.6f}",
                "21", f"{p2[1]:.6f}",
                "31", "0.000000",
            ])
    lines.extend([
        "0", "ENDSEC",
        "0", "EOF",
        ""
    ])
    with open(output_dxf_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return True
