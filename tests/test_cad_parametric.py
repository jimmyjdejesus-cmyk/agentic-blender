import pytest
from agentic_blender.cad.parametric import (
    generate_modular_dispenser_code,
    generate_cnc_bracket_code,
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

def test_generate_threaded_lip_code():
    from agentic_blender.cad.parametric import generate_threaded_lip_code
    code = generate_threaded_lip_code(radius=2.0, pitch=0.2, turns=4)
    assert "Thread_Base_Core" in code
    assert "Helix_Node_" in code
    assert "pitch = 0.2" in code
    assert "turns = 4" in code

def test_generate_snap_fit_joint_code():
    from agentic_blender.cad.parametric import generate_snap_fit_joint_code
    code = generate_snap_fit_joint_code(radius=1.5, count=6)
    assert "Snap_Fit_Collar" in code
    assert "Snap_Tab_" in code
    assert "count = 6" in code
