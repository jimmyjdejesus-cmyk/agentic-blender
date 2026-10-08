"""
Agentic Blender Bridge Client.
Provides instant Python & CLI communication with the live running Blender session.
"""

import sys
import os
import json
import time
import subprocess
import urllib.request
import urllib.error

BRIDGE_URL = "http://127.0.0.1:9876"
BLENDER_EXE = r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"

def is_blender_running():
    """Check if Blender bridge server is reachable."""
    try:
        req = urllib.request.Request(f"{BRIDGE_URL}/status", method="GET")
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return True, data
    except Exception:
        return False, None

def launch_blender_live():
    """Launch Blender with GUI."""
    running, info = is_blender_running()
    if running:
        print("[Agentic Blender] Blender is already running with bridge active.")
        return True

    print("[Agentic Blender] Launching Blender 5.2...")
    subprocess.Popen([BLENDER_EXE], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Wait up to 15 seconds for bridge to respond
    for _ in range(30):
        time.sleep(0.5)
        running, info = is_blender_running()
        if running:
            print(f"[Agentic Blender] Connected to live Blender session! (Version: {info.get('blender_version')})")
            return True
            
    print("[Warning] Blender launched, but bridge server has not responded yet.")
    return False

def execute_bpy(code):
    """
    Execute Python code inside the live Blender session.
    Returns (success, stdout, error).
    """
    running, _ = is_blender_running()
    if not running:
        print("[Agentic Blender] Blender bridge not detected. Launching Blender...")
        if not launch_blender_live():
            return False, "", "Could not connect to Blender."

    payload = json.dumps({"code": code}).encode("utf-8")
    req = urllib.request.Request(
        f"{BRIDGE_URL}/execute",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=35.0) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            if res.get("success"):
                stdout = res.get("stdout", "")
                return True, stdout, None
            else:
                err = res.get("error", "Unknown error")
                tb = res.get("traceback", "")
                return False, "", f"{err}\n{tb}"
    except Exception as e:
        return False, "", str(e)

def get_scene_summary():
    """Fetch current scene objects and hierarchy."""
    try:
        req = urllib.request.Request(f"{BRIDGE_URL}/scene", method="GET")
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}

def clear_scene():
    """Reset Blender scene to empty."""
    try:
        req = urllib.request.Request(
            f"{BRIDGE_URL}/clear",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}

def render_preview(output_file="preview.png"):
    """Trigger a fast render of the current viewport scene."""
    abs_path = os.path.abspath(output_file)
    try:
        req = urllib.request.Request(
            f"{BRIDGE_URL}/render",
            data=json.dumps({"path": abs_path}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30.0) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Agentic Blender Live Controller")
    parser.add_argument("--status", action="store_true", help="Check bridge status")
    parser.add_argument("--launch", action="store_true", help="Launch live Blender")
    parser.add_argument("--clear", action="store_true", help="Clear current scene")
    parser.add_argument("--code", type=str, help="Execute raw Python code in Blender")
    parser.add_argument("--file", type=str, help="Execute Python script file in Blender")
    parser.add_argument("--summary", action="store_true", help="Print scene summary")
    
    args = parser.parse_args()

    if args.status:
        running, info = is_blender_running()
        if running:
            print("[OK] Blender bridge is online:", info)
        else:
            print("[OFFLINE] Blender bridge is not reachable.")
            
    elif args.launch:
        launch_blender_live()
        
    elif args.clear:
        res = clear_scene()
        print("Clear result:", res)
        
    elif args.summary:
        print(json.dumps(get_scene_summary(), indent=2))
        
    elif args.code:
        ok, out, err = execute_bpy(args.code)
        if ok:
            print("[Success]")
            if out:
                print(out)
        else:
            print("[Failed]", err)
            
    elif args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            code = f.read()
        ok, out, err = execute_bpy(code)
        if ok:
            print("[Success]")
            if out:
                print(out)
        else:
            print("[Failed]", err)
    else:
        parser.print_help()
