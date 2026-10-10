"""
Parametric CAD Generator for Agentic Blender.
Produces robust Blender Python code for mechanical assemblies, modular canisters,
calibrated dosing holders, dry filter bases, and Langmuir CNC brackets.
"""

import math

def generate_modular_dispenser_code(
    base_shape="cylinder",  # "cylinder", "hexagon", "rectangle"
    radius=1.8,
    height=4.0,
    wall_thickness=0.25,
    include_filter=True,
    include_holders=True,
    include_lid=True,
    units="inches"
):
    """
    Generates a complete, self-contained Blender Python script to build
    a modular powder dispenser ecosystem with separate components.
    """
    vertices = 32
    if base_shape == "hexagon":
        vertices = 6
    elif base_shape == "rectangle":
        vertices = 4

    script = f'''import bpy, bmesh, math

# 1. Clean existing scene safely
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

mat_body = get_or_create_mat('Anodized_Body', (0.1, 0.45, 0.85, 1.0), roughness=0.25, metallic=0.9)
mat_lid = get_or_create_mat('Matte_Polymer', (0.12, 0.12, 0.15, 1.0), roughness=0.45, metallic=0.1)
mat_filter = get_or_create_mat('Filter_Grate', (0.75, 0.75, 0.8, 1.0), roughness=0.2, metallic=0.95)

# --- 1. Main Canister Reservoir ---
radius = {radius}
height = {height}
wall = {wall_thickness}

bpy.ops.mesh.primitive_cylinder_add(
    vertices={vertices},
    radius=radius,
    depth=height,
    location=(0, 0, height / 2.0)
)
body = bpy.context.active_object
body.name = "Dispenser_Main_Body"
body.data.materials.append(mat_body)

# Interior cavity boolean
inner_r = max(0.1, radius - wall)
inner_h = max(0.1, height - wall)
bpy.ops.mesh.primitive_cylinder_add(
    vertices={vertices},
    radius=inner_r,
    depth=inner_h,
    location=(0, 0, (height / 2.0) + (wall / 2.0))
)
core = bpy.context.active_object
core.name = "Interior_Core"
cbool = body.modifiers.new(name="Cavity", type='BOOLEAN')
cbool.object = core
cbool.operation = 'DIFFERENCE'
bpy.context.view_layer.objects.active = body
bpy.ops.object.modifier_apply(modifier="Cavity")
bpy.data.objects.remove(core, do_unlink=True)
'''

    if include_filter:
        script += f'''
# --- 2. Dry Desiccant & Humidity Filter Base ---
filter_x = radius * 2.5
bpy.ops.mesh.primitive_cylinder_add(
    vertices={vertices},
    radius=radius,
    depth=0.8,
    location=(filter_x, 0, 0.4)
)
filter_base = bpy.context.active_object
filter_base.name = "Dry_Filter_Base"
filter_base.data.materials.append(mat_filter)

# Perforations in filter base for air circulation
for i in range(8):
    ang = i * (2.0 * math.pi / 8.0)
    hx = filter_x + (radius * 0.55) * math.cos(ang)
    hy = (radius * 0.55) * math.sin(ang)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.12, depth=1.0, location=(hx, hy, 0.4))
    hole = bpy.context.active_object
    hbool = filter_base.modifiers.new(name=f"Hole_{{i}}", type='BOOLEAN')
    hbool.object = hole
    hbool.operation = 'DIFFERENCE'
    bpy.context.view_layer.objects.active = filter_base
    bpy.ops.object.modifier_apply(modifier=f"Hole_{{i}}")
    bpy.data.objects.remove(hole, do_unlink=True)
'''

    if include_holders:
        script += f'''
# --- 3. Calibrated Precision Dosing Holders ---
holder_x = -radius * 2.5
# Standard well (0.1g)
bpy.ops.mesh.primitive_cylinder_add(radius=1.2, depth=0.9, location=(holder_x, -1.8, 0.45))
h_std = bpy.context.active_object
h_std.name = "Dosing_Holder_Standard_0.1g"
h_std.data.materials.append(mat_body)

bpy.ops.mesh.primitive_cylinder_add(radius=0.5, depth=0.6, location=(holder_x, -1.8, 0.65))
well1 = bpy.context.active_object
wbool1 = h_std.modifiers.new(name="WellBool", type='BOOLEAN')
wbool1.object = well1
wbool1.operation = 'DIFFERENCE'
bpy.context.view_layer.objects.active = h_std
bpy.ops.object.modifier_apply(modifier="WellBool")
bpy.data.objects.remove(well1, do_unlink=True)

# Micro well (25mg funnel)
bpy.ops.mesh.primitive_cylinder_add(radius=1.2, depth=0.9, location=(holder_x, 1.8, 0.45))
h_micro = bpy.context.active_object
h_micro.name = "Dosing_Holder_Micro_25mg"
h_micro.data.materials.append(mat_body)

bpy.ops.mesh.primitive_cone_add(radius1=0.4, radius2=0.08, depth=0.6, location=(holder_x, 1.8, 0.65))
well2 = bpy.context.active_object
wbool2 = h_micro.modifiers.new(name="ConeWell", type='BOOLEAN')
wbool2.object = well2
wbool2.operation = 'DIFFERENCE'
bpy.context.view_layer.objects.active = h_micro
bpy.ops.object.modifier_apply(modifier="ConeWell")
bpy.data.objects.remove(well2, do_unlink=True)
'''

    if include_lid:
        script += f'''
# --- 4. Knurled Airtight Twist Cap ---
lid_y = radius * 2.5
bpy.ops.mesh.primitive_cylinder_add(radius=radius * 1.06, depth=0.7, location=(0, lid_y, 0.35))
lid = bpy.context.active_object
lid.name = "Knurled_Airtight_Lid"
lid.data.materials.append(mat_lid)

# Knurling ridges around lid circumference
num_ridges = 24
for i in range(num_ridges):
    ang = i * (2.0 * math.pi / float(num_ridges))
    rx = (radius * 1.06) * math.cos(ang)
    ry = lid_y + (radius * 1.06) * math.sin(ang)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.06, depth=0.7, location=(rx, ry, 0.35))
    ridge = bpy.context.active_object
    ridge.data.materials.append(mat_lid)
'''

    script += '''
# Camera & Lighting
bpy.ops.object.camera_add(location=(9.0, -9.0, 7.5), rotation=(math.radians(60), 0, math.radians(45)))
bpy.context.scene.camera = bpy.context.active_object
bpy.ops.object.light_add(type='SUN', location=(4, -4, 10))
bpy.context.active_object.data.energy = 4.0
print("[CAD Generator] Modular dispenser ecosystem created successfully.")
'''
    return script

