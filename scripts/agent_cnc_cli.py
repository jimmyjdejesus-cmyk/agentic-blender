"""
Langmuir CNC Agent CLI & Pipeline Orchestrator.
Automates Blender CAD-to-CAM workflow directly for Langmuir Systems CNC machines.
"""

import os
import sys
import subprocess
import argparse
from langmuir_config import MACHINE_PROFILES

BLENDER_EXE = r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
FIRECONTROL_EXE = r"C:\Users\jimmy\AppData\Local\FireControl\FireControl.exe"

def validate_gcode(file_path, machine_name="crossfire_pro"):
    """Validates that the output file meets Langmuir FireControl standards."""
    profile = MACHINE_PROFILES.get(machine_name, {})
    if not os.path.exists(file_path):
        return False, f"File not found: {file_path}"
        
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    errors = []
    warnings = []
    
    if "G20" not in content and "G21" not in content:
        errors.append("Missing units declaration (G20/G21).")
    if "M3" not in content:
        warnings.append("No torch ignition (M3) found.")
    if "M5" not in content:
        warnings.append("No torch extinguish (M5) found.")
    if profile.get("thc_enabled") and ("H1" not in content or "H0" not in content):
        warnings.append("THC is enabled for this profile, but H1/H0 commands were not detected.")
    if "M30" not in content:
        errors.append("Missing end of program code (M30).")
        
    status = len(errors) == 0
    return status, {"errors": errors, "warnings": warnings}

def run_blender_export(blend_file=None, output_nc="gcode/part.nc", output_svg="dxf_svg/part.svg",
                       machine="crossfire_pro", material="14_gauge_mild_steel", create_sample=False):
    """Executes Blender in headless background mode using blender_cnc_export.py."""
    script_path = os.path.join(os.path.dirname(__file__), "blender_cnc_export.py")
    
    profile = MACHINE_PROFILES.get(machine, MACHINE_PROFILES["crossfire_pro"])
    mat_presets = profile.get("material_presets", {}).get(material, {})
    
    feedrate = mat_presets.get("cut_feed_rate", 150.0)
    delay = mat_presets.get("pierce_delay", 0.6)
    
    cmd = [
        BLENDER_EXE,
        "--background"
    ]
    if blend_file and os.path.exists(blend_file):
        cmd.append(blend_file)
        
    cmd.extend([
        "--python", script_path,
        "--",
        "--output-gcode", output_nc,
        "--output-svg", output_svg,
        "--machine", machine,
        "--material", material,
        "--feedrate", str(feedrate),
        "--pierce-delay", str(delay)
    ])
    
    if create_sample or not blend_file:
        cmd.append("--create-sample")
        
    print(f"\n[Agentic CNC] Running Blender in headless mode...")
    print(f"Machine: {profile['name']} | Material: {material} ({feedrate} IPM, {delay}s delay)")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("[Error] Blender execution failed:")
        print(result.stderr)
        return False
        
    print(result.stdout)
    
    # Run validation
    ok, report = validate_gcode(output_nc, machine)
    print("\n[Validation Report]")
    if ok:
        print("  [OK] G-code structure is valid for Langmuir FireControl.")
    else:
        print("  [FAIL] Errors:", report["errors"])
    if report["warnings"]:
        print("  [WARN] Warnings:", report["warnings"])
        
    return ok

def launch_firecontrol():
    """Launch Langmuir Systems FireControl machine controller."""
    if os.path.exists(FIRECONTROL_EXE):
        print(f"[Agentic CNC] Launching FireControl from {FIRECONTROL_EXE}...")
        subprocess.Popen([FIRECONTROL_EXE])
    else:
        print(f"[Error] FireControl not found at {FIRECONTROL_EXE}")

def main():
    parser = argparse.ArgumentParser(description="Langmuir CNC Agent Toolpath Orchestrator")
    parser.add_argument("--model", type=str, default=None, help="Path to .blend model file")
    parser.add_argument("--machine", type=str, default="crossfire_pro", choices=list(MACHINE_PROFILES.keys()), help="Langmuir machine profile")
    parser.add_argument("--material", type=str, default="14_gauge_mild_steel", help="Material preset")
    parser.add_argument("--out-nc", type=str, default="gcode/langmuir_output.nc", help="Output .nc file")
    parser.add_argument("--out-svg", type=str, default="dxf_svg/langmuir_contour.svg", help="Output .svg file")
    parser.add_argument("--sample", action="store_true", help="Generate a sample test part")
    parser.add_argument("--open-firecontrol", action="store_true", help="Launch FireControl after generation")
    
    args = parser.parse_args()
    
    success = run_blender_export(
        blend_file=args.model,
        output_nc=args.out_nc,
        output_svg=args.out_svg,
        machine=args.machine,
        material=args.material,
        create_sample=args.sample
    )
    
    if success and args.open_firecontrol:
        launch_firecontrol()

if __name__ == "__main__":
    main()
