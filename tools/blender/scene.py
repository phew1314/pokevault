"""POKÉVAULT draw cinema — Blender scene + animation.
Usage: python scene.py <variant> <start> <end> [samples] [res_scale]
variant: intro | bigA | rev
All three end on the SAME final frame composition: card face-down, top-down camera,
card centred, card height = 55% of frame height (site handoff relies on this).
"""
import bpy, bmesh, math, random, sys, os
from mathutils import Vector, Euler

VAR = sys.argv[1]; F0 = int(sys.argv[2]); F1 = int(sys.argv[3])
SAMPLES = int(sys.argv[4]) if len(sys.argv) > 4 else 24
RES = float(sys.argv[5]) if len(sys.argv) > 5 else 1.0
TEX = '/home/claude/blend/tex/'
OUT = f'/home/claude/blend/out/{VAR}/'
os.makedirs(OUT, exist_ok=True)

FPS = 24
LEN = {'intro': 108, 'bigA': 150, 'rev': 120}[VAR]
CARD_W, CARD_H, CARD_T = 0.063, 0.088, 0.0004
ENV_W, ENV_H, ENV_T = 0.080, 0.115, 0.0030
STRIP = 0.014
FINAL_Y = 0.13
LENS = 50.0
D_FINAL = (CARD_H / 0.55 / 2) / math.tan(math.atan(18 / LENS))

bpy.ops.wm.read_factory_settings(use_empty=True)
S = bpy.context.scene
S.render.fps = FPS
S.frame_start, S.frame_end = 1, LEN

# ---------------------------------------------------------------- helpers
def ease(t): t = max(0, min(1, t)); return t * t * (3 - 2 * t)
def ease_out(t): t = max(0, min(1, t)); return 1 - (1 - t) ** 3
def ease_in(t): t = max(0, min(1, t)); return t ** 3
def seg(f, a, b): return max(0.0, min(1.0, (f - a) / float(b - a)))
def lerp(a, b, t): return a + (b - a) * t

def img(name, cs='sRGB'):
    i = bpy.data.images.load(TEX + name); i.colorspace_settings.name = cs; return i

def new_mat(name):
    m = bpy.data.materials.new(name); m.use_nodes = True
    return m, m.node_tree.nodes, m.node_tree.links, m.node_tree.nodes['Principled BSDF']

def emission_mat(name, color, strength, alpha_falloff=False):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; n = nt.nodes; l = nt.links
    for x in list(n): n.remove(x)
    out = n.new('ShaderNodeOutputMaterial')
    em = n.new('ShaderNodeEmission'); em.inputs['Color'].default_value = (*color, 1); em.inputs['Strength'].default_value = strength
    if alpha_falloff:
        # soft edges: facing-based falloff mixed with transparent
        tr = n.new('ShaderNodeBsdfTransparent'); mix = n.new('ShaderNodeMixShader')
        lw = n.new('ShaderNodeLayerWeight'); lw.inputs['Blend'].default_value = 0.6
        inv = n.new('ShaderNodeMath'); inv.operation = 'POWER'; inv.inputs[1].default_value = 2.5
        one = n.new('ShaderNodeMath'); one.operation = 'SUBTRACT'; one.inputs[0].default_value = 1.0
        l.new(lw.outputs['Facing'], one.inputs[1]); l.new(one.outputs[0], inv.inputs[0])
        l.new(inv.outputs[0], mix.inputs['Fac'])
        l.new(tr.outputs[0], mix.inputs[1]); l.new(em.outputs[0], mix.inputs[2])
        l.new(mix.outputs[0], out.inputs['Surface'])
    else:
        l.new(em.outputs[0], out.inputs['Surface'])
    return m, em

