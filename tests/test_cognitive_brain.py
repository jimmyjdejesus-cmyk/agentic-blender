"""End-to-end data flow and unit tests for System 1 + System 2 Brain and Google Stitch workflow."""

import pytest
from agentic_blender.llm.cognitive_brain import (
    DualBrainOrchestrator,
    System1Brain,
)
from agentic_blender.harness.dsh_adapter import DshBlenderAdapter


def test_system1_parse_intent_dimensions_and_theme():
    intent = System1Brain.parse_intent(
        "Create a hexagon powder canister with radius 2.5 and height 6.0 wall 0.3 in brushed titanium with 3 variations"
    )
    assert intent.archetype == "canister"
    assert intent.shape == "hexagon"
    assert intent.radius == 2.5
    assert intent.height == 6.0
    assert intent.wall == 0.3
    assert intent.theme == "brushed_titanium"
    assert intent.variations == 3


def test_system1_parse_intent_cnc_bracket():
    intent = System1Brain.parse_intent("Design a Langmuir CNC mounting bracket plate with 8 holes")
    assert intent.archetype == "bracket"
    assert intent.theme == "plasma_steel"
    assert intent.hole_count == 8


def test_stitch_three_variations_ast_valid():
    code = System1Brain.generate_Stitch_variations_code("canister", base_radius=1.8, base_height=4.0, wall=0.25)
    valid, msg = DualBrainOrchestrator.validate_python_ast(code)
    assert valid, msg
    assert "Variant_A_Cylinder" in code
    assert "Variant_B_Hexagon" in code
    assert "Variant_C_Rectangle" in code


@pytest.mark.parametrize(
    "chip_action",
    ["explode", "assemble", "chamfer", "hollow", "bolt_pattern", "theme:brushed_titanium", "theme:matte_carbon"],
)
def test_stitch_refinement_chips_ast_valid(chip_action):
    code = System1Brain.generate_refinement_code(chip_action)
    valid, msg = DualBrainOrchestrator.validate_python_ast(code)
    assert valid, msg


def test_dual_brain_loads_design_md_and_builds_system2_prompt():
    orch = DualBrainOrchestrator()
    tokens = orch.load_design_tokens()
    assert "DESIGN.md" in tokens
    assert "Langmuir CrossFire PRO" in tokens

    intent = System1Brain.parse_intent("Hexagon enclosure radius 2.0")
    full_prompt = orch.build_system2_prompt("Hexagon enclosure radius 2.0", intent, "SYSTEM_HEADER")
    assert "SYSTEM_HEADER" in full_prompt
    assert "DESIGN.MD ENGINEERING TOKENS" in full_prompt
    assert "SYSTEM 1 PARSED INTENT" in full_prompt
    assert "shape: hexagon" in full_prompt.lower()


def test_full_application_data_flow():
    """Verify full data flow: Prompt -> System 1 Intent -> DSH CAD Gen -> 3D Print Pre-flight -> CNC Post-processor."""
    intent = System1Brain.parse_intent("Modular hexagon canister radius 2.0 height 4.5")
    adapter = DshBlenderAdapter()

    # Step 1: CAD Generation
    cad_res = adapter.dispatch_tool(
        "blender_cad_generate",
        {"type": "dispenser", "baseShape": intent.shape, "executeLive": False},
    )
    assert "import bpy" in cad_res["code"]
    valid, _ = DualBrainOrchestrator.validate_python_ast(cad_res["code"])
    assert valid

    # Step 2: 3D Print Pre-Flight
    print_res = adapter.dispatch_tool(
        "blender_3dprint_preflight",
        {
            "vertexCount": 1200,
            "edgeCount": 2400,
            "faceCount": 1200,
            "nonManifoldEdges": 0,
            "zeroAreaFaces": 0,
            "invertedNormals": 0,
            "dimensionsMm": [intent.radius * 50.8, intent.radius * 50.8, intent.height * 25.4],
            "volumeCm3": 42.5,
            "material": "petg",
            "printer": "bambu_x1c",
        },
    )
    assert print_res["is_printable"] is True
    assert print_res["is_watertight"] is True
    assert print_res["metrics"]["estimated_mass_g"] > 0

    # Step 3: Langmuir CNC G-Code Generation
    cnc_res = adapter.dispatch_tool(
        "blender_cnc_postprocess",
        {
            "paths": [[(0.0, 0.0), (4.0, 0.0), (4.0, 3.0), (0.0, 3.0), (0.0, 0.0)]],
            "machine": "crossfire_pro",
            "material": "14_gauge_mild_steel",
        },
    )
    assert "G38.2" in cnc_res["gcode"]
    assert "H1" in cnc_res["gcode"]
    assert "M30" in cnc_res["gcode"]
