# Agentic Blender: Prompt-Driven 3D & CNC CAD

You now have a fully autonomous, prompt-driven Blender environment connected directly to Antigravity.

---

## ⚡ How It Works

1. **Live Execution Bridge (`localhost:9876`)**:
   - A high-performance Python HTTP bridge runs inside Blender's thread/timer loop.
   - Any prompt you give to Antigravity gets translated into Python (`bpy`) operations and executed instantly inside Blender.
   - All agent actions automatically generate native Blender **Undo steps (`Ctrl + Z`)**.

2. **In-Blender UI Sidebar**:
   - Press **`N`** in Blender's 3D Viewport to open the sidebar.
   - Select the **Agentic** tab to see connection status, activity logs, and scene controls.

3. **Autonomous Capabilities**:
   - **Mesh Generation & Boolean Operations**: Canisters, enclosures, threads, hollow shells, modular connectors, mounting plates.
   - **Modifiers & Detailing**: Chamfers, bevels, knurling, sub-surf, mirror, boolean cutouts.
   - **Materials & Lighting**: Metallic, plastic, silicone shaders, studio 3-point lighting setups.
   - **Direct CNC & 3D Print Export**: Instant STL, OBJ, DXF, and Langmuir FireControl G-code generation.

---

## 💬 How to Use: Just Prompt Antigravity

You can simply tell Antigravity what you want to create, modify, or export. For example:

* *"Clear the scene and create a 50mm diameter cylindrical canister with a 3mm wall thickness and screw-thread lip."*
* *"Add a knurled grip pattern along the exterior of the active cylinder."*
* *"Model a snap-fit cap with a silicone gasket groove."*
* *"Bevel all 90-degree edges by 1.5mm."*
* *"Export this part to STL for 3D printing and generate Langmuir FireControl G-code for the base plate."*

---

## 🛠️ CLI Utilities

You can also interact via terminal:

```powershell
# Check bridge connection
python scripts/agent_blender_bridge.py --status

# Get full scene summary (objects, dimensions, coordinates)
python scripts/agent_blender_bridge.py --summary

# Clear the current scene
python scripts/agent_blender_bridge.py --clear

# Execute a one-liner bpy command
python scripts/agent_blender_bridge.py --code "bpy.ops.mesh.primitive_torus_add(location=(0,0,5))"
```
