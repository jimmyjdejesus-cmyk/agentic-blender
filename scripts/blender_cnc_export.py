"""
Blender to Langmuir CNC Toolpath Generator & G-Code Post-Processor.
Runs headless in Blender via:
  blender --background [file.blend] --python scripts/blender_cnc_export.py -- [options]

Or imported inside Blender's interactive script editor.
"""

import sys
import os
import argparse
import math

try:
    import bpy
    import bmesh
    import mathutils
    IN_BLENDER = True
except ImportError:
    IN_BLENDER = False

def get_cli_args():
    """Extract arguments passed after '--' to Blender CLI."""
    if "--" in sys.argv:
        argv = sys.argv[sys.argv.index("--") + 1:]
    else:
        argv = []
    
    parser = argparse.ArgumentParser(description="Export Blender geometry to Langmuir FireControl G-code")
    parser.add_argument("--output-gcode", type=str, default="gcode/output_langmuir.nc", help="Output G-code file")
    parser.add_argument("--output-svg", type=str, default="dxf_svg/output_contour.svg", help="Output SVG profile")
    parser.add_argument("--machine", type=str, default="crossfire_pro", help="Machine profile (crossfire_pro / mr1_mill)")
    parser.add_argument("--material", type=str, default="14_gauge_mild_steel", help="Material preset")
    parser.add_argument("--feedrate", type=float, default=150.0, help="Cutting feed rate (IPM)")
    parser.add_argument("--pierce-delay", type=float, default=0.6, help="Pierce delay (seconds)")
    parser.add_argument("--create-sample", action="store_true", help="Generate a sample mechanical bracket part")
    return parser.parse_args(argv)

