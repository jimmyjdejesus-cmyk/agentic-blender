# 🎨 Agentic Blender (`agentic-blender`)

> **Autonomous Prompt-Driven 3D CAD, 3D Printing Pre-Flight, and Langmuir CNC Manufacturing Engine.**

[![CI](https://github.com/jimmyjdejesus-cmyk/agentic-blender/actions/workflows/ci.yml/badge.svg)](https://github.com/jimmyjdejesus-cmyk/agentic-blender/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Blender 4.0 - 5.2+](https://img.shields.io/badge/Blender-5.2%20LTS-orange.svg)](https://www.blender.org/)
[![DSH Cordis Native](https://img.shields.io/badge/DSH-Cordis%20Plugin-purple.svg)](https://github.com/deepseek-ai/dsh)

---

## 🌟 Highlights

1. **Prompt Directly in Blender**:
   - Native 3D Viewport UI panel (`N` sidebar -> **Agentic AI** tab) or instant popup (**`Shift + Alt + A`**).
   - Multi-engine flexibility: **Built-in Parametric CAD Engine** (100% offline, zero setup), **Google Gemini AI**, or **Local LLM (Ollama/LM Studio)**.
   - Pushes native **Undo steps (`Ctrl + Z`)** for every generation.
2. **DeepSeek Harness (DSH) Agentic Runtime**:
   - Native Cordis plugin (`dsh-plugin-blender`) exposing 5 tools for autonomous planning, CAD modeling, and manufacturing preparation.
3. **3D Printing Pre-Flight Engine**:
   - Watertight & non-manifold edge detection, inverted normal checks, and degenerate face repair.
   - Exact volume calculation ($cm^3$) and filament mass estimation (PLA, PETG, ABS, TPU, Resin).
   - Build plate envelope verification for **Bambu Lab X1C**, **Prusa MK4**, **Ender 3**, and **Voron 2.4**.
4. **Langmuir Systems CNC Post-Processor**:
   - Direct G-code export for **Langmuir Systems FireControl** (CrossFire, CrossFire PRO, CrossFire XR plasma tables, and MR-1 CNC Mill).
   - Initial Height Sensing (IHS) ohmic/switch touch probe (`G38.2`), torch trigger (`M3`/`M5`), pierce delays, and Torch Height Control (THC) `H1`/`H0`.
   - Linear lead-ins to prevent edge blowout divots.
   - 2D DXF & SVG contour slicing for SheetCAM.
5. **Jules GitHub Agent Integration**:
   - Tag `@jules` on GitHub issues or add the `jules` label to have Google Jules autonomously write code, run tests, and open Pull Requests.

---

## 📐 System Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Autonomous Agent Runtimes                       │
│  ┌─────────────────────────┐  ┌─────────────────────────────────────┐  │
│  │   DeepSeek Harness      │  │        Google Jules Agent           │  │
│  │   (DSH Cordis Plugins)  │  │        (GitHub Issue -> PR)         │  │
│  └────────────┬────────────┘  └──────────────────┬──────────────────┘  │
└───────────────┼──────────────────────────────────┼─────────────────────┘
                │ DSH Tool Calls                   │ Git PRs & Commits
┌───────────────▼──────────────────────────────────▼─────────────────────┐
│                 agentic-blender Python Core Package                    │
│  • cad/parametric.py  : Modular canisters, snap fits, helical threads │
│  • print3d/           : Watertight manifold checks, volume & bed fit   │
│  • cnc/               : Langmuir FireControl post-processor & IHS THC  │
│  • bridge/client.py   : High-level Python RPC client (:9876)           │
└───────────────────────────────┬────────────────────────────────────────┘
                                │ JSON-RPC / HTTP (:9876)
┌───────────────────────────────▼────────────────────────────────────────┐
│                        Blender 5.2 Session                             │
│  • 3D Viewport Sidebar: N-panel -> 'Agentic AI' tab (or Shift+Alt+A)   │
│  • Thread-safe background execution queue & Main-thread timers         │
│  • Native Undo stack integration (Ctrl+Z)                              │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### 1. Installation

```bash
git clone https://github.com/jimmyjdejesus-cmyk/agentic-blender.git
cd agentic-blender
pip install -e .
```

### 2. Launch Blender & Check Bridge

```bash
# Verify connectivity to live Blender session
agentic-blender status
```

### 3. Generate CAD in Blender

```bash
# Generate a modular cylindrical powder dispenser directly in Blender
agentic-blender cad --type dispenser --shape cylinder --execute

# Generate a precision Langmuir CNC mounting plate
agentic-blender cad --type bracket --execute
```

### 4. 3D Printing Pre-Flight Check

```bash
agentic-blender print3d --check-sample --printer bambu_x1c --material pla
```

### 5. Validate Langmuir CNC G-Code

```bash
agentic-blender cnc --validate gcode/test_sample.nc --machine crossfire_pro
```

---

## 🔌 DeepSeek Harness (DSH) Setup

To connect `agentic-blender` to your DSH harness instance:

```bash
# 1. Run DSH plugin test suite
cd dsh-plugin-blender
npm test

# 2. Link plugin to your local DSH installation
mkdir -p ~/.dsh/plugins
ln -sfn $(pwd) ~/.dsh/plugins/dsh-plugin-blender
```

See [`dsh.config.json`](dsh.config.json) for the active harness profile and tool registrations.

---

## 🤖 Jules GitHub Agent Workflow

1. Open an issue on this repository describing a feature or fix.
2. Tag `@jules` in the issue description or apply the **`jules`** label.
3. Jules will clone the repo in an isolated VM, write code, run pytest & npm test, and submit a PR to `main`.
4. Review and merge the pull request.

---

## 🧪 Running the Test Suites

```bash
# Run Python pytest suite (CAD, 3D printing, CNC post-processor, bridge client)
pytest tests/ -v

# Run DSH Cordis plugin Node test suite
cd dsh-plugin-blender && npm test
```

---

## 📄 License

MIT © [Jimmy De Jesus](https://github.com/jimmyjdejesus-cmyk)
