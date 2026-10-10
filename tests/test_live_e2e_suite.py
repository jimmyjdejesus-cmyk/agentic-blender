import os
import struct
import pytest
from agentic_blender.bridge.client import BlenderBridgeClient
from agentic_blender.cad.parametric import (
    generate_modular_dispenser_code,
    generate_cnc_bracket_code,
    generate_threaded_lip_code,
    generate_snap_fit_joint_code,
)
from agentic_blender.print3d.validator import analyze_mesh_topology, calculate_mass
from agentic_blender.cnc.langmuir import MACHINE_PROFILES
from agentic_blender.cnc.post_processor import (
    format_firecontrol_plasma_gcode,
    format_firecontrol_mr1_mill_gcode,
)
from agentic_blender.cnc.validator import validate_firecontrol_gcode
from agentic_blender.cnc.slicer import export_dxf_from_paths
from agentic_blender.harness.dsh_adapter import DshBlenderAdapter

@pytest.fixture(scope="module")
def bridge():
    client = BlenderBridgeClient()
    if not client.is_online():
        pytest.skip("Live Blender Bridge on port 9876 is offline.")
    return client

def test_bridge_connectivity(bridge):
    status = bridge.get_status()
    assert status.get("status") == "online"
    assert "blender_version" in status
    ver = status["blender_version"]
    assert ver[0] >= 5, f"Expected Blender 5+, got {ver}"

def test_live_cad_dispenser_cylinder(bridge):
    bridge.clear_scene()
    code = generate_modular_dispenser_code(base_shape="cylinder", radius=1.8, height=4.0)
    res = bridge.execute_bpy(code)
    assert res.get("success") is True, f"Execution failed: {res.get('error')}"

    scene = bridge.get_scene()
    names = [o["name"] for o in scene.get("objects", [])]
    assert "Dispenser_Main_Body" in names
    assert "Dry_Filter_Base" in names
    assert "Dosing_Holder_Standard_0.1g" in names
    assert "Dosing_Holder_Micro_25mg" in names
    assert "Knurled_Airtight_Lid" in names

def test_live_cad_dispenser_hexagon(bridge):
    bridge.clear_scene()
    code = generate_modular_dispenser_code(base_shape="hexagon", radius=2.0, height=3.5)
    res = bridge.execute_bpy(code)
    assert res.get("success") is True, f"Execution failed: {res.get('error')}"

    scene = bridge.get_scene()
    names = [o["name"] for o in scene.get("objects", [])]
    assert "Dispenser_Main_Body" in names
    assert "Dry_Filter_Base" in names

def test_live_cad_dispenser_rectangle(bridge):
    bridge.clear_scene()
    code = generate_modular_dispenser_code(base_shape="rectangle", radius=2.2, height=4.5)
    res = bridge.execute_bpy(code)
    assert res.get("success") is True, f"Execution failed: {res.get('error')}"

    scene = bridge.get_scene()
    names = [o["name"] for o in scene.get("objects", [])]
    assert "Dispenser_Main_Body" in names
    assert "Knurled_Airtight_Lid" in names

def test_live_cad_threaded_lip(bridge):
    bridge.clear_scene()
    code = generate_threaded_lip_code(radius=1.8, pitch=0.2, turns=3)
    res = bridge.execute_bpy(code)
    assert res.get("success") is True, f"Execution failed: {res.get('error')}"

    scene = bridge.get_scene()
    names = [o["name"] for o in scene.get("objects", [])]
    assert "Thread_Base_Core" in names
    helix_nodes = [n for n in names if n.startswith("Helix_Node_")]
    assert len(helix_nodes) > 0

def test_live_cad_snap_fit_joint(bridge):
    bridge.clear_scene()
    code = generate_snap_fit_joint_code(radius=1.8, count=4)
    res = bridge.execute_bpy(code)
    assert res.get("success") is True, f"Execution failed: {res.get('error')}"

    scene = bridge.get_scene()
    names = [o["name"] for o in scene.get("objects", [])]
    assert "Snap_Fit_Collar" in names
    snap_tabs = [n for n in names if n.startswith("Snap_Tab_")]
    assert len(snap_tabs) == 4

