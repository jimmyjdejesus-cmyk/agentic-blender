"""
FireControl G-Code Syntax & Envelope Validator.
Verifies compliance with Langmuir Systems machine safety and execution standards.
"""

import re
from .langmuir import get_machine_profile

def validate_firecontrol_gcode(gcode_text_or_path, machine_name="crossfire_pro"):
    """
    Scans G-code text or file against Langmuir FireControl requirements.
    Returns: {"valid": bool, "errors": list, "warnings": list, "stats": dict}
    """
    if gcode_text_or_path.endswith((".nc", ".tap", ".gcode", ".txt")):
        with open(gcode_text_or_path, "r", encoding="utf-8") as f:
            content = f.read()
    else:
        content = gcode_text_or_path

    profile = get_machine_profile(machine_name)
    envelope = profile.get("work_area", {"x": 33.3, "y": 48.0, "z": 3.0})
    is_plasma = (profile.get("type") == "plasma")

    errors = []
    warnings = []

    # 1. Header Checks
    if "G20" not in content and "G21" not in content:
        errors.append("Missing units modal declaration (G20 for inches or G21 for mm).")
    if "G90" not in content:
        warnings.append("G90 (Absolute Positioning) not explicitly set.")
    if "G54" not in content:
        warnings.append("G54 (Work Coordinate System) not declared.")

    # 2. Plasma Specific Controls
    if is_plasma:
        if "M3" not in content:
            errors.append("No torch ignition (M3) found in plasma program.")
        if "M5" not in content:
            errors.append("No torch extinguish (M5) found in plasma program.")
        if profile.get("thc_enabled"):
            if "H1" not in content or "H0" not in content:
                warnings.append("THC is enabled for machine, but H1/H0 control codes were not detected.")
        if profile.get("ihs_enabled"):
            if "G38.2" not in content:
                warnings.append("Initial Height Sensing (IHS) enabled, but G38.2 touch probe cycle not found.")

    # 3. Footer Check
    if "M30" not in content:
        errors.append("Missing program termination (M30).")

    # 4. Coordinate Limits Check
    x_coords = [float(m) for m in re.findall(r"X(-?\d+\.?\d*)", content)]
    y_coords = [float(m) for m in re.findall(r"Y(-?\d+\.?\d*)", content)]
    z_coords = [float(m) for m in re.findall(r"Z(-?\d+\.?\d*)", content)]

    min_x = min(x_coords) if x_coords else 0.0
    max_x = max(x_coords) if x_coords else 0.0
    min_y = min(y_coords) if y_coords else 0.0
    max_y = max(y_coords) if y_coords else 0.0

    if max_x > envelope["x"]:
        errors.append(f"X move ({max_x:.2f}) exceeds machine envelope limit ({envelope['x']} in).")
    if max_y > envelope["y"]:
        errors.append(f"Y move ({max_y:.2f}) exceeds machine envelope limit ({envelope['y']} in).")

    return {
        "valid": (len(errors) == 0),
        "machine": profile["name"],
        "errors": errors,
        "warnings": warnings,
        "envelope_bounds": {
            "x_range": (round(min_x, 3), round(max_x, 3)),
            "y_range": (round(min_y, 3), round(max_y, 3)),
            "work_area": envelope
        }
    }
