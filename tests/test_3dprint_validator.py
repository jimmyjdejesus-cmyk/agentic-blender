import pytest
from agentic_blender.print3d.validator import analyze_mesh_topology

def test_watertight_manifold_mesh():
    res = analyze_mesh_topology(
        vertex_count=1000,
        edge_count=2000,
        face_count=1000,
        non_manifold_edges=0,
        zero_area_faces=0,
        inverted_normals=0,
        bounding_box_mm=(50.0, 50.0, 60.0),
        volume_cm3=30.0,
        material="pla",
        printer_profile="bambu_x1c"
    )
    assert res["is_printable"] is True
    assert res["is_watertight"] is True
    assert len(res["errors"]) == 0
    assert res["metrics"]["estimated_mass_g"] == round(30.0 * 1.24, 2)
    assert res["metrics"]["fits_build_plate"] is True

def test_non_manifold_detection():
    res = analyze_mesh_topology(
        vertex_count=500,
        edge_count=1000,
        face_count=500,
        non_manifold_edges=12,
        bounding_box_mm=(40.0, 40.0, 40.0),
        volume_cm3=15.0
    )
    assert res["is_printable"] is False
    assert res["is_watertight"] is False
    assert any("non-manifold" in err.lower() for err in res["errors"])

def test_build_plate_overflow():
    res = analyze_mesh_topology(
        vertex_count=2000,
        edge_count=4000,
        face_count=2000,
        non_manifold_edges=0,
        bounding_box_mm=(300.0, 300.0, 300.0),  # Exceeds Bambu X1C 256mm
        printer_profile="bambu_x1c"
    )
    assert res["is_printable"] is False
    assert any("exceeds maximum build envelope" in err.lower() for err in res["errors"])

def test_material_densities():
    res_alu = analyze_mesh_topology(
        vertex_count=100, edge_count=200, face_count=100,
        volume_cm3=10.0, material="aluminum"
    )
    assert res_alu["metrics"]["estimated_mass_g"] == 27.0
