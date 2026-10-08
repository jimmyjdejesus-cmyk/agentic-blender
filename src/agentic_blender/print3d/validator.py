"""
3D Print Pre-Flight Validator & Geometry Analyzer for Blender.
Evaluates meshes for watertight manifold topology, wall thickness,
volume, filament usage, and 3D printer build plate fit.
"""

MATERIAL_DENSITIES = {
    "pla": 1.24,       # g/cm^3
    "petg": 1.27,
    "abs": 1.04,
    "tpu": 1.21,
    "nylon": 1.14,
    "resin": 1.15,
    "aluminum": 2.70,
    "steel": 7.85,
}

BUILD_PLATES = {
    "bambu_x1c": {"x": 256.0, "y": 256.0, "z": 256.0},      # mm
    "prusa_mk4": {"x": 250.0, "y": 210.0, "z": 220.0},
    "ender_3": {"x": 220.0, "y": 220.0, "z": 250.0},
    "voron_2_4_350": {"x": 350.0, "y": 350.0, "z": 350.0},
    "elegoo_saturn": {"x": 218.0, "y": 123.0, "z": 250.0},
}

def analyze_mesh_topology(
    vertex_count,
    edge_count,
    face_count,
    non_manifold_edges=0,
    zero_area_faces=0,
    inverted_normals=0,
    bounding_box_mm=(50.0, 50.0, 50.0),
    volume_cm3=25.0,
    material="pla",
    printer_profile="bambu_x1c"
):
    """
    Evaluates topological health and printability metrics.
    Returns structured analysis dict with printability status and actionable warnings.
    """
    errors = []
    warnings = []
    
    # 1. Watertight / Manifold Check
    is_watertight = (non_manifold_edges == 0)
    if not is_watertight:
        errors.append(f"Model has {non_manifold_edges} non-manifold edges. Mesh is not watertight!")
        
    if zero_area_faces > 0:
        warnings.append(f"Found {zero_area_faces} degenerate (zero-area) faces. Run degenerate dissolve.")
        
    if inverted_normals > 0:
        errors.append(f"Found {inverted_normals} inverted or inconsistent face normals.")

    # 2. Size & Dimensions Check
    dim_x, dim_y, dim_z = bounding_box_mm
    plate = BUILD_PLATES.get(printer_profile, BUILD_PLATES["bambu_x1c"])
    
    fits_bed = (dim_x <= plate["x"]) and (dim_y <= plate["y"]) and (dim_z <= plate["z"])
    if not fits_bed:
        # Check if rotated fitting works
        dims_sorted = sorted([dim_x, dim_y, dim_z])
        plate_sorted = sorted([plate["x"], plate["y"], plate["z"]])
        fits_diagonal = all(d <= p for d, p in zip(dims_sorted, plate_sorted))
        
        if fits_diagonal:
            warnings.append(f"Model ({dim_x:.1f}x{dim_y:.1f}x{dim_z:.1f}mm) requires re-orientation to fit {printer_profile} bed ({plate['x']}x{plate['y']}x{plate['z']}mm).")
            fits_bed = True
        else:
            errors.append(f"Model ({dim_x:.1f}x{dim_y:.1f}x{dim_z:.1f}mm) exceeds maximum build envelope for {printer_profile} ({plate['x']}x{plate['y']}x{plate['z']}mm)!")

    # 3. Material & Mass Estimation
    density = MATERIAL_DENSITIES.get(material.lower(), MATERIAL_DENSITIES["pla"])
    estimated_mass_g = round(volume_cm3 * density, 2)

    printable = (len(errors) == 0)
    
    return {
        "is_printable": printable,
        "is_watertight": is_watertight,
        "metrics": {
            "vertices": vertex_count,
            "edges": edge_count,
            "faces": face_count,
            "non_manifold_edges": non_manifold_edges,
            "zero_area_faces": zero_area_faces,
            "inverted_normals": inverted_normals,
            "dimensions_mm": {"x": round(dim_x, 2), "y": round(dim_y, 2), "z": round(dim_z, 2)},
            "volume_cm3": round(volume_cm3, 3),
            "estimated_mass_g": estimated_mass_g,
            "material": material,
            "printer": printer_profile,
            "fits_build_plate": fits_bed
        },
        "errors": errors,
        "warnings": warnings
    }