def radial_glow_mat(name, color, strength):
    """Emission with radial alpha falloff on a plane (UV centred)."""
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; n = nt.nodes; l = nt.links
    for x in list(n): n.remove(x)
    out = n.new('ShaderNodeOutputMaterial'); tc = n.new('ShaderNodeTexCoord')
    sub = n.new('ShaderNodeVectorMath'); sub.operation = 'SUBTRACT'; sub.inputs[1].default_value = (0.5, 0.5, 0)
    ln = n.new('ShaderNodeVectorMath'); ln.operation = 'LENGTH'
    mr = n.new('ShaderNodeMapRange'); mr.inputs['From Min'].default_value = 0.5; mr.inputs['From Max'].default_value = 0.0
    pw = n.new('ShaderNodeMath'); pw.operation = 'POWER'; pw.inputs[1].default_value = 2.2
    em = n.new('ShaderNodeEmission'); em.inputs['Color'].default_value = (*color, 1); em.inputs['Strength'].default_value = strength
    tr = n.new('ShaderNodeBsdfTransparent'); mix = n.new('ShaderNodeMixShader')
    l.new(tc.outputs['UV'], sub.inputs[0]); l.new(sub.outputs[0], ln.inputs[0])
    l.new(ln.outputs['Value'], mr.inputs['Value']); l.new(mr.outputs[0], pw.inputs[0])
    l.new(pw.outputs[0], mix.inputs['Fac']); l.new(tr.outputs[0], mix.inputs[1]); l.new(em.outputs[0], mix.inputs[2])
    l.new(mix.outputs[0], out.inputs['Surface'])
    return m, em

def link(o): S.collection.objects.link(o); return o

def outline_mesh(name, pts, thick, uv_box):
    """Extrude a 2D outline (CCW, xy) to thickness; planar UVs from uv_box=(x0,y0,x1,y1)."""
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    vb = [bm.verts.new((x, y, 0)) for x, y in pts]
    vt = [bm.verts.new((x, y, thick)) for x, y in pts]
    bot = bm.faces.new(list(reversed(vb))); top = bm.faces.new(vt)
    n = len(pts)
    sides = [bm.faces.new((vb[i], vb[(i + 1) % n], vt[(i + 1) % n], vt[i])) for i in range(n)]
    top.material_index = 0; bot.material_index = 1
    for f in sides: f.material_index = 2
    uv = bm.loops.layers.uv.new()
    x0, y0, x1, y1 = uv_box
    for f in bm.faces:
        for lp in f.loops:
            co = lp.vert.co
            u = (co.x - x0) / (x1 - x0); v = (co.y - y0) / (y1 - y0)
            if f is bot: u = 1 - u
            lp[uv].uv = (u, v)
    bm.to_mesh(me); bm.free()
    return link(bpy.data.objects.new(name, me))

def rounded_rect(w, h, r, seg_n=6):
    pts = []
    cs = [(w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90), (-w / 2 + r, -h / 2 + r, 180), (w / 2 - r, -h / 2 + r, 270)]
    for cx, cy, a0 in cs:
        for k in range(seg_n + 1):
            a = math.radians(a0 + 90 * k / seg_n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts

def key_obj(o, f, loc=None, rot=None, scale=None):
    if loc is not None: o.location = loc; o.keyframe_insert('location', frame=f)
    if rot is not None: o.rotation_euler = rot; o.keyframe_insert('rotation_euler', frame=f)
    if scale is not None: o.scale = scale if hasattr(scale, '__len__') else (scale,) * 3; o.keyframe_insert('scale', frame=f)

def key_vis(o, f, vis):
    o.hide_render = not vis; o.keyframe_insert('hide_render', frame=f)

def key_val(sock_owner, attr, f, val):
    setattr(sock_owner, attr, val); sock_owner.keyframe_insert(attr, frame=f)

def key_input(node, inp, f, val):
    node.inputs[inp].default_value = val; node.inputs[inp].keyframe_insert('default_value', frame=f)

# ---------------------------------------------------------------- render setup
S.render.engine = 'CYCLES'
S.cycles.device = 'CPU'
S.cycles.samples = SAMPLES
S.cycles.use_adaptive_sampling = True
S.cycles.adaptive_threshold = 0.03
S.cycles.use_denoising = True
S.cycles.denoiser = 'OPENIMAGEDENOISE'
S.cycles.max_bounces = 4; S.cycles.diffuse_bounces = 2; S.cycles.glossy_bounces = 2
S.cycles.transmission_bounces = 2; S.cycles.transparent_max_bounces = 8
S.cycles.caustics_reflective = False; S.cycles.caustics_refractive = False
S.render.use_persistent_data = True
S.render.use_motion_blur = True; S.render.motion_blur_shutter = 0.5
S.render.resolution_x = int(540 * RES); S.render.resolution_y = int(960 * RES)
S.render.resolution_percentage = 100
S.view_settings.view_transform = 'AgX'
try: S.view_settings.look = 'AgX - Punchy'
except Exception: pass
S.view_settings.exposure = -0.35
S.render.image_settings.file_format = 'PNG'

# world: very dark, faint cool fill
w = bpy.data.worlds.new('W'); S.world = w; w.use_nodes = True
bg = w.node_tree.nodes['Background']; bg.inputs['Color'].default_value = (0.006, 0.008, 0.014, 1); bg.inputs['Strength'].default_value = 0.2

# ---------------------------------------------------------------- table (felt)
bpy.ops.mesh.primitive_plane_add(size=3, location=(0, 0, 0)); table = bpy.context.object; table.name = 'Felt'
m, n, l, p = new_mat('felt')
p.inputs['Base Color'].default_value = (0.006, 0.02, 0.017, 1)
p.inputs['Roughness'].default_value = 0.95
p.inputs['Sheen Weight'].default_value = 0.2; p.inputs['Sheen Roughness'].default_value = 0.4
p.inputs['Sheen Tint'].default_value = (0.25, 0.55, 0.45, 1)
noi = n.new('ShaderNodeTexNoise'); noi.inputs['Scale'].default_value = 900; noi.inputs['Detail'].default_value = 8
bump = n.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.25; bump.inputs['Distance'].default_value = 0.0004
l.new(noi.outputs['Fac'], bump.inputs['Height']); l.new(bump.outputs['Normal'], p.inputs['Normal'])
# slight large-scale tone variation
noi2 = n.new('ShaderNodeTexNoise'); noi2.inputs['Scale'].default_value = 6
cr = n.new('ShaderNodeValToRGB'); cr.color_ramp.elements[0].color = (0.004, 0.014, 0.012, 1); cr.color_ramp.elements[1].color = (0.009, 0.028, 0.024, 1)
l.new(noi2.outputs['Fac'], cr.inputs['Fac']); l.new(cr.outputs['Color'], p.inputs['Base Color'])
table.data.materials.append(m)

# out-of-focus bokeh lights far behind (warm venue lights)
random.seed(11)
bokeh_mat, _ = emission_mat('bokeh', (1.0, 0.62, 0.25), 6)
for i in range(14):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=random.uniform(0.006, 0.012), segments=12, ring_count=8,
        location=(random.uniform(-0.9, 0.9), random.uniform(1.4, 2.2), random.uniform(0.15, 0.6)))
    bpy.context.object.data.materials.append(bokeh_mat)

