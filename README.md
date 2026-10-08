# Langmuir CNC & Blender Agentic Workspace

This workspace bridges **Blender 5.2** 3D modeling with **Langmuir Systems CNC machines** (CrossFire, CrossFire PRO, CrossFire XR, and MR-1 Gantry Mill) running **FireControl**.

---

## 📁 Workspace Structure

- **`models/`**: 3D design files (`.blend`, `.obj`, `.stl`).
- **`dxf_svg/`**: Exported 2D contours and profiles (`.svg`, `.dxf`) for sheet metal and plasma cutting.
- **`gcode/`**: Generated CNC G-code files (`.nc`, `.tap`) formatted for FireControl.
- **`scripts/`**:
  - `langmuir_config.py`: Machine parameters, work envelopes, and material feeds/speeds.
  - `blender_cnc_export.py`: Blender headless script to extract contours and generate FireControl G-code.
  - `agent_cnc_cli.py`: Unified pipeline orchestrator and G-code syntax validator.

---

## 🚀 Quick Start & CLI Usage

### 1. Generate a Test Part & FireControl G-code
```powershell
python scripts/agent_cnc_cli.py --sample --out-nc gcode/test_bracket.nc
```

### 2. Export G-Code from a Blender Model
```powershell
python scripts/agent_cnc_cli.py --model models/my_part.blend --out-nc gcode/my_part.nc --material 14_gauge_mild_steel
```

### 3. Automatically Launch FireControl
```powershell
python scripts/agent_cnc_cli.py --sample --open-firecontrol
```

---

## ⚙️ Supported Machines & Materials

### Machines:
- `crossfire_pro` (Default): CrossFire PRO Plasma CNC with IHS & THC
- `crossfire_xr`: CrossFire XR 4x8 Industrial Plasma CNC
- `mr1_mill`: MR-1 CNC Gantry Milling Machine

### Material Presets (Mild Steel):
- `16_gauge_mild_steel`: 180 IPM, 0.5s pierce delay
- `14_gauge_mild_steel`: 150 IPM, 0.6s pierce delay (Default)
- `11_gauge_mild_steel`: 110 IPM, 0.7s pierce delay
- `3_16_inch_mild_steel`: 75 IPM, 0.9s pierce delay
- `1_4_inch_mild_steel`: 48 IPM, 1.2s pierce delay

---

## 🎛️ FireControl Standard Syntax
Generated `.nc` files include:
- **IHS (Initial Height Sensing)**: `G38.2` electrical touch probe with 0.02" springback compensation.
- **Pierce Cycle**: `M3` torch fire + `G4 P[seconds]` dwell before cutting.
- **THC (Torch Height Control)**: `H1` (enable THC during cut) and `H0` (disable before rapid).
- **Coordinate Systems**: `G20` (Inches), `G54` Work Coordinate System, and `G90 G94`.
