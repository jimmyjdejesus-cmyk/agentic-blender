import pytest
from agentic_blender.cnc.post_processor import (
    format_firecontrol_plasma_gcode,
    format_firecontrol_mr1_mill_gcode,
)
from agentic_blender.cnc.validator import validate_firecontrol_gcode

def test_plasma_gcode_formatting():
    path = [(0.0, 0.0), (5.0, 0.0), (5.0, 3.0), (0.0, 3.0), (0.0, 0.0)]
    gcode = format_firecontrol_plasma_gcode(
        paths=[path],
        machine_name="crossfire_pro",
        material_name="14_gauge_mild_steel"
    )

    # Check modal headers
    assert "G90 G94" in gcode
    assert "G20" in gcode
    assert "G54" in gcode

    # Check IHS probe sequence
    assert "G38.2 Z-5.0000" in gcode
    assert "G92 Z0.0" in gcode

    # Check torch ignite & pierce dwell
    assert "M3 (Torch Fire ON)" in gcode
    assert "G4 P0.60" in gcode
    assert "H1 (Torch Height Control ON)" in gcode

    # Check cut motion & feed
    assert "Lead-in Cut" in gcode
    assert "G1 X5.0000 Y0.0000 F150.0" in gcode

    # Check torch off & retract
    assert "H0 (Torch Height Control OFF)" in gcode
    assert "M5 (Torch Extinguish OFF)" in gcode
    assert "M30 (End of Program)" in gcode

def test_mr1_mill_gcode_formatting():
    pass_data = {
        "z": -0.05,
        "feed": 45.0,
        "points": [(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 0.0)]
    }
    gcode = format_firecontrol_mr1_mill_gcode([pass_data], spindle_rpm=6500)
    assert "M3 S6500" in gcode
    assert "M8" in gcode
    assert "G1 Z-0.0500" in gcode
    assert "M9" in gcode
    assert "M5" in gcode
    assert "M30" in gcode

def test_gcode_validator_valid():
    path = [(0.0, 0.0), (4.0, 0.0), (4.0, 2.0), (0.0, 0.0)]
    gcode = format_firecontrol_plasma_gcode([path])
    res = validate_firecontrol_gcode(gcode, machine_name="crossfire_pro")
    assert res["valid"] is True
    assert len(res["errors"]) == 0

def test_gcode_validator_out_of_bounds():
    # CrossFire PRO X envelope is 33.3 in. A move to X=40.0 should error.
    bad_gcode = """
    G90 G94 G20 G54
    M3
    G1 X40.000 Y5.000 F100.0
    M5
    M30
    """
    res = validate_firecontrol_gcode(bad_gcode, machine_name="crossfire_pro")
    assert res["valid"] is False
    assert any("exceeds machine envelope limit" in err for err in res["errors"])