# ---------------------------------------------------------------- envelope
def jag(xs_from, xs_to, y, n_teeth, amp, seed):
    rnd = random.Random(seed); pts = []
    for i in range(n_teeth + 1):
        x = lerp(xs_from, xs_to, i / n_teeth)
        pts.append((x, y + (rnd.uniform(-amp, amp) if 0 < i < n_teeth else 0)))
    return pts

TEAR_Y = ENV_H / 2 - STRIP
tear = jag(ENV_W / 2, -ENV_W / 2, TEAR_Y, 34, 0.0009, 5)  # right -> left
body_pts = [(-ENV_W / 2, -ENV_H / 2), (ENV_W / 2, -ENV_H / 2)] + tear
strip_pts = list(reversed(tear)) + [(ENV_W / 2, ENV_H / 2), (-ENV_W / 2, ENV_H / 2)]
strip_pts = [strip_pts[0]] + strip_pts[1:]
uvb = (-ENV_W / 2, -ENV_H / 2, ENV_W / 2, ENV_H / 2)
env_body = outline_mesh('EnvBody', body_pts, ENV_T, uvb)
env_strip_local = [(x, y - TEAR_Y) for x, y in strip_pts]  # strip origin on tear line
env_strip = outline_mesh('EnvStrip', env_strip_local, ENV_T, (uvb[0], uvb[1] - TEAR_Y, uvb[2], uvb[3] - TEAR_Y))

