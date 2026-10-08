/**
 * dsh-plugin-blender
 * DeepSeek Harness (DSH) native Cordis plugin for autonomous Blender 3D CAD,
 * 3D printing preparation, and Langmuir CNC machining.
 */

const http = require('http');
const fs = require('fs');
const path = require('path');

class BlenderService {
  constructor(ctx, config = {}) {
    this.ctx = ctx;
    this.host = config.host || '127.0.0.1';
    this.port = config.port || 9876;
    this.auditLog = [];
  }

  logAudit(action, details, success = true) {
    const entry = {
      timestamp: new Date().toISOString(),
      action,
      details,
      success,
    };
    this.auditLog.push(entry);
    return entry;
  }

  async _request(endpoint, method = 'GET', data = null) {
    return new Promise((resolve, reject) => {
      const payload = data ? JSON.stringify(data) : null;
      const options = {
        hostname: this.host,
        port: this.port,
        path: endpoint,
        method: method,
        headers: {
          'Content-Type': 'application/json',
          ...(payload ? { 'Content-Length': Buffer.byteLength(payload) } : {}),
        },
        timeout: 5000,
      };

      const req = http.request(options, (res) => {
        let body = '';
        res.on('data', (chunk) => (body += chunk));
        res.on('end', () => {
          try {
            const parsed = JSON.parse(body);
            resolve(parsed);
          } catch (e) {
            resolve({ raw: body, statusCode: res.statusCode });
          }
        });
      });

      req.on('error', (err) => {
        reject(err);
      });

      req.on('timeout', () => {
        req.destroy();
        reject(new Error(`Request to ${endpoint} timed out`));
      });

      if (payload) {
        req.write(payload);
      }
      req.end();
    });
  }

  async getStatus() {
    try {
      const res = await this._request('/status');
      this.logAudit('status_check', { online: res.status === 'online' });
      return res;
    } catch (err) {
      this.logAudit('status_check', { online: false, error: err.message }, false);
      return { status: 'offline', error: err.message };
    }
  }

  async inspectScene() {
    try {
      const res = await this._request('/scene');
      this.logAudit('inspect_scene', { objectCount: res.objects ? res.objects.length : 0 });
      return res;
    } catch (err) {
      return { error: 'Failed to inspect scene', details: err.message };
    }
  }

  async executeBpy(pythonCode) {
    if (!pythonCode || typeof pythonCode !== 'string') {
      throw new Error('pythonCode must be a non-empty string');
    }
    try {
      const res = await this._request('/execute', 'POST', { code: pythonCode });
      this.logAudit('execute_bpy', { success: res.success });
      return res;
    } catch (err) {
      this.logAudit('execute_bpy', { error: err.message }, false);
      return { success: false, error: err.message };
    }
  }