def create_sample_bracket():
    """Create a sample 2.5D mechanical mounting plate/bracket in Blender."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    
    # Create main plate (6" x 3" x 0.125")
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(3.0, 1.5, 0.0))
    bracket = bpy.context.active_object
    bracket.name = "Langmuir_Bracket"
    bracket.scale = (6.0, 3.0, 0.125)
    bpy.ops.object.transform_apply(scale=True)
    
    print("[Langmuir Agent] Created sample bracket plate: 6.0\" x 3.0\"")
    return bracket

def extract_loops_from_object(obj):
    """
    Extract 2D boundary polygons/loops projected onto the XY plane.
    Returns list of paths where each path is a list of (x, y) coordinates.
    """
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    mesh = eval_obj.to_mesh()
    
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.transform(bm, matrix=obj.matrix_world)
    
    # Find boundary edges or bottom edges (Z ~ min)
    # Collect 2D projection of bottom or outline vertices
    min_z = min(v.co.z for v in bm.verts) if bm.verts else 0.0
    
    paths = []
    # Identify faces facing down or XY planar cross section
    planar_faces = [f for f in bm.faces if abs(f.normal.z) > 0.8]
    
    if planar_faces:
        # Use first planar face boundary loop as cut path
        for face in planar_faces:
            if face.normal.z < 0: # bottom face
                pts = [(v.co.x, v.co.y) for v in face.verts]
                if pts:
                    pts.append(pts[0])  # Close loop
                    paths.append(pts)
                break
    
    if not paths:
        # Fallback: create bounding box boundary
        xs = [v.co.x for v in bm.verts]
        ys = [v.co.y for v in bm.verts]
        if xs and ys:
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            paths.append([
                (min_x, min_y),
                (max_x, min_y),
                (max_x, max_y),
                (min_x, max_y),
                (min_x, min_y)
            ])
            
    bm.free()
    eval_obj.to_mesh_clear()
    return paths

def generate_svg(paths, output_svg_path, scale=50):
    """Export 2D path list to SVG vector format."""
    os.makedirs(os.path.dirname(os.path.abspath(output_svg_path)), exist_ok=True)
    with open(output_svg_path, "w", encoding="utf-8") as f:
        f.write('<svg xmlns="http://www.w3.org/2000/svg" version="1.1">\n')
        f.write('  <g fill="none" stroke="red" stroke-width="2">\n')
        for loop in paths:
            pts_str = " ".join([f"{pt[0]*scale},{pt[1]*scale}" for pt in loop])
            f.write(f'    <polyline points="{pts_str}" />\n')
        f.write('  </g>\n')
        f.write('</svg>\n')
    print(f"[Langmuir Agent] Exported SVG contour to: {output_svg_path}")

def generate_firecontrol_gcode(paths, output_gcode_path, feedrate=150.0, pierce_delay=0.6, safe_z=1.0, pierce_height=0.15, cut_height=0.06):
    """
    Format G-code conforming directly to Langmuir FireControl plasma standards:
    - G90 (Absolute), G94 (Units/min), G20 (Inches)
    - G54 Coordinate origin
    - Initial Height Sensing (IHS) G38.2 probe touch-off routine
    - M3 (Torch On) / G4 P (Pierce Delay) / H1 (THC On)
    - Cut moves G1 X Y F...
    - H0 (THC Off) / M5 (Torch Off)
    - Safe Z retract & M30 end
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_gcode_path)), exist_ok=True)
    lines = [
        "(================================================)",
        "( Generated by Langmuir CNC Blender Agent        )",
        "( Controller: Langmuir Systems FireControl        )",
        "( Target: CrossFire PRO / XR Plasma CNC          )",
        "( Units: Inches (G20)                            )",
        "(================================================)",
        "G90 G94",
        "G20",
        "G54",
        f"G0 Z{safe_z:.4f}",
        ""
    ]
    
    cut_idx = 1
    for path in paths:
        if not path:
            continue
        start_x, start_y = path[0]
        lines.append(f"( --- Cut Profile {cut_idx} --- )")
        lines.append(f"G0 X{start_x:.4f} Y{start_y:.4f}")
        
        # Initial Height Sensing (IHS) Touch-off routine
        lines.append(f"G38.2 Z-5.0000 F60.0 (IHS Probe Material Contact)")
        lines.append(f"G92 Z0.0 (Set Z Work Coordinate Zero)")
        lines.append(f"G0 Z0.0200 (Switch Springback Compensation)")
        lines.append(f"G92 Z0.0")
        lines.append(f"G0 Z{pierce_height:.4f} (Rapid to Pierce Height)")
        
        # Torch Ignition
        lines.append(f"M3 (Plasma Torch ON)")
        lines.append(f"G4 P{pierce_delay:.2f} (Pierce Delay {pierce_delay}s)")
        lines.append(f"G1 Z{cut_height:.4f} F60.0 (Descend to Cut Height)")
        lines.append(f"H1 (Torch Height Control ON)")
        
        # Contour cut moves
        for pt in path[1:]:
            lines.append(f"G1 X{pt[0]:.4f} Y{pt[1]:.4f} F{feedrate:.1f}")
            
        # Torch Extinguish & Retract
        lines.append(f"H0 (Torch Height Control OFF)")
        lines.append(f"M5 (Plasma Torch OFF)")
        lines.append(f"G0 Z{safe_z:.4f} (Rapid to Safe Z Height)")
        lines.append("")
        cut_idx += 1
        
    lines.append("M30 (End of Program)")
    lines.append("")
    
    with open(output_gcode_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[Langmuir Agent] Successfully generated FireControl G-code: {output_gcode_path}")

def main():
    if not IN_BLENDER:
        print("[Error] This script must run inside Blender environment.")
        return
        
    args = get_cli_args()
    
    # If Blender scene has no mesh or sample requested, make sample bracket
    mesh_objs = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    if args.create_sample or not mesh_objs:
        target_obj = create_sample_bracket()
    else:
        target_obj = mesh_objs[0]
        print(f"[Langmuir Agent] Using existing object: {target_obj.name}")
        
    paths = extract_loops_from_object(target_obj)
    generate_svg(paths, args.output_svg)
    generate_firecontrol_gcode(
        paths=paths,
        output_gcode_path=args.output_gcode,
        feedrate=args.feedrate,
        pierce_delay=args.pierce_delay
    )

if __name__ == "__main__":
    main()