m_env, n, l, p = new_mat('envelope')
tb = n.new('ShaderNodeTexImage'); tb.image = img('env_base.png')
tf = n.new('ShaderNodeTexImage'); tf.image = img('env_foil.png', 'Non-Color')
gold = (0.83, 0.58, 0.2, 1)
mixc = n.new('ShaderNodeMixRGB'); mixc.inputs['Color2'].default_value = gold
l.new(tf.outputs['Color'], mixc.inputs['Fac']); l.new(tb.outputs['Color'], mixc.inputs['Color1'])
l.new(mixc.outputs['Color'], p.inputs['Base Color'])
l.new(tf.outputs['Color'], p.inputs['Metallic'])
rmap = n.new('ShaderNodeMapRange'); rmap.inputs['To Min'].default_value = 0.42; rmap.inputs['To Max'].default_value = 0.22
l.new(tf.outputs['Color'], rmap.inputs['Value']); l.new(rmap.outputs[0], p.inputs['Roughness'])
pn = n.new('ShaderNodeTexNoise'); pn.inputs['Scale'].default_value = 1500; pn.inputs['Detail'].default_value = 4
pb = n.new('ShaderNodeBump'); pb.inputs['Strength'].default_value = 0.12; pb.inputs['Distance'].default_value = 0.0002
l.new(pn.outputs['Fac'], pb.inputs['Height']); l.new(pb.outputs['Normal'], p.inputs['Normal'])
p.inputs['Coat Weight'].default_value = 0.25; p.inputs['Coat Roughness'].default_value = 0.15
m_back, _, _, pbk = new_mat('env_back'); pbk.inputs['Base Color'].default_value = (0.02, 0.022, 0.03, 1); pbk.inputs['Roughness'].default_value = 0.5
m_edge, _, _, ped = new_mat('paper_edge'); ped.inputs['Base Color'].default_value = (0.55, 0.52, 0.47, 1); ped.inputs['Roughness'].default_value = 0.9
for o in (env_body, env_strip):
    o.data.materials.append(m_env); o.data.materials.append(m_back); o.data.materials.append(m_edge)
    for poly in o.data.polygons: poly.use_smooth = False

# ---------------------------------------------------------------- card
card = outline_mesh('Card', rounded_rect(CARD_W, CARD_H, 0.003), CARD_T, (-CARD_W / 2, -CARD_H / 2, CARD_W / 2, CARD_H / 2))
# card mesh: top face(index0)=BACK of card (face-down card shows its back to the camera)
m_cb, n, l, p = new_mat('cardback')
t = n.new('ShaderNodeTexImage'); t.image = img('cardback.png'); l.new(t.outputs['Color'], p.inputs['Base Color'])
p.inputs['Roughness'].default_value = 0.45; p.inputs['Coat Weight'].default_value = 0.12; p.inputs['Coat Roughness'].default_value = 0.12
m_cf, _, _, pf = new_mat('cardfront'); pf.inputs['Base Color'].default_value = (0.85, 0.85, 0.85, 1); pf.inputs['Roughness'].default_value = 0.3
m_ce, _, _, pe = new_mat('cardedge'); pe.inputs['Base Color'].default_value = (0.75, 0.75, 0.75, 1); pe.inputs['Roughness'].default_value = 0.6
for mm in (m_cb, m_cf, m_ce): card.data.materials.append(mm)

# ---------------------------------------------------------------- camera
cam_data = bpy.data.cameras.new('Cam'); cam_data.lens = LENS; cam_data.sensor_width = 36; cam_data.sensor_fit = 'AUTO'
cam_data.clip_start = 0.005; cam_data.clip_end = 20
cam_data.dof.use_dof = True; cam_data.dof.aperture_fstop = 4.5
cam = link(bpy.data.objects.new('Cam', cam_data)); S.camera = cam
focus = link(bpy.data.objects.new('Focus', None)); cam_data.dof.focus_object = focus

def cam_pose(f, target, theta_deg, dist, shake=0.0, seed=0):
    th = math.radians(theta_deg)
    loc = Vector(target) + Vector((0, -math.sin(th), math.cos(th))) * dist
    rot = Euler((th, 0, 0))
    if shake:
        r = random.Random(seed * 1000 + f)
        loc += Vector((r.uniform(-1, 1), r.uniform(-1, 1), 0)) * shake
        rot.z += r.uniform(-1, 1) * shake * 3
    key_obj(cam, f, loc=loc, rot=rot)
    key_obj(focus, f, loc=Vector(target))

# ---------------------------------------------------------------- lights
def area(name, loc, rot, size, energy, color):
    d = bpy.data.lights.new(name, 'AREA'); d.shape = 'DISK'; d.size = size; d.energy = energy; d.color = color
    o = link(bpy.data.objects.new(name, d)); o.location = loc; o.rotation_euler = rot; return o