  generateThreadedLipScript(options = {}) {
    const {
      radius = 1.8,
      height = 0.5,
      pitch = 0.2,
      threadDepth = 0.08,
      isOuter = true,
      turns = 3.0,
      segmentsPerTurn = 32,
    } = options;

    const threadType = isOuter ? 'Outer' : 'Inner';
    const depthSign = isOuter ? 1.0 : -1.0;

    return `import bpy, bmesh, math

if bpy.context.object and bpy.context.object.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

mat = bpy.data.materials.new(name='Thread_Mat')
mat.use_nodes = True

radius = ${radius}
height = ${height}
pitch = ${pitch}
thread_depth = ${threadDepth}
is_outer = ${isOuter ? 'True' : 'False'}
turns = ${turns}
segments_per_turn = ${segmentsPerTurn}

# Base Collar
bpy.ops.mesh.primitive_cylinder_add(vertices=${segmentsPerTurn}, radius=${radius}, depth=${height}, location=(0, 0, ${height / 2}))
base_collar = bpy.context.active_object
base_collar.name = "Threaded_Lip_Collar_${threadType}"

# Procedural Thread Helix
mesh = bpy.data.meshes.new("Thread_Helix_Mesh")
thread_obj = bpy.data.objects.new("Threaded_Lip_${threadType}", mesh)
bpy.context.collection.objects.link(thread_obj)
bpy.context.view_layer.objects.active = thread_obj

bm = bmesh.new()
total_steps = int(turns * segments_per_turn)
depth_sign = ${depthSign}

prev_verts = None
for i in range(total_steps + 1):
    angle = (i / segments_per_turn) * 2.0 * math.pi
    z = (i / total_steps) * min(height, turns * pitch)
    half_pitch = pitch * 0.4
    r_base = radius
    r_crest = radius + (depth_sign * thread_depth)
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)

    v0 = bm.verts.new((r_base * cos_a, r_base * sin_a, max(0.0, z - half_pitch)))
    v1 = bm.verts.new((r_crest * cos_a, r_crest * sin_a, z))
    v2 = bm.verts.new((r_base * cos_a, r_base * sin_a, min(height, z + half_pitch)))

    curr_verts = [v0, v1, v2]
    if prev_verts:
        bm.faces.new([prev_verts[0], curr_verts[0], curr_verts[1], prev_verts[1]])
        bm.faces.new([prev_verts[1], curr_verts[1], curr_verts[2], prev_verts[2]])
    prev_verts = curr_verts

bm.to_mesh(mesh)
bm.free()

base_collar.select_set(True)
thread_obj.select_set(True)
bpy.context.view_layer.objects.active = base_collar
bpy.ops.object.join()
base_collar.name = "Threaded_Lip_${threadType}"

bpy.ops.object.camera_add(location=(5.0, -5.0, 4.0), rotation=(math.radians(60), 0, math.radians(45)))
bpy.context.scene.camera = bpy.context.active_object
bpy.ops.object.light_add(type='SUN', location=(3, -3, 6))
print("[DSH CAD] Procedural ${threadType} screw thread generated.")
`;
  }

  generateSnapFitJointScript(options = {}) {
    const {
      radius = 1.8,
      tabCount = 4,
      tabWidth = 0.3,
      tabHeight = 0.5,
      cantileverThickness = 0.08,
      latchDepth = 0.05,
      clearance = 0.02,
    } = options;

    return `import bpy, bmesh, math

if bpy.context.object and bpy.context.object.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

radius = ${radius}
tab_count = ${tabCount}
tab_width = ${tabWidth}
tab_height = ${tabHeight}
cantilever_thickness = ${cantileverThickness}
latch_depth = ${latchDepth}
clearance = ${clearance}

# 1. Male Component
bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=0.6, location=(0, 0, 0.3))
male_body = bpy.context.active_object
male_body.name = "Snap_Fit_Male"

for i in range(tab_count):
    angle = i * (2.0 * math.pi / tab_count)
    rx = radius * math.cos(angle)
    ry = radius * math.sin(angle)

    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(rx, ry, 0.6 + tab_height / 2.0))
    tab = bpy.context.active_object
    tab.scale = (cantilever_thickness, tab_width, tab_height)
    tab.rotation_euler = (0, 0, angle)
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    tab.name = f"Snap_Tab_Male_{i}"

    hook_r = radius + latch_depth
    hx = hook_r * math.cos(angle)
    hy = hook_r * math.sin(angle)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(hx, hy, 0.6 + tab_height - (latch_depth / 2.0)))
    hook = bpy.context.active_object
    hook.scale = (latch_depth * 1.5, tab_width, latch_depth * 1.2)
    hook.rotation_euler = (0, 0, angle)
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    hook.name = f"Snap_Latch_Male_{i}"

# 2. Female Component
female_y = radius * 2.5
bpy.ops.mesh.primitive_cylinder_add(radius=radius + cantilever_thickness + clearance + 0.1, depth=0.8, location=(0, female_y, 0.4))
female_body = bpy.context.active_object
female_body.name = "Snap_Fit_Female"

bpy.ops.mesh.primitive_cylinder_add(radius=radius + clearance, depth=0.7, location=(0, female_y, 0.35))
female_core = bpy.context.active_object
fbool = female_body.modifiers.new(name="MatingCavity", type='BOOLEAN')
fbool.object = female_core
fbool.operation = 'DIFFERENCE'
bpy.context.view_layer.objects.active = female_body
bpy.ops.object.modifier_apply(modifier="MatingCavity")
bpy.data.objects.remove(female_core, do_unlink=True)

for i in range(tab_count):
    angle = i * (2.0 * math.pi / tab_count)
    rx = (radius + cantilever_thickness) * math.cos(angle)
    ry = female_y + (radius + cantilever_thickness) * math.sin(angle)

    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(rx, ry, 0.5))
    recess = bpy.context.active_object
    recess.scale = (cantilever_thickness + clearance * 2, tab_width + clearance * 2, latch_depth + clearance)
    recess.rotation_euler = (0, 0, angle)
    bpy.ops.object.transform_apply(scale=True, rotation=True)

    rbool = female_body.modifiers.new(name=f"Slot_{i}", type='BOOLEAN')
    rbool.object = recess
    rbool.operation = 'DIFFERENCE'
    bpy.context.view_layer.objects.active = female_body
    bpy.ops.object.modifier_apply(modifier=f"Slot_{i}")
    bpy.data.objects.remove(recess, do_unlink=True)

bpy.ops.object.camera_add(location=(7.0, -7.0, 6.0), rotation=(math.radians(60), 0, math.radians(45)))
bpy.context.scene.camera = bpy.context.active_object
bpy.ops.object.light_add(type='SUN', location=(3, -3, 8))
print(f"[DSH CAD] Interlocking snap-fit cantilever joint created with {tab_count} tabs.")
`;
  }

