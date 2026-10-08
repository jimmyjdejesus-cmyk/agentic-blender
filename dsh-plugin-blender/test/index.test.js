const { test } = require('node:test');
const assert = require('node:assert');
const { name, apply, BlenderService } = require('../index.js');

test('1. Plugin module metadata and exports', () => {
  assert.strictEqual(name, 'dsh-plugin-blender');
  assert.strictEqual(typeof apply, 'function');
  assert.strictEqual(typeof BlenderService, 'function');
});

test('2. BlenderService initialization & audit ledger', () => {
  const service = new BlenderService({}, { host: '127.0.0.1', port: 9876 });
  assert.strictEqual(service.host, '127.0.0.1');
  assert.strictEqual(service.port, 9876);
  assert.strictEqual(service.auditLog.length, 0);

  const entry = service.logAudit('test_action', { foo: 'bar' });
  assert.strictEqual(service.auditLog.length, 1);
  assert.strictEqual(entry.action, 'test_action');
  assert.strictEqual(entry.success, true);
});

test('3. Parametric CAD script generation', () => {
  const service = new BlenderService({});
  
  // Cylinder test
  const cylScript = service.generateCadScript({ baseShape: 'cylinder', radius: 2.0, height: 4.5 });
  assert.ok(cylScript.includes('vertices=32'));
  assert.ok(cylScript.includes('Dispenser_Main_Body'));
  assert.ok(cylScript.includes('Dry_Filter_Base'));
  assert.ok(cylScript.includes('Dosing_Holder_0.1g'));
  assert.ok(cylScript.includes('Knurled_Airtight_Lid'));

  // Hexagon test
  const hexScript = service.generateCadScript({ baseShape: 'hexagon' });
  assert.ok(hexScript.includes('vertices=6'));
});

test('4. 3D Printing Pre-Flight Validator', () => {
  const service = new BlenderService({});

  // Watertight pass
  const valid = service.validate3DPrint({
    nonManifoldEdges: 0,
    dimensionsMm: [60, 60, 80],
    volumeCm3: 35.0,
    material: 'pla',
    printer: 'bambu_x1c',
  });
  assert.strictEqual(valid.isPrintable, true);
  assert.strictEqual(valid.isWatertight, true);
  assert.strictEqual(valid.errors.length, 0);
  assert.strictEqual(valid.estimatedMassG, Math.round(35.0 * 1.24 * 100) / 100);

  // Non-manifold failure
  const nonManifold = service.validate3DPrint({
    nonManifoldEdges: 5,
  });
  assert.strictEqual(nonManifold.isPrintable, false);
  assert.strictEqual(nonManifold.isWatertight, false);
  assert.ok(nonManifold.errors[0].includes('not watertight'));

  // Build plate overflow
  const overflow = service.validate3DPrint({
    dimensionsMm: [300, 300, 300],
    printer: 'prusa_mk4', // bed is 250x210x220
  });
  assert.strictEqual(overflow.isPrintable, false);
  assert.ok(overflow.errors[0].includes('exceed prusa_mk4 bed envelope'));
});

test('5. Langmuir FireControl G-code post-processor', () => {
  const service = new BlenderService({});
  const path = [[0, 0], [4, 0], [4, 2], [0, 2], [0, 0]];
  const gcode = service.formatFireControlGCode([path], {
    machine: 'crossfire_pro',
    material: '14_gauge_mild_steel',
    feedrate: 150.0,
  });

  assert.ok(gcode.includes('G90 G94'));
  assert.ok(gcode.includes('G20'));
  assert.ok(gcode.includes('G54'));
  assert.ok(gcode.includes('G38.2 Z-5.0000 F60.0'));
  assert.ok(gcode.includes('M3 (Torch ON)'));
  assert.ok(gcode.includes('H1 (THC ON)'));
  assert.ok(gcode.includes('G1 X4.0000 Y0.0000 F150.0'));
  assert.ok(gcode.includes('H0 (THC OFF)'));
  assert.ok(gcode.includes('M5 (Torch OFF)'));
  assert.ok(gcode.includes('M30 (End of Program)'));
});

test('6. Cordis apply() and DSH Tool Catalog Registration', () => {
  const mockCtx = {
    provide: (name) => {
      mockCtx[name] = true;
    },
  };

  const { service, tools } = apply(mockCtx, { port: 9876 });
  assert.ok(service instanceof BlenderService);
  assert.strictEqual(tools.length, 5);

  const toolNames = tools.map((t) => t.name);
  assert.ok(toolNames.includes('blender_status'));
  assert.ok(toolNames.includes('blender_inspect_scene'));
  assert.ok(toolNames.includes('blender_cad_generate'));
  assert.ok(toolNames.includes('blender_3dprint_preflight'));
  assert.ok(toolNames.includes('blender_cnc_postprocess'));
});