key = area('Key', (-0.32, -0.05, 0.42), (math.radians(4), math.radians(-38), 0), 0.3, 5, (1.0, 0.85, 0.68)); key.data.spread = math.radians(38)
rim = area('Rim', (0.3, 0.45, 0.25), (math.radians(-60), math.radians(30), 0), 0.25, 1.5, (0.55, 0.7, 1.0)); rim.data.spread = math.radians(60)
sweepd = bpy.data.lights.new('Sweep', 'SPOT'); sweepd.energy = 0; sweepd.spot_size = math.radians(18); sweepd.spot_blend = 0.6
sweepd.shadow_soft_size = 0.03; sweepd.color = (1.0, 0.9, 0.75)
sweep = link(bpy.data.objects.new('Sweep', sweepd))

# ---------------------------------------------------------------- shared FX objects (big prize)
glow_mat, glow_em = radial_glow_mat('aura', (1.0, 0.72, 0.25), 0.0)
bpy.ops.mesh.primitive_plane_add(size=1, location=(0, FINAL_Y, 0.0002)); aura = bpy.context.object; aura.name = 'Aura'
aura.scale = (0.2, 0.24, 1); aura.data.materials.append(glow_mat)
aura.visible_shadow = False

inner_d = bpy.data.lights.new('Inner', 'POINT'); inner_d.energy = 0; inner_d.shadow_soft_size = 0.01
inner = link(bpy.data.objects.new('Inner', inner_d)); inner.location = (0, TEAR_Y - 0.004, ENV_T * 0.5)

ray_mat, ray_em = radial_glow_mat('flare', (1.0, 0.8, 0.45), 0.0)
bpy.ops.mesh.primitive_plane_add(size=1); flare = bpy.context.object; flare.name = 'Flare'
flare.data.materials.append(ray_mat); flare.visible_shadow = False; flare.visible_diffuse = False; flare.visible_glossy = False
rays = [flare]

dust_mat, dust_em = emission_mat('dust', (1.0, 0.78, 0.35), 0.0)
dusts = []
random.seed(21)
for i in range(70):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=random.uniform(0.0003, 0.0008))
    d = bpy.context.object; d.data.materials.append(dust_mat); d.visible_shadow = False
    d['seed'] = (random.uniform(-0.03, 0.03), random.uniform(0.0, 0.25), random.uniform(0.02, 0.09),
                 random.uniform(-0.03, 0.03), random.uniform(0, 1))
    dusts.append(d)

ring_mat, ring_em = emission_mat('ring', (1.0, 0.75, 0.3), 0.0)
bpy.ops.mesh.primitive_torus_add(major_radius=0.05, minor_radius=0.0012, major_segments=96, minor_segments=8,
                                 location=(0, FINAL_Y, 0.0006))
ring = bpy.context.object; ring.data.materials.append(ring_mat); ring.visible_shadow = False

# paper flakes from the tear
flake_mat = m_edge
flakes = []
random.seed(31)
for i in range(6):
    bpy.ops.mesh.primitive_plane_add(size=random.uniform(0.0012, 0.0022))
    fl = bpy.context.object; fl.data.materials.append(m_edge)
    fl['v'] = (random.uniform(-0.04, 0.04), random.uniform(0.0, 0.05), random.uniform(0.04, 0.12), random.uniform(5, 15), random.uniform(-0.035, 0.035))
    flakes.append(fl)

# ================================================================= ANIMATION
def card_final(f):
    key_obj(card, f, loc=(0, FINAL_Y, 0.0002), rot=(0, 0, 0))

def hide_fx(f):
    for o in [aura, ring] + rays + dusts: key_vis(o, f, False)