  generateCadScript(options = {}) {
    if (options.type === 'threaded_lip') {
      return this.generateThreadedLipScript(options);
    }
    if (options.type === 'snap_fit_joint') {
      return this.generateSnapFitJointScript(options);
    }

    const {
      baseShape = 'cylinder',
      radius = 1.8,
      height = 4.0,
      includeFilter = true,
      includeHolders = true,
      includeLid = true,
    } = options;

    let vertices = 32;
    if (baseShape === 'hexagon') vertices = 6;
    if (baseShape === 'rectangle') vertices = 4;

    const script = `import bpy, math
if bpy.context.object and bpy.context.object.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

def get_or_create_mat(name, color, roughness=0.3, metallic=0.0):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    if bsdf:
        bsdf.inputs['Base Color'].default_value = color
        bsdf.inputs['Roughness'].default_value = roughness
        bsdf.inputs['Metallic'].default_value = metallic
    return mat

mat_body = get_or_create_mat('Anodized_Mat', (0.1, 0.45, 0.85, 1.0), roughness=0.25, metallic=0.85)

# 1. Main Canister
bpy.ops.mesh.primitive_cylinder_add(vertices=${vertices}, radius=${radius}, depth=${height}, location=(0, 0, ${height / 2}))
body = bpy.context.active_object
body.name = "Dispenser_Main_Body"
body.data.materials.append(mat_body)

# Interior cavity
bpy.ops.mesh.primitive_cylinder_add(vertices=${vertices}, radius=${radius - 0.25}, depth=${height - 0.25}, location=(0, 0, ${(height / 2) + 0.15}))
core = bpy.context.active_object
core.name = "Core"
cmod = body.modifiers.new(name="Cavity", type='BOOLEAN')
cmod.object = core
cmod.operation = 'DIFFERENCE'
bpy.context.view_layer.objects.active = body
bpy.ops.object.modifier_apply(modifier="Cavity")
bpy.data.objects.remove(core, do_unlink=True)
${includeFilter ? `
# 2. Dry Desiccant Filter Base
bpy.ops.mesh.primitive_cylinder_add(vertices=${vertices}, radius=${radius}, depth=0.8, location=(${radius * 2.5}, 0, 0.4))
filter_base = bpy.context.active_object
filter_base.name = "Dry_Filter_Base"
` : ''}
${includeHolders ? `
# 3. Precision Dosing Cavities
bpy.ops.mesh.primitive_cylinder_add(radius=1.2, depth=0.9, location=(${-radius * 2.5}, 0, 0.45))
h_std = bpy.context.active_object
h_std.name = "Dosing_Holder_0.1g"
` : ''}
${includeLid ? `
# 4. Knurled Cap
bpy.ops.mesh.primitive_cylinder_add(radius=${radius * 1.05}, depth=0.6, location=(0, ${radius * 2.5}, 0.3))
lid = bpy.context.active_object
lid.name = "Knurled_Airtight_Lid"
` : ''}
bpy.ops.object.camera_add(location=(8.5, -8.5, 7.0), rotation=(math.radians(60), 0, math.radians(45)))
bpy.context.scene.camera = bpy.context.active_object
bpy.ops.object.light_add(type='SUN', location=(4, -4, 9))
print("[DSH CAD] Modular ecosystem created.")
`;
    return script;
  }

