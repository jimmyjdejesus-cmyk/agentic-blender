import pytest
from agentic_blender.harness.dsh_adapter import DshBlenderAdapter

def test_dsh_adapter_init():
    adapter = DshBlenderAdapter()
    assert adapter.host == "127.0.0.1"
    assert adapter.port == 9876

def test_dsh_adapter_tool_dispatch():
    adapter = DshBlenderAdapter()
    
    # Tool: blender_cad_generate (dispenser)
    res_cad = adapter.dispatch_tool("blender_cad_generate", {"type": "dispenser", "baseShape": "hexagon"})
    assert "code" in res_cad
    assert "vertices=6" in res_cad["code"]

    # Tool: blender_cad_generate (threaded_lip)
    res_thread = adapter.dispatch_tool("blender_cad_generate", {"type": "threaded_lip", "pitch": 0.25, "isOuter": True})
    assert "code" in res_thread
    assert "Threaded_Lip_Outer" in res_thread["code"]
    assert "pitch = 0.25" in res_thread["code"]

    # Tool: blender_cad_generate (snap_fit_joint)
    res_snap = adapter.dispatch_tool("blender_cad_generate", {"type": "snap_fit_joint", "tabCount": 6})
    assert "code" in res_snap
    assert "Snap_Fit_Male" in res_snap["code"]
    assert "tab_count = 6" in res_snap["code"]

    # Tool: blender_3dprint_preflight
    res_print = adapter.dispatch_tool("blender_3dprint_preflight", {
        "nonManifoldEdges": 0,
        "volumeCm3": 20.0,
        "material": "pla"
    })
    assert res_print["is_printable"] is True
    assert res_print["is_watertight"] is True

    # Tool: blender_cnc_postprocess
    res_cnc = adapter.dispatch_tool("blender_cnc_postprocess", {
        "paths": [[(0, 0), (2, 0), (2, 2), (0, 0)]],
        "machine": "crossfire_pro"
    })
    assert "G38.2" in res_cnc["gcode"]
    assert "M3" in res_cnc["gcode"]

def test_dsh_adapter_unknown_tool():
    adapter = DshBlenderAdapter()
    with pytest.raises(ValueError, match="Unknown tool"):
        adapter.dispatch_tool("nonexistent_tool")
