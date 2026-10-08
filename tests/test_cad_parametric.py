import pytest
from agentic_blender.cad.parametric import (
    generate_modular_dispenser_code,
    generate_cnc_bracket_code,
    generate_threaded_lip_code,
    generate_snap_fit_joint_code,
)

def test_generate_modular_dispenser_cylinder():
    code = generate_modular_dispenser_code(base_shape="cylinder", radius=2.0, height=4.5)
    assert "vertices=32" in code
    assert "Dispenser_Main_Body" in code
    assert "Dry_Filter_Base" in code
    assert "Dosing_Holder_Standard_0.1g" in code
    assert "Dosing_Holder_Micro_25mg" in code
    assert "Knurled_Airtight_Lid" in code
    assert "Cavity" in code

def test_generate_modular_dispenser_hexagon():
    code = generate_modular_dispenser_code(base_shape="hexagon", radius=2.0)
    assert "vertices=6" in code
    assert "Dispenser_Main_Body" in code

def test_generate_modular_dispenser_rectangle():
    code = generate_modular_dispenser_code(base_shape="rectangle", radius=2.0)
    assert "vertices=4" in code
    assert "Dispenser_Main_Body" in code

def test_generate_cnc_bracket_code():
    code = generate_cnc_bracket_code(length=6.0, width=3.0, thickness=0.25)
    assert "Langmuir_CNC_Mounting_Plate" in code
    assert "plate.scale = (length, width, thickness)" in code
    assert "length = 6.0" in code
    assert "width = 3.0" in code
    assert "thickness = 0.25" in code
    assert "Fillet" in code
    assert "Hole" in code

def test_generate_threaded_lip_code_default():
    code = generate_threaded_lip_code()
    assert "Threaded_Lip_Outer" in code
    assert "radius = 1.8" in code
    assert "pitch = 0.2" in code
    assert "thread_depth = 0.08" in code
    assert "is_outer = True" in code
    assert "turns = 3.0" in code
    assert "bmesh" in code
    assert "bm.faces.new" in code

def test_generate_threaded_lip_code_inner_custom():
    code = generate_threaded_lip_code(
        radius=2.2,
        height=0.75,
        pitch=0.3,
        thread_depth=0.12,
        is_outer=False,
        turns=4.0
    )
    assert "Threaded_Lip_Inner" in code
    assert "radius = 2.2" in code
    assert "height = 0.75" in code
    assert "pitch = 0.3" in code
    assert "thread_depth = 0.12" in code
    assert "is_outer = False" in code
    assert "turns = 4.0" in code

def test_generate_snap_fit_joint_code_default():
    code = generate_snap_fit_joint_code()
    assert "Snap_Fit_Male" in code
    assert "Snap_Fit_Female" in code
    assert "Snap_Tab_Male" in code
    assert "Snap_Latch_Male" in code
    assert "radius = 1.8" in code
    assert "tab_count = 4" in code
    assert "tab_width = 0.3" in code
    assert "cantilever_thickness = 0.08" in code
    assert "MatingCavity" in code

def test_generate_snap_fit_joint_code_custom():
    code = generate_snap_fit_joint_code(
        radius=2.5,
        tab_count=6,
        tab_width=0.4,
        tab_height=0.6,
        cantilever_thickness=0.1,
        latch_depth=0.06,
        clearance=0.03
    )
    assert "Snap_Fit_Male" in code
    assert "Snap_Fit_Female" in code
    assert "radius = 2.5" in code
    assert "tab_count = 6" in code
    assert "tab_width = 0.4" in code
    assert "tab_height = 0.6" in code
    assert "cantilever_thickness = 0.1" in code
    assert "latch_depth = 0.06" in code
    assert "clearance = 0.03" in code