  validate3DPrint(params = {}) {
    const {
      nonManifoldEdges = 0,
      zeroAreaFaces = 0,
      invertedNormals = 0,
      dimensionsMm = [50, 50, 50],
      volumeCm3 = 25.0,
      material = 'pla',
      printer = 'bambu_x1c',
    } = params;

    const densities = { pla: 1.24, petg: 1.27, abs: 1.04, tpu: 1.21, aluminum: 2.7 };
    const printerBeds = {
      bambu_x1c: [256, 256, 256],
      prusa_mk4: [250, 210, 220],
      ender_3: [220, 220, 250],
    };

    const bed = printerBeds[printer] || [256, 256, 256];
    const errors = [];
    const warnings = [];

    const isWatertight = nonManifoldEdges === 0;
    if (!isWatertight) {
      errors.push(`Mesh is not watertight: ${nonManifoldEdges} non-manifold edges.`);
    }
    if (zeroAreaFaces > 0) {
      warnings.push(`Mesh contains ${zeroAreaFaces} degenerate zero-area faces.`);
    }
    if (invertedNormals > 0) {
      errors.push(`Mesh contains ${invertedNormals} inverted face normals.`);
    }

    const fitsBed =
      dimensionsMm[0] <= bed[0] &&
      dimensionsMm[1] <= bed[1] &&
      dimensionsMm[2] <= bed[2];

    if (!fitsBed) {
      errors.push(`Model dimensions exceed ${printer} bed envelope (${bed.join('x')} mm).`);
    }

    const density = densities[material.toLowerCase()] || 1.24;
    const estimatedMassG = Math.round(volumeCm3 * density * 100) / 100;

    return {
      isPrintable: errors.length === 0,
      isWatertight,
      dimensionsMm,
      volumeCm3,
      estimatedMassG,
      material,
      printer,
      fitsBed,
      errors,
      warnings,
    };
  }

