"""
High-Level Client for Blender Agentic Bridge.
Allows agents and automation scripts to interact with the live running Blender session.
"""

import json
import urllib.request
import urllib.error

class BlenderBridgeClient:
    def __init__(self, host="127.0.0.1", port=9876):
        self.base_url = f"http://{host}:{port}"

    def is_online(self, timeout=1.0):
        """Check if Blender bridge server is reachable."""
        try:
            req = urllib.request.Request(f"{self.base_url}/status", method="GET")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("status") == "online"
        except Exception:
            return False

    def get_status(self, timeout=2.0):
        """Get bridge runtime status, active object, object counts."""
        req = urllib.request.Request(f"{self.base_url}/status", method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def get_scene(self, timeout=3.0):
        """Get list of objects, locations, and bounding box dimensions in active scene."""
        req = urllib.request.Request(f"{self.base_url}/scene", method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def execute_bpy(self, python_code, timeout=35.0):
        """Execute Python code inside Blender's main event loop."""
        payload = json.dumps({"code": python_code}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/execute",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def clear_scene(self, timeout=5.0):
        """Reset scene objects to empty state."""
        req = urllib.request.Request(
            f"{self.base_url}/clear",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