def intro_common(f, big=False):
    """Frames 1..~100 of intro; big=True adds the mid-sequence special inside."""
    # sweep light: crosses the envelope early
    s = seg(f, 4, 40)
    sweep.location = (lerp(-0.35, 0.35, ease(s)), -0.25, 0.35)
    sweep.rotation_euler = (Vector((0, 0, 0)) - Vector(sweep.location)).to_track_quat('-Z', 'Y').to_euler()
    sweep.keyframe_insert('location', frame=f); sweep.keyframe_insert('rotation_euler', frame=f)
    key_val(sweepd, 'energy', f, 3.0 * math.sin(math.pi * s))
    # lights
    key_val(key.data, 'energy', f, lerp(2.5, 5, ease(seg(f, 1, 24))))

    # camera
    c1 = seg(f, 1, 40); c2 = ease(seg(f, 58, 96))
    th = lerp(lerp(60, 50, ease(c1)), 0.0, c2)
    dist = lerp(lerp(0.30, 0.235, ease(c1)), D_FINAL, c2)
    tgt = (0, lerp(0.005, FINAL_Y, c2), 0)
    shake = 0.0
    if big: shake = 0.0012 * math.sin(math.pi * seg(f, 44, 80))
    cam_pose(f, tgt, th, dist, shake=shake, seed=1)

    # envelope body (with shake in big variant)
    jit = Vector((0, 0, 0)); jr = Euler((0, 0, 0))
    if big and 44 <= f <= 80:
        r = random.Random(f); a = 0.0012 * math.sin(math.pi * seg(f, 44, 80))
        jit = Vector((r.uniform(-a, a), r.uniform(-a, a), abs(r.uniform(0, a))))
        jr = Euler((r.uniform(-a, a) * 4, r.uniform(-a, a) * 4, r.uniform(-a, a) * 6))
    key_obj(env_body, f, loc=jit, rot=jr)

    # tear strip: peel (36-44), fly (44-58)
    pe = ease(seg(f, 34, 44)); fl = ease_in(seg(f, 43, 58))
    sl = Vector((0, TEAR_Y, 0)) + jit
    sl += Vector((0.0, 0.002 * pe, 0.004 * pe)) + Vector((0.25, 0.05, 0.12)) * fl
    rot = Euler((math.radians(-14 * pe), math.radians(-18 * pe - 80 * fl), math.radians(10 * fl)))
    key_obj(env_strip, f, loc=sl, rot=rot)

    # flakes
    for i, fo in enumerate(flakes):
        vx, vy, vz, spin, x0 = fo['v']; tt = (f - 40) / FPS
        if tt < 0:
            key_obj(fo, f, loc=(x0, TEAR_Y, ENV_T), rot=(0, 0, 0)); key_vis(fo, f, False)
        else:
            z = ENV_T + vz * tt - 0.5 * 0.35 * tt * tt
            key_obj(fo, f, loc=(x0 + vx * tt, TEAR_Y + vy * tt, max(0.0003, z)), rot=(spin * tt, spin * 0.7 * tt, 0))
            key_vis(fo, f, f < 66)

    # card slides out (52-86), drops onto felt
    cs = ease(seg(f, 52, 86))
    cy = lerp(-0.004, FINAL_Y, cs)
    inside = cy < TEAR_Y + CARD_H / 2
    cz = lerp(ENV_T * 0.45, 0.0002, ease(seg(f, 78, 90)))
    tilt = math.radians(4) * math.sin(math.pi * seg(f, 70, 90))
    key_obj(card, f, loc=Vector((0, cy, cz)) + (jit if inside else Vector()), rot=(tilt, 0, 0))

    # envelope gently pulled back/out once the card is out
    if f > 70:
        out = ease(seg(f, 70, 96))
        key_obj(env_body, f, loc=jit + Vector((0, -0.05 * out, 0)), rot=jr)

import colorsys
def big_fx(f, t0, origin_fn, card_glow_from):
    """Gold rays + dust + aura. origin_fn(f)->Vector where light pours from."""
    o = origin_fn(f)
    on = seg(f, t0, t0 + 10)
    th = Vector(cam.rotation_euler).x
    key_obj(flare, f, loc=o + Vector((0, 0.004, 0.006)), rot=Euler((th, 0, f * 0.02)), scale=(0.16, 0.16, 1))
    key_vis(flare, f, f >= t0)
    key_input(ray_em, 'Strength', f, 3.5 * on * (0.75 + 0.25 * math.sin(f * 0.9)))
    ray_em.inputs['Color'].default_value = (*colorsys.hsv_to_rgb((f * 0.035) % 1.0, 0.35, 1.0), 1); ray_em.inputs['Color'].keyframe_insert('default_value', frame=f)
    # rainbow-shifting inner light
    hue = (f * 0.035) % 1.0
    rgb = colorsys.hsv_to_rgb(hue, 0.55, 1.0)
    inner_d.color = rgb; inner_d.keyframe_insert('color', frame=f)
    key_val(inner_d, 'energy', f, 2.5 * on)
    inner.location = o; inner.keyframe_insert('location', frame=f)
    # dust rising
    for d in dusts:
        x0, delay, vz, vx, ph = d['seed']
        tt = (f - t0) / FPS - delay
        if tt < 0:
            key_vis(d, f, False); key_obj(d, f, loc=o)
        else:
            key_obj(d, f, loc=o + Vector((x0 + vx * tt + 0.004 * math.sin(tt * 6 + ph * 6), 0.02 * tt, 0.004 + vz * tt)))
            key_vis(d, f, True)
    key_input(dust_em, 'Strength', f, 25.0 * on)
    # aura under card
    ag = seg(f, card_glow_from, card_glow_from + 18)
    key_vis(aura, f, f >= card_glow_from)
    key_input(glow_em, 'Strength', f, 0.9 * ag * (0.85 + 0.15 * math.sin(f * 0.25)))