def generate_cnc_bracket_code(length=6.0, width=3.5, thickness=0.125, hole_dia=0.375, corner_fillet=0.35):
    """
    Generates a Blender Python script to build a precision CNC mounting plate
    suitable for Langmuir CrossFire plasma cutting or MR-1 milling.
    """
    return f'''import bpy, bmesh, math

if bpy.context.object and bpy.context.object.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

mat_metal = bpy.data.materials.new(name='Plate_Steel')
mat_metal.use_nodes = True
bsdf = mat_metal.node_tree.nodes.get('Principled BSDF')
if bsdf:
    bsdf.inputs['Base Color'].default_value = (0.7, 0.72, 0.75, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.3
    bsdf.inputs['Metallic'].default_value = 0.9

length = {length}
width = {width}
thickness = {thickness}
hole_radius = {hole_dia / 2.0}

bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, thickness / 2.0))
plate = bpy.context.active_object
plate.name = "Langmuir_CNC_Mounting_Plate"
plate.scale = (length, width, thickness)
bpy.ops.object.transform_apply(scale=True)
plate.data.materials.append(mat_metal)

# Corner mounting holes
offset_x = (length / 2.0) - 0.5
offset_y = (width / 2.0) - 0.5
for x in [-offset_x, offset_x]:
    for y in [-offset_y, offset_y]:
        bpy.ops.mesh.primitive_cylinder_add(radius=hole_radius, depth=thickness * 3.0, location=(x, y, 0))
        hole = bpy.context.active_object
        hbool = plate.modifiers.new(name="Hole", type='BOOLEAN')
        hbool.object = hole
        hbool.operation = 'DIFFERENCE'
        bpy.context.view_layer.objects.active = plate
        bpy.ops.object.modifier_apply(modifier="Hole")
        bpy.data.objects.remove(hole, do_unlink=True)

# Edge Bevel
bev = plate.modifiers.new(name="Fillet", type='BEVEL')
bev.width = {corner_fillet}
bev.segments = 4
bpy.ops.object.modifier_apply(modifier="Fillet")

bpy.ops.object.camera_add(location=(0, -7.0, 6.0), rotation=(math.radians(50), 0, 0))
bpy.context.scene.camera = bpy.context.active_object
bpy.ops.object.light_add(type='SUN', location=(2, -3, 8))
print("[CAD Generator] Precision CNC mounting plate created.")
'''

