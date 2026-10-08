# AGENTS.md — Agent & Contributor Directives

Welcome to **Agentic Blender** (`agentic-blender`).
This document outlines project architecture, coding standards, branch conventions, and testing requirements for human engineers and autonomous agents (including Google Labs **Jules** and **DeepSeek Harness (DSH)** agents).

---

## 🎯 Project Mission & MVP Scope

Agentic Blender provides a prompt-driven, autonomous 3D CAD/CAM workflow:
1. **Prompt-to-CAD Design**: Parametric generation of mechanical components, assemblies, enclosures, modular canisters, threads, knurling, lattices, and brackets.
2. **3D Printing Preparation**:
   - Manifold & watertight verification (non-manifold edge detection, flipped normals, zero-thickness face warnings).
   - Volume calculation ($cm^3$), bounding box, and print bed fit estimation.
   - High-fidelity binary STL and 3MF export.
3. **CNC Machining (Langmuir Systems)**:
   - 2.5D planar contour extraction & DXF/SVG export for SheetCAM / CAM packages.
   - Native post-processing for **Langmuir Systems FireControl** (CrossFire, CrossFire PRO, CrossFire XR plasma tables, and MR-1 CNC Gantry Mill).
   - Generates Initial Height Sensing (IHS) `G38.2` touch probe cycles, torch trigger `M3`/`M5`, pierce delays, and Torch Height Control (THC) `H1`/`H0` commands.
4. **Agent Runtimes**:
   - **In-Blender UI Panel**: 3D Viewport sidebar (`N` panel -> `Agentic AI`) and quick popup (`Shift+Alt+A`).
   - **Local HTTP Bridge**: Background RPC engine on `http://127.0.0.1:9876` for live viewport synchronization.
   - **DSH Harness Plugin (`dsh-plugin-blender`)**: Native Cordis plugin for DeepSeek Harness (`@deepseek-ai/dsh`).

---

## 🌿 Branching & Git Workflow

All contributors and agents must follow standard trunk-based feature branching:

* **Default Branch**: `main` (production-ready, tested code).
* **Feature Branches**: `feat/<feature-name>` (e.g. `feat/dsh-runtime-plugin`, `feat/3dprint-validator`).
* **Fix Branches**: `fix/<bug-name>`
* **Pull Requests**:
  - All PRs must target `main`.
  - PR titles must follow Conventional Commits (`feat: ...`, `fix: ...`, `test: ...`, `docs: ...`).
  - PRs must include a test summary and confirm tests pass.

### 🤖 Jules Collaboration
- Jules is enabled for issue-to-PR workflows.
- Create an issue on GitHub describing the needed feature, bugfix, or enhancement, and apply the **`jules`** label (or mention `@jules`).
- Jules will autonomously inspect the repository, write code, run tests, and open a Pull Request into `main`.
- Review and merge Jules' PRs with proper verification.

---

## 🧪 Testing Requirements

Before committing or opening PRs, all tests must pass:

```bash
# Python Test Suite (Core CAD, 3D Print Validator, CNC Post-Processor, Bridge)
pytest tests/ -v

# DSH Cordis Plugin Tests
cd dsh-plugin-blender && npm test
```

### Test Standards:
- All new features must have unit tests.
- 3D print validation tests must verify watertight manifolds and catch non-manifold errors.
- CNC post-processor tests must verify FireControl G-code syntax (`G20/G21`, `G54`, `G38.2`, `M3`, `M5`, `H1`, `H0`, `M30`).
- No hardcoded paths: use standard environment variables or fallback defaults.
