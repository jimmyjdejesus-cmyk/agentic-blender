"""
Command Line Interface for Agentic Blender.
"""

import sys
import os
import argparse
import json
from .bridge.client import BlenderBridgeClient
from .cad.parametric import (
    generate_modular_dispenser_code,
    generate_cnc_bracket_code,
    generate_threaded_lip_code,
    generate_snap_fit_joint_code,
)
from .print3d.validator import analyze_mesh_topology
from .cnc.post_processor import format_firecontrol_plasma_gcode
from .cnc.validator import validate_firecontrol_gcode

def main():
    parser = argparse.ArgumentParser(
        prog="agentic-blender",
        description="Autonomous CAD, 3D Printing & CNC Manufacturing Engine"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # 1. Status command
    subparsers.add_parser("status", help="Check live Blender bridge status")

    # 2. Scene command
    subparsers.add_parser("scene", help="Get summary of objects in active Blender scene")

    # 3. Prompt / CAD command
    cad_parser = subparsers.add_parser("cad", help="Generate parametric CAD models")
    cad_parser.add_argument("--type", choices=["dispenser", "bracket", "threaded_lip", "snap_fit_joint"], default="dispenser", help="CAD archetype")
    cad_parser.add_argument("--shape", choices=["cylinder", "hexagon", "rectangle"], default="cylinder", help="Base shape")
    cad_parser.add_argument("--execute", action="store_true", help="Execute directly in live Blender session")
    cad_parser.add_argument("--out-script", type=str, help="Save generated script to file")

    # 4. 3D Print command
    print_parser = subparsers.add_parser("print3d", help="3D printing validation & pre-flight checks")
    print_parser.add_argument("--check-sample", action="store_true", help="Run topology check on sample mesh")
    print_parser.add_argument("--printer", default="bambu_x1c", help="Printer profile (bambu_x1c, prusa_mk4, ender_3)")
    print_parser.add_argument("--material", default="pla", help="Filament material (pla, petg, abs, tpu)")

    # 5. CNC command
    cnc_parser = subparsers.add_parser("cnc", help="CNC Machining & FireControl post-processing")
    cnc_parser.add_argument("--validate", type=str, help="Path to G-code file to validate")
    cnc_parser.add_argument("--machine", default="crossfire_pro", help="Langmuir machine profile")
    cnc_parser.add_argument("--material", default="14_gauge_mild_steel", help="Material cut chart preset")

    args = parser.parse_args()

    client = BlenderBridgeClient()

    if args.command == "status":
        online = client.is_online()
        if online:
            print("[OK] Live Blender Bridge is ONLINE.")
            print(json.dumps(client.get_status(), indent=2))
        else:
            print("[OFFLINE] Blender bridge is not reachable on http://127.0.0.1:9876.")

    elif args.command == "scene":
        if not client.is_online():
            print("[Error] Blender bridge is offline.")
            sys.exit(1)
        print(json.dumps(client.get_scene(), indent=2))

    elif args.command == "cad":
        if args.type == "dispenser":
            code = generate_modular_dispenser_code(base_shape=args.shape)
        elif args.type == "threaded_lip":
            code = generate_threaded_lip_code()
        elif args.type == "snap_fit_joint":
            code = generate_snap_fit_joint_code()
        else:
            code = generate_cnc_bracket_code()

        if args.out_script:
            with open(args.out_script, "w", encoding="utf-8") as f:
                f.write(code)
            print(f"[CAD] Saved generated script to: {args.out_script}")

        if args.execute:
            if not client.is_online():
                print("[Error] Live Blender bridge is not running.")
                sys.exit(1)
            print("[CAD] Sending code to live Blender session...")
            res = client.execute_bpy(code)
            print("[Result]:", res)
        elif not args.out_script:
            print(code)

    elif args.command == "print3d":
        res = analyze_mesh_topology(
            vertex_count=1240,
            edge_count=2480,
            face_count=1240,
            non_manifold_edges=0,
            bounding_box_mm=(65.0, 65.0, 90.0),
            volume_cm3=42.5,
            material=args.material,
            printer_profile=args.printer
        )
        print(json.dumps(res, indent=2))

    elif args.command == "cnc":
        if args.validate:
            res = validate_firecontrol_gcode(args.validate, machine_name=args.machine)
            print(json.dumps(res, indent=2))
        else:
            print("[Info] Specify --validate <gcode_file> to verify a file for FireControl.")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