def generate_threaded_lip_code(radius=1.8, pitch=0.15, turns=3, internal=False):
    """
    Generates procedural helical screw thread geometry for modular canister lips and caps.
    """
    direction = -1 if internal else 1
    return f'''import bpy, bmesh, math

radius = {radius}
pitch = {pitch}
turns = {turns}
direction = {direction}

# Create helical ridge profile
total_height = pitch * turns
steps_per_turn = 32
total_steps = turns * steps_per_turn

bpy.ops.mesh.primitive_cylinder_add(
    radius=radius,
    depth=total_height,
    location=(0, 0, total_height / 2.0)
)
core = bpy.context.active_object
core.name = "Thread_Base_Core"

# Generate spiral helical ridges
for step in range(total_steps):
    theta = step * (2.0 * math.pi / float(steps_per_turn))
    z = (step / float(total_steps)) * total_height
    x = (radius + (direction * 0.08)) * math.cos(theta)
    y = (radius + (direction * 0.08)) * math.sin(theta)
    bpy.ops.mesh.primitive_cylinder_add(
        radius=0.07,
        depth=pitch * 0.8,
        location=(x, y, z),
        rotation=(0, math.radians(90), theta)
    )
    ridge = bpy.context.active_object
    ridge.name = f"Helix_Node_{{step}}"

print("[CAD Generator] Procedural helical threads generated: {turns} turns at pitch {pitch} in.")
'''

def generate_snap_fit_joint_code(radius=1.8, count=4, tab_width=0.3, tab_height=0.2):
    """
    Generates interlocking cantilever snap-fit tabs for modular toolless assembly.
    """
    return f'''import bpy, bmesh, math

radius = {radius}
count = {count}
tab_w = {tab_width}
tab_h = {tab_height}

bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=0.8, location=(0, 0, 0.4))
collar = bpy.context.active_object
collar.name = "Snap_Fit_Collar"

for i in range(count):
    ang = i * (2.0 * math.pi / float(count))
    tx = (radius - 0.05) * math.cos(ang)
    ty = (radius - 0.05) * math.sin(ang)
    bpy.ops.mesh.primitive_cube_add(
        size=1.0,
        location=(tx, ty, 0.4 + (tab_h / 2.0)),
        rotation=(0, 0, ang)
    )
    tab = bpy.context.active_object
    tab.scale = (0.1, tab_w, tab_h)
    bpy.ops.object.transform_apply(scale=True)
    tab.name = f"Snap_Tab_{{i}}"

print(f"[CAD Generator] Generated {{count}} cantilever snap-fit joint tabs.")
'''