def fade_rays(f, a, b):
    k = 1 - seg(f, a, b)
    key_input(ray_em, 'Strength', f, ray_em.inputs['Strength'].default_value * k)
    key_input(dust_em, 'Strength', f, dust_em.inputs['Strength'].default_value * (0.4 + 0.6 * k))

def ring_burst(f, t0, dur=20):
    rb = seg(f, t0, t0 + dur)
    key_vis(ring, f, t0 <= f <= t0 + dur)
    key_obj(ring, f, scale=lerp(0.3, 2.6, ease_out(rb)))
    key_input(ring_em, 'Strength', f, 12 * (1 - rb) ** 1.5)

# ---- build keyframes for the whole clip
for f in range(1, LEN + 1):
    S.frame_set(f)
    if VAR == 'intro':
        hide_fx(f); key_input(glow_em, 'Strength', f, 0); key_val(inner_d, 'energy', f, 0)
        intro_common(f)
        if f > 96: card_final(f)
    elif VAR == 'bigA':
        hide_fx(f)
        intro_common(f, big=True)
        if f > 96: card_final(f)
    elif VAR == 'rev':
        pass

# bigA needs card-following origin; do it in a clean second pass
if VAR == 'bigA':
    for f in range(42, LEN + 1):
        S.frame_set(f)
        def origin(ff):
            S.frame_set(ff)
            return Vector((0, TEAR_Y + 0.002, ENV_T * 0.6)) + Vector(env_body.location)
        big_fx(f, 42, origin, 84)
        if f >= 100:
            fade_rays(f, 100, 130)
        ring_burst(f, 88, 22)
    # warmer key light for the payoff
    for f in range(1, LEN + 1):
        key_val(key.data, 'energy', f, 5 if f < 88 else lerp(5, 3.5, seg(f, 88, 110)))

if VAR == 'rev':
    # top-down final framing throughout; dark, flicker, beam, card descends spinning, lands.
    import colorsys
    for f in range(1, LEN + 1):
        S.frame_set(f)
        for o in [env_body, env_strip] + flakes: key_vis(o, f, False)
        key_val(sweepd, 'energy', f, 0)
        # flicker: blackout 1-8, stutters 8-34, dark 34-44
        fl_pattern = {9: .5, 10: 0, 12: .8, 13: .1, 15: 1, 16: 0, 19: .6, 20: 0, 24: .3, 26: 0, 29: .9, 30: .05, 33: .4}
        base = 0
        if f in fl_pattern: base = fl_pattern[f]
        elif 34 <= f < 46: base = 0.0
        elif f >= 46: base = 0.35 + 0.65 * ease(seg(f, 70, 100))
        key_val(key.data, 'energy', f, 5 * base)
        key_val(rim.data, 'energy', f, 1.5 * (base if f < 46 else 1.0))
        key_input(bg, 'Strength', f, 0.08 if f < 46 else 0.2)
        # camera: slowly pushes, shakes on landing
        land = 88
        sh = 0.0025 * max(0, 1 - (f - land) / 10) if f >= land else 0.0
        cam_pose(f, (0, FINAL_Y, 0), 0.0, lerp(D_FINAL * 1.25, D_FINAL, ease(seg(f, 1, 100))), shake=sh, seed=3)
        # beam of gold from above (46-100)
        on = ease(seg(f, 44, 56)) * (1 - 0.7 * seg(f, 96, 118))
        key_obj(flare, f, loc=(0, FINAL_Y, 0.0001), rot=(0, 0, f * 0.03), scale=(0.2 + 0.08 * on, 0.24 + 0.08 * on, 1))
        key_vis(flare, f, f >= 44)
        key_input(ray_em, 'Strength', f, 3.0 * on * (0.85 + 0.15 * math.sin(f * 1.3)))
        # card descends spinning (face-down, spins flat), lands at f=88
        dsc = seg(f, 50, land)
        z = lerp(0.05, 0.0002, ease_in(dsc) * 0.35 + ease(dsc) * 0.65)
        spin = (1 - ease_out(dsc)) * math.radians(720)
        if f < 50:
            key_obj(card, f, loc=(0, FINAL_Y, 0.05), rot=(0, 0, 0)); key_vis(card, f, False)
        else:
            key_vis(card, f, True)
            key_obj(card, f, loc=(0, FINAL_Y, z), rot=(0, 0, spin))
        if f >= 100: card_final(f)
        # aura + dust + ring on landing
        key_vis(aura, f, f >= 60)
        key_input(glow_em, 'Strength', f, 0.9 * ease(seg(f, 60, 92)) * (0.85 + 0.15 * math.sin(f * 0.25)))
        for d in dusts:
            x0, delay, vz, vx, ph = d['seed']; tt = (f - land) / FPS - delay * 0.4
            if tt < 0:
                key_vis(d, f, False); key_obj(d, f, loc=(0, FINAL_Y, 0))
            else:
                ang = ph * 2 * math.pi
                rr = 0.02 + 0.08 * (1 - math.exp(-tt * 2.5))
                key_obj(d, f, loc=(math.cos(ang) * rr, FINAL_Y + math.sin(ang) * rr * 1.3, 0.002 + vz * tt * 0.5))
                key_vis(d, f, True)
        key_input(dust_em, 'Strength', f, 25.0 * (1 - 0.6 * seg(f, 100, 120)))
        ring_burst(f, land, 22)
        key_val(inner_d, 'energy', f, 0)
        key_vis(env_body, f, False)

