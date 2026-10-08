# dsh-plugin-blender

**DeepSeek Harness (DSH)** native Cordis plugin for autonomous Blender 3D CAD modeling, 3D printing preparation, and Langmuir Systems CNC manufacturing.

---

## 🛠️ Tool Catalog Registered in DSH

| Tool Name | Parameters | Description |
| :--- | :--- | :--- |
| `blender_status` | *none* | Verifies connectivity to the live Blender session on `localhost:9876`. |
| `blender_inspect_scene` | *none* | Retrieves scene hierarchy, object transforms, and bounding dimensions. |
| `blender_cad_generate` | `type`, `baseShape`, `radius`, `height`, `executeLive` | Synthesizes parametric 3D CAD models (modular canisters, filters, holders, CNC brackets). |
| `blender_3dprint_preflight` | `nonManifoldEdges`, `dimensionsMm`, `volumeCm3`, `material`, `printer` | Analyzes watertight manifold topology, estimates filament mass, and checks build plate fit. |
| `blender_cnc_postprocess` | `paths`, `machine`, `material`, `feedrate` | Formats 2D planar toolpaths into certified Langmuir FireControl G-code (IHS probe, THC, M3/M5). |

---

## 📐 Architecture

```
┌────────────────────────────────────────────────────────┐
│               DeepSeek Harness (DSH)                   │
│      Cordis Plugin Architecture & Agentic Loop         │
└───────────────────────────┬────────────────────────────┘
                            │ Tool Invocations
┌───────────────────────────▼────────────────────────────┐
│                  dsh-plugin-blender                    │
│      • Parametric CAD Engine                           │
│      • 3D Printing Pre-Flight Validator                │
│      • Langmuir CNC Post-Processor                     │
│      • Security & Audit Action Ledger                  │
└───────────────────────────┬────────────────────────────┘
                            │ HTTP JSON-RPC (:9876)
┌───────────────────────────▼────────────────────────────┐
│             Blender 5.2 Live Session                   │
│      • 3D Viewport GUI Panel (Agentic AI)              │
│      • Thread-safe Execution Queue                     │
│      • Native Undo Stack Integration (Ctrl+Z)          │
└────────────────────────────────────────────────────────┘
```

---

## 🧪 Testing

```bash
npm test
```
