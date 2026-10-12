# DESIGN.md — Agentic Blender "Stitch" 3D CAD & Manufacturing System Tokens

> Inspired by **Google Stitch (`DESIGN.md`)**, this document defines the persistent engineering, visual, and manufacturing design tokens automatically injected into both **System 1 (Fast Parametric Brain)** and **System 2 (Deliberative LLM Brain)** across every prompt and variation.

## 1. Dimensional & Tolerance Tokens
- **Primary CAD Units**: `inches` (with automatic `25.4x` conversion to `mm` for 3D printing STL/3MF pre-flight)
- **Minimum Wall Thickness (FDM 3D Print)**: `0.10 in` (`2.54 mm`, 6 perimeters @ 0.4mm nozzle)
- **Default Structural Wall Thickness**: `0.25 in` (`6.35 mm`)
- **Thread / Lid Slip-Fit Clearance**: `0.008 in` (`0.20 mm` radial clearance)
- **Default Edge Treatment**: `0.04 in` (`1.0 mm`) 3-segment bevel/chamfer on external load-bearing edges

## 2. Fastener & Hole Standards
- **CNC Mounting Plate Bolt Holes**: `0.375 in` (`3/8"`) diameter (`0.1875 in` radius) with `+0.015 in` plasma kerf compensation
- **M3 Clearance Hole**: `3.2 mm` (`0.126 in`) diameter
- **M4 Clearance Hole**: `4.3 mm` (`0.169 in`) diameter
- **1/4"-20 Clearance Hole**: `0.266 in` (`6.75 mm`) diameter

## 3. PBR Material & Surface Finish Themes (Stitch Vibe Tokens)
| Theme ID | Base Color `(R, G, B, A)` | Metallic | Roughness | Usage |
| :--- | :--- | :--- | :--- | :--- |
| `anodized_blue` | `(0.10, 0.45, 0.85, 1.0)` | `0.85` | `0.25` | Primary precision CNC aluminum bodies |
| `brushed_titanium` | `(0.62, 0.64, 0.68, 1.0)` | `0.92` | `0.22` | High-strength aerospace & medical housings |
| `matte_carbon` | `(0.12, 0.12, 0.15, 1.0)` | `0.15` | `0.45` | Knurled lids, ergonomic grips, CF-Nylon |
| `industrial_brass` | `(0.85, 0.65, 0.20, 1.0)` | `0.95` | `0.20` | Nozzles, inserts, precision dosing wells |
| `plasma_steel` | `(0.35, 0.38, 0.42, 1.0)` | `0.88` | `0.35` | Langmuir CrossFire PRO sheet/plate steel |

## 4. Manufacturing Target Profiles
### 3D Printing (`print3d`)
- **Default Printer**: `Bambu Lab X1C` (`256 x 256 x 256 mm` build volume)
- **Topology Requirement**: 100% watertight manifold (`non_manifold_edges == 0`, `inverted_normals == 0`)

### Langmuir CNC Plasma (`cnc`)
- **Default Machine**: `Langmuir CrossFire PRO` (`48 x 36 in` table)
- **Controller**: `FireControl` (`G20`, `G90`, `G94`, `G54`)
- **IHS & THC Sequence**: `G38.2 Z-5.0 F60.0` touch-off $\rightarrow$ `G0 Z0.02` $\rightarrow$ `G92 Z0.0` $\rightarrow$ Pierce `0.15 in` $\rightarrow$ Cut `0.06 in` $\rightarrow$ `H1` / `H0` Torch Height Control