# keep big FX out of intro / pre-FX frames of bigA
if VAR == 'bigA':
    for f in range(1, 42):
        hide_fx(f); key_input(ray_em, 'Strength', f, 0); key_input(dust_em, 'Strength', f, 0)
        key_input(glow_em, 'Strength', f, 0); key_val(inner_d, 'energy', f, 0)

# linear interpolation for all generated keys (per-frame keys, so no overshoot)
for ob in list(bpy.data.objects) + list(bpy.data.lights) + list(bpy.data.materials) + [S.world]:
    ad = getattr(ob, 'animation_data', None)
    trees = [ob]
    if hasattr(ob, 'node_tree') and ob.node_tree: trees.append(ob.node_tree)
    for tobj in trees:
        ad = getattr(tobj, 'animation_data', None)
        if ad and ad.action:
            try:
                fcs = ad.action.fcurves
            except AttributeError:
                fcs = [fc for layer in ad.action.layers for strip in layer.strips for bag in strip.channelbags for fc in bag.fcurves]
            for fc in fcs:
                for kp in fc.keyframe_points:
                    kp.interpolation = 'CONSTANT' if fc.data_path == 'hide_render' else 'LINEAR'

# ---------------------------------------------------------------- compositor
ng = bpy.data.node_groups.new('Comp', 'CompositorNodeTree'); S.compositing_node_group = ng
ng.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
rl = ng.nodes.new('CompositorNodeRLayers'); go = ng.nodes.new('NodeGroupOutput')
g1 = ng.nodes.new('CompositorNodeGlare'); g1.inputs['Type'].default_value = 'Fog Glow'
g1.inputs['Highlights Threshold'].default_value = 2.0; g1.inputs['Strength'].default_value = 0.35; g1.inputs['Size'].default_value = 0.6
g2 = ng.nodes.new('CompositorNodeGlare'); g2.inputs['Type'].default_value = 'Streaks'
g2.inputs['Highlights Threshold'].default_value = (99.0 if VAR == 'intro' else 6.0); g2.inputs['Strength'].default_value = 0.35; g2.inputs['Streaks'].default_value = 6
g2.inputs['Fade'].default_value = 0.93; g2.inputs['Streaks Angle'].default_value = 0.26
ng.links.new(rl.outputs['Image'], g1.inputs['Image']); ng.links.new(g1.outputs['Image'], g2.inputs['Image'])
ng.links.new(g2.outputs['Image'], go.inputs[0])
S.render.use_compositing = True

# ---------------------------------------------------------------- render
import time
for f in range(F0, F1 + 1):
    S.frame_set(f)
    S.render.filepath = OUT + f'{f:04d}.png'
    t = time.time()
    bpy.ops.render.render(write_still=True)
    print(f'[{VAR}] frame {f} {time.time() - t:.1f}s', flush=True)