def test_live_3dprint_preflight_and_stl_export(bridge, tmp_path):
    # Setup a clean model in live Blender
    bridge.clear_scene()
    setup_code = """
import bpy
bpy.ops.mesh.primitive_cylinder_add(radius=1.5, depth=3.0, location=(0, 0, 1.5))
obj = bpy.context.active_object
obj.name = "Test_Print_Body"
"""
    res = bridge.execute_bpy(setup_code)
    assert res.get("success") is True

    # Run in-Blender topology and export script
    export_stl_path = str(tmp_path / "Test_Print_Body.stl")
    stl_code = f"""
import bpy
import bmesh
import json

obj = bpy.data.objects.get("Test_Print_Body")
bpy.context.view_layer.objects.active = obj
bpy.ops.object.select_all(action='DESELECT')
obj.select_set(True)

bm = bmesh.new()
bm.from_mesh(obj.data)
non_manifold = sum(1 for e in bm.edges if not e.is_manifold)
vol_m3 = abs(bm.calc_volume())
vol_cm3 = vol_m3 * 1e6
bm.free()

if hasattr(bpy.ops.wm, "stl_export"):
    bpy.ops.wm.stl_export(filepath=r"{export_stl_path}", export_selected_objects=True)
else:
    bpy.ops.export_mesh.stl(filepath=r"{export_stl_path}", use_selection=True)

print(json.dumps({{"non_manifold": non_manifold, "vol_cm3": vol_cm3}}))
"""
    export_res = bridge.execute_bpy(stl_code)
    assert export_res.get("success") is True

    # Validate output STL on disk
    assert os.path.exists(export_stl_path)
    file_size = os.path.getsize(export_stl_path)
    assert file_size >= 84  # 80-byte header + 4-byte triangle count

    with open(export_stl_path, "rb") as f:
        header = f.read(80)
        tri_bytes = f.read(4)
        tri_count = struct.unpack("<I", tri_bytes)[0]
        assert tri_count > 0, "STL must contain triangles"

    # Validate material mass calculations
    pla_mass = calculate_mass(25.0, "pla")
    petg_mass = calculate_mass(25.0, "petg")
    abs_mass = calculate_mass(25.0, "abs")
    assert round(pla_mass, 1) == 31.0
    assert round(petg_mass, 1) == 31.8
    assert round(abs_mass, 1) == 26.0

def test_live_cnc_dxf_and_firecontrol_plasma_gcode(tmp_path):
    # Slicing planar geometry
    square_contour = [
        [(0.0, 0.0), (4.0, 0.0), (4.0, 3.0), (0.0, 3.0), (0.0, 0.0)]
    ]
    
    dxf_path = str(tmp_path / "Test_Plate.dxf")
    export_dxf_from_paths(square_contour, dxf_path)
    assert os.path.exists(dxf_path)
    assert os.path.getsize(dxf_path) > 100

    # Read back DXF with ezdxf
    ezdxf = pytest.importorskip("ezdxf")
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    polylines = msp.query("LWPOLYLINE")
    assert len(polylines) == 1

    # Generate FireControl Plasma G-code for 14ga mild steel
    gcode = format_firecontrol_plasma_gcode(
        paths=square_contour,
        material_name="14_gauge_mild_steel",
        machine_name="crossfire_pro",
        lead_in=True,
        lead_in_distance=0.150
    )
    assert "G90 G94" in gcode
    assert "G20" in gcode
    assert "G54" in gcode
    assert "G38.2 Z-5.0" in gcode
    assert "G92 Z0.0" in gcode
    assert "G0 Z0.1500" in gcode  # Pierce height
    assert "G4 P0.60" in gcode    # Pierce delay
    assert "G1 Z0.0600" in gcode  # Cut height
    assert "M3" in gcode          # Torch fire
    assert "H1" in gcode          # THC On
    assert "F150.0" in gcode      # Cut speed IPM
    assert "H0" in gcode          # THC Off
    assert "M5" in gcode          # Torch off
    assert "M30" in gcode         # End program

    # Bounds validation against CrossFire PRO work envelope (33.3" x 48.0")
    val = validate_firecontrol_gcode(gcode, machine_name="crossfire_pro")
    assert val["valid"] is True
    assert val["errors"] == []

def test_live_cnc_mr1_mill_gcode():
    pass_data = {
        "z": -0.05,
        "feed": 45.0,
        "points": [(1.0, 1.0), (5.0, 1.0), (5.0, 4.0), (1.0, 4.0), (1.0, 1.0)]
    }
    gcode = format_firecontrol_mr1_mill_gcode(
        passes=[pass_data],
        spindle_rpm=8000
    )
    assert "M3 S8000" in gcode
    assert "M8" in gcode  # Coolant on
    assert "F45.0" in gcode
    assert "M9" in gcode  # Coolant off
    assert "M5" in gcode  # Spindle off
    assert "M30" in gcode

    val = validate_firecontrol_gcode(gcode, machine_name="mr1_mill")
    assert val["valid"] is True
    assert val["errors"] == []

def test_live_dsh_adapter_roundtrip():
    adapter = DshBlenderAdapter()
    
    # 1. CAD generation
    cad_res = adapter.dispatch_tool("blender_cad_generate", {
        "type": "dispenser",
        "baseShape": "cylinder"
    })
    assert "code" in cad_res
    assert "Dispenser_Main_Body" in cad_res["code"]

    # 2. 3D Print Pre-Flight
    check_res = adapter.dispatch_tool("blender_3dprint_preflight", {
        "nonManifoldEdges": 0,
        "volumeCm3": 42.5,
        "dimensionsMm": {"x": 50, "y": 50, "z": 90},
        "material": "pla",
        "printer": "bambu_x1c"
    })
    assert check_res["is_printable"] is True
    assert check_res["is_watertight"] is True
    assert check_res["metrics"]["estimated_mass_g"] == 52.7

    # 3. Langmuir G-code
    gcode_res = adapter.dispatch_tool("blender_cnc_postprocess", {
        "material": "14_gauge_mild_steel",
        "machine": "crossfire_pro",
        "paths": [[(0, 0), (2, 0), (2, 2), (0, 0)]]
    })
    assert "gcode" in gcode_res
    assert "G38.2" in gcode_res["gcode"]
    assert "F150.0" in gcode_res["gcode"]