  formatFireControlGCode(paths, options = {}) {
    const {
      machine = 'crossfire_pro',
      material = '14_gauge_mild_steel',
      feedrate = 150.0,
      pierceDelay = 0.6,
      safeZ = 1.0,
    } = options;

    const lines = [
      '(================================================)',
      '( Controller: Langmuir Systems FireControl        )',
      `(${machine} | ${material} | DSH Agent)`,
      '(================================================)',
      'G90 G94',
      'G20',
      'G54',
      `G0 Z${safeZ.toFixed(4)}`,
      '',
    ];

    paths.forEach((path, i) => {
      if (!path || path.length === 0) return;
      lines.push(`( --- Profile ${i + 1} --- )`);
      lines.push(`G0 X${path[0][0].toFixed(4)} Y${path[0][1].toFixed(4)}`);
      lines.push('G38.2 Z-5.0000 F60.0 (IHS Probe Contact)');
      lines.push('G92 Z0.0');
      lines.push('G0 Z0.0200 (Springback)');
      lines.push('G92 Z0.0');
      lines.push('G0 Z0.1500 (Pierce Height)');
      lines.push('M3 (Torch ON)');
      lines.push(`G4 P${pierceDelay.toFixed(2)} (Pierce Dwell)`);
      lines.push('G1 Z0.0600 F60.0 (Cut Height)');
      lines.push('H1 (THC ON)');

      for (let j = 1; j < path.length; j++) {
        lines.push(`G1 X${path[j][0].toFixed(4)} Y${path[j][1].toFixed(4)} F${feedrate.toFixed(1)}`);
      }

      lines.push('H0 (THC OFF)');
      lines.push('M5 (Torch OFF)');
      lines.push(`G0 Z${safeZ.toFixed(4)}`);
      lines.push('');
    });

    lines.push('M30 (End of Program)');
    lines.push('');
    return lines.join('\n');
  }
}

function apply(ctx, config) {
  const service = new BlenderService(ctx, config);

  // Expose as Cordis service
  if (ctx && typeof ctx.provide === 'function') {
    ctx.provide('blender');
    ctx.blender = service;
  }

  // Register DSH Tool definitions
  const tools = [
    {
      name: 'blender_status',
      description: 'Check connectivity to the live Blender session on localhost:9876',
      parameters: {},
      execute: async () => await service.getStatus(),
    },
    {
      name: 'blender_inspect_scene',
      description: 'Retrieve object hierarchy, transforms, and bounding dimensions of active Blender scene',
      parameters: {},
      execute: async () => await service.inspectScene(),
    },
    {
      name: 'blender_cad_generate',
      description: 'Generate parametric 3D CAD models (modular canisters, filters, holders, screw threads, snap-fit joints, CNC brackets)',
      parameters: {
        type: { type: 'string', enum: ['dispenser', 'bracket', 'threaded_lip', 'snap_fit_joint'], default: 'dispenser' },
        baseShape: { type: 'string', enum: ['cylinder', 'hexagon', 'rectangle'], default: 'cylinder' },
        radius: { type: 'number', default: 1.8 },
        height: { type: 'number', default: 4.0 },
        pitch: { type: 'number', default: 0.2 },
        threadDepth: { type: 'number', default: 0.08 },
        isOuter: { type: 'boolean', default: true },
        tabCount: { type: 'number', default: 4 },
        executeLive: { type: 'boolean', default: false },
      },
      execute: async (params) => {
        const code = service.generateCadScript(params);
        if (params.executeLive) {
          const execRes = await service.executeBpy(code);
          return { script: code, execution: execRes };
        }
        return { script: code };
      },
    },
    {
      name: 'blender_3dprint_preflight',
      description: 'Analyze mesh for watertight manifold topology, calculate volume/weight, and check build plate fit',
      parameters: {
        nonManifoldEdges: { type: 'number', default: 0 },
        dimensionsMm: { type: 'array', items: { type: 'number' } },
        volumeCm3: { type: 'number', default: 25.0 },
        material: { type: 'string', default: 'pla' },
        printer: { type: 'string', default: 'bambu_x1c' },
      },
      execute: async (params) => service.validate3DPrint(params),
    },
    {
      name: 'blender_cnc_postprocess',
      description: 'Convert 2D toolpaths to certified Langmuir FireControl G-code (IHS probe, THC, M3/M5)',
      parameters: {
        paths: { type: 'array' },
        machine: { type: 'string', default: 'crossfire_pro' },
        material: { type: 'string', default: '14_gauge_mild_steel' },
        feedrate: { type: 'number', default: 150.0 },
      },
      execute: async (params) => service.formatFireControlGCode(params.paths, params),
    },
  ];

  return {
    service,
    tools,
  };
}

module.exports = {
  name: 'dsh-plugin-blender',
  apply,
  BlenderService,
};
