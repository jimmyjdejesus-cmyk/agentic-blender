"""
DeepSeek Harness (DSH) Python Runtime Adapter.
Links Python agent pipelines with DSH Cordis harness plugins.
"""

import json
import os
from ..bridge.client import BlenderBridgeClient
from ..cad.parametric import generate_modular_dispenser_code, generate_cnc_bracket_code
from ..print3d.validator import analyze_mesh_topology
from ..cnc.post_processor import format_firecontrol_plasma_gcode

class DshBlenderAdapter:
    def __init__(self, config_path=None):
        if config_path is None:
            root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            config_path = os.path.join(root_dir, "dsh.config.json")
            
        self.config_path = config_path
        self.config = {}
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                self.config = json.load(f)
                
        dsh_cfg = self.config.get("dsh", {}).get("profile", {}).get("config", {})
        self.host = dsh_cfg.get("host", "127.0.0.1")
        self.port = dsh_cfg.get("port", 9876)
        self.client = BlenderBridgeClient(host=self.host, port=self.port)

    def dispatch_tool(self, tool_name, params=None):
        """Dispatches a DSH tool invocation to the underlying service."""
        params = params or {}
        
        if tool_name == "blender_status":
            return {"online": self.client.is_online()}
            
        elif tool_name == "blender_inspect_scene":
            return self.client.get_scene()
            
        elif tool_name == "blender_cad_generate":
            archetype = params.get("type", "dispenser")
            shape = params.get("baseShape", "cylinder")
            if archetype == "dispenser":
                code = generate_modular_dispenser_code(base_shape=shape)
            else:
                code = generate_cnc_bracket_code()
                
            if params.get("executeLive", False) and self.client.is_online():
                exec_res = self.client.execute_bpy(code)
                return {"code": code, "execution": exec_res}
            return {"code": code}
            
        elif tool_name == "blender_3dprint_preflight":
            return analyze_mesh_topology(
                vertex_count=params.get("vertexCount", 1000),
                edge_count=params.get("edgeCount", 2000),
                face_count=params.get("faceCount", 1000),
                non_manifold_edges=params.get("nonManifoldEdges", 0),
                zero_area_faces=params.get("zeroAreaFaces", 0),
                inverted_normals=params.get("invertedNormals", 0),
                bounding_box_mm=tuple(params.get("dimensionsMm", [50, 50, 50])),
                volume_cm3=params.get("volumeCm3", 25.0),
                material=params.get("material", "pla"),
                printer_profile=params.get("printer", "bambu_x1c")
            )
            
        elif tool_name == "blender_cnc_postprocess":
            paths = params.get("paths", [])
            machine = params.get("machine", "crossfire_pro")
            material = params.get("material", "14_gauge_mild_steel")
            return {
                "gcode": format_firecontrol_plasma_gcode(paths, machine, material)
            }
            
        else:
            raise ValueError(f"Unknown tool name: {tool_name}")
