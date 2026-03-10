"""
Kinematic Indicator Nest -- FreeCAD Scripted CAD
================================================
Two-phase product: exact-constraint kinematic coupling with
integrated LED operator feedback for manual assembly stations.

Phase 1: Passive indicator nest -- hall effect + comparator + LED
Phase 2: Lockable precision nest -- adds electromagnet coil lock

Kinematic principle:
  3x 5mm ball bearings in 3x two-pin dowel cradles
  35mm bolt circle, 120 deg spacing
  6 Hertzian contact lines = exact constraint (6 DOF)
  Hall effect detects 0.01-0.05mm displacement threshold

Generates:
  - Base plate (Phase 1, with Phase 2 groove unpopulated)
  - Nest plate Variant A (pin location)
  - Nest plate Variant B (ledge location)
  - Nest plate blank (customer machines own features)
  - Coupled and exploded assemblies
  - STL exports for each body

Manufacturing:
  Base: 80x80x12mm 6061-T6, black anodize
  Nest: 80x80x8mm 6061-T6, natural anodize
  Cradles: 3.3mm ground dowel pins, H7/h6 press fit
  Balls: 5mm chrome steel grade 25, press fit

Usage:
  freecadcmd.exe kinematic_nest.py
  -- or paste into FreeCAD macro editor
"""

import sys
import os
import math

import FreeCAD
import Part
import Mesh

try:
    OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    OUTPUT_DIR = os.path.abspath(".")


# =======================================================================
# CONSTANTS
# =======================================================================

# === Base plate =======================================================
BP_W = 80.0           # width mm (X)
BP_D = 80.0           # depth mm (Y)
BP_H = 12.0           # thickness mm (Z)
BP_CORNER_R = 3.0     # corner radius for finished look

# Center bore (utility passthrough / wire routing)
BP_CENTER_HOLE_DIA = 12.0

# 4x M5 mounting holes -- corners, 10mm inset from edges
BP_MOUNT_INSET = 10.0
BP_MOUNT_DIA = 5.5    # M5 clearance
BP_MOUNT_CBORE_DIA = 9.0
BP_MOUNT_CBORE_DEPTH = 4.0

# === Kinematic features (shared geometry) ============================
KC_BOLT_CIRCLE_R = 35.0 / 2.0  # 35mm bolt circle = 17.5mm radius
# Correction: "35mm bolt circle" = 35mm diameter = 17.5mm radius.
# But that's very tight for 80mm plate. Re-reading spec:
# "three 5mm ball bearings in three two-pin dowel cradles, 35mm bolt circle"
# 35mm bolt circle diameter = 17.5mm radius. That fits fine in 40mm half-width.
KC_BOLT_CIRCLE_R = 17.5

# Dowel pins -- 3.3mm diameter for 5mm ball seating
# Ball_r + Pin_r = 2.5 + 1.65 = 4.15mm
# Pin spacing = (ball_r + pin_r) x =2 = 4.15 x 1.414 = 5.87mm for 45 deg seat
PIN_DIA = 3.3
PIN_HOLE_DIA = 3.27       # H7/h6 press fit in aluminum
PIN_LENGTH = 10.0          # total pin length
PIN_DEPTH = 8.0            # blind hole depth
PIN_PROTRUDE = 2.0         # proud of face
PIN_SPACING = 5.87         # center-to-center between pin pair

# Ball bearings -- 5mm chrome steel
BALL_DIA = 5.0
BALL_POCKET_DIA = 4.97     # press fit
BALL_POCKET_DEPTH = 3.5    # blind
BALL_PROTRUDE = 1.5        # proud of nest plate face
# Check: pocket_depth=3.5, ball_r=2.5, so ball center at 3.5-2.5=1.0 above pocket bottom
# Ball protrusion = ball_r - (pocket_depth - ball_r) = 2.5 - (3.5 - 2.5) = 2.5 - 1.0 = 1.5mm

CRADLE_COUNT = 3
CRADLE_ANGLE_START = 0.0   # first cradle at 0 deg (along +X)

# === Hall effect sensor ==============================================
SENSOR_ANGLE = 60.0        # between cradle 1 and 2
SENSOR_RADIUS = KC_BOLT_CIRCLE_R
SENSOR_POCKET_DIA = 8.0
SENSOR_POCKET_DEPTH = 6.0
SENSOR_MOUNT_SPACING = 7.0   # M2 holes, 7mm apart
SENSOR_MOUNT_DIA = 2.0       # M2 tap drill
SENSOR_MOUNT_DEPTH = 4.0

# === Magnet (nest plate) =============================================
MAGNET_POCKET_DIA = 6.2
MAGNET_POCKET_DEPTH = 3.2

# === Spring retention ================================================
# 3x at 60 deg offset from cradles, at larger radius
SPRING_RADIUS = 28.0       # between kinematic circle and plate edge
SPRING_HOLE_DIA = 3.2      # M3 clearance through nest plate
SPRING_CBORE_DIA = 7.0     # spring seat counterbore
SPRING_CBORE_DEPTH = 2.0
SPRING_TAP_DIA = 2.5       # M3 tap drill in base plate
SPRING_TAP_DEPTH = 5.0
SPRING_COUNT = 3

# === Electromagnet groove (Phase 2 -- machined in Phase 1, unpopulated) ==
EMAG_OD = 28.0             # outer diameter of annular groove
EMAG_ID = 20.0             # inner diameter
EMAG_DEPTH = 5.0           # groove depth from top face

# Keeper ring bore (Phase 2 -- machined in Phase 1)
KEEPER_OD = 30.0
KEEPER_ID = 18.0
KEEPER_DEPTH = 1.5         # pressed flush with top face

# === PCB recess (bottom face of base plate) ==========================
PCB_W = 35.0               # along X
PCB_D = 25.0               # along Y (swapped to fit 25x35 board)
PCB_H = 5.0                # pocket depth
PCB_OFFSET_X = 0.0         # centered
PCB_OFFSET_Y = 20.0        # offset toward one edge for wire routing

# === LED window (side face, 30 deg angled upward) =======================
LED_SLOT_W = 8.0            # slot width along plate edge
LED_SLOT_H = 5.0            # slot height on side face
LED_SLOT_DEPTH = 6.0        # into plate
LED_ANGLE = 30.0            # angled upward for visibility from standing position
# 3x LED windows at 120 deg -- we'll place on 3 side faces (front, and two angled corners)
# For square plate: place on +X face, and at =120 deg angular positions mapped to edges
LED_COUNT = 3
# LED positions: center of each side face, or at angular positions
# Simpler: place one LED on each of 3 edges (front +X, left+Y, back-left corner)
# For square: use edge midpoints offset

# === Wire channel ====================================================
WIRE_CHANNEL_W = 3.0
WIRE_CHANNEL_D = 2.0

# === Nest plate ======================================================
NP_W = 80.0
NP_D = 80.0
NP_H = 8.0
NP_CORNER_R = 3.0

# === Variant A: pin location =========================================
VARIAN_A_PIN_DIA = 3.0       # h6 precision locating pins
VARIAN_A_PIN_DEPTH = 6.0     # press fit depth
VARIAN_A_PIN_PROTRUDE = 4.0  # above nest plate top face
VARIAN_A_PIN_SPACING = 25.0  # center-to-center, customer-adjustable
VARIAN_A_PIN_HOLE_DIA = 2.97 # press fit

# === Variant B: ledge location =======================================
VARIAN_B_REF_CIRCLE_R = 15.0 # reference circle for OD location
VARIAN_B_LEDGE_W = 12.0      # ledge width
VARIAN_B_LEDGE_D = 4.0       # ledge depth (radial)
VARIAN_B_LEDGE_H = 3.0       # ledge height above top face
VARIAN_B_SLOT_W = 14.0       # radial slot for adjustment
VARIAN_B_SLOT_D = 3.4        # M3 clearance slot

# === Colors ==========================================================
COLOR_BASE = (0.12, 0.12, 0.14)     # black anodized aluminum
COLOR_NEST = (0.72, 0.72, 0.76)     # natural anodized aluminum
COLOR_PIN = (0.85, 0.85, 0.90)      # ground steel dowel pins
COLOR_BALL = (0.90, 0.90, 0.95)     # polished chrome steel
COLOR_LED_RED = (0.9, 0.1, 0.1)     # LED diffuser accent
COLOR_LOCATING_PIN = (0.80, 0.82, 0.85)  # precision locating pins
COLOR_LEDGE = (0.72, 0.72, 0.76)    # same as nest plate


# =======================================================================
# HELPERS
# =======================================================================

def polar_to_xy(radius, angle_deg):
    """Convert polar (radius, angle deg) to Cartesian (x, y)."""
    rad = math.radians(angle_deg)
    return radius * math.cos(rad), radius * math.sin(rad)


def cradle_angles():
    """3 cradle angular positions at 120 deg spacing."""
    return [CRADLE_ANGLE_START + i * 120.0 for i in range(CRADLE_COUNT)]


def spring_angles():
    """Spring positions offset 60 deg from cradle positions."""
    return [CRADLE_ANGLE_START + 60.0 + i * 120.0 for i in range(SPRING_COUNT)]


def set_color(obj, rgb):
    """Set shape color (no-op in console mode without GUI)."""
    try:
        obj.ViewObject.ShapeColor = rgb
    except Exception:
        pass


def make_rounded_rect(width, depth, height, corner_r):
    """Create a box with rounded vertical corners using fillet.

    Returns a Part.Shape: rounded rectangular prism centered at origin in XY,
    bottom face at Z=0.
    """
    if corner_r <= 0.01:
        box = Part.makeBox(width, depth, height,
                           FreeCAD.Vector(-width / 2, -depth / 2, 0))
        return box

    # Build rounded rectangle as extruded wire with arcs at corners
    hw, hd = width / 2.0, depth / 2.0
    r = min(corner_r, hw - 0.1, hd - 0.1)

    # Corner centers
    pts = [
        (hw - r, hd - r),    # top-right
        (-hw + r, hd - r),   # top-left
        (-hw + r, -hd + r),  # bottom-left
        (hw - r, -hd + r),   # bottom-right
    ]

    edges = []
    for i in range(4):
        cx, cy = pts[i]
        nx, ny = pts[(i + 1) % 4]
        # Arc at corner i
        start_angle = 90.0 * i
        arc = Part.makeCircle(r, FreeCAD.Vector(cx, cy, 0),
                              FreeCAD.Vector(0, 0, 1),
                              start_angle, start_angle + 90.0)
        edges.append(arc)
        # Straight edge from end of this arc to start of next arc
        # Arc end point
        ea = math.radians(start_angle + 90.0)
        ex = cx + r * math.cos(ea)
        ey = cy + r * math.sin(ea)
        # Next arc start point
        sa_next = math.radians(90.0 * ((i + 1) % 4))
        sx = nx + r * math.cos(sa_next)
        sy = ny + r * math.sin(sa_next)

        if abs(ex - sx) > 0.001 or abs(ey - sy) > 0.001:
            line = Part.makeLine(FreeCAD.Vector(ex, ey, 0),
                                 FreeCAD.Vector(sx, sy, 0))
            edges.append(line)

    wire = Part.Wire(edges)
    face = Part.Face(wire)
    solid = face.extrude(FreeCAD.Vector(0, 0, height))
    return solid


def make_led_slot_shape(slot_w, slot_h, slot_depth, angle_deg):
    """Create an angled LED window slot shape.

    Slot is angled upward by angle_deg from horizontal so LED is
    visible to standing operator at 1.5-3m distance.
    Returns shape centered at origin, extending in -X direction (into plate).
    """
    # Rectangular cross-section slot, angled upward
    box = Part.makeBox(slot_depth, slot_w, slot_h,
                       FreeCAD.Vector(-slot_depth, -slot_w / 2, -slot_h / 2))
    # Rotate upward around Y axis by angle_deg
    box.rotate(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(0, 1, 0), -angle_deg)
    return box


# =======================================================================
# BASE PLATE
# =======================================================================

def build_base_plate(doc):
    """Build base plate with all Phase 1 features and Phase 2 prep grooves.

    Coordinate convention:
      - Plate centered at XY origin
      - Bottom face at Z=0, top face at Z=BP_H
      - Kinematic cradle pins protrude from top face upward
      - Hall sensor pocket on top face (sensor faces up toward nest plate)
      - PCB recess on bottom face
      - LED windows on side faces
    """
    # == 1. Base blank -- 80x80x12mm with rounded corners ==
    # Mill rectangular blank from 6061-T6 billet
    base = make_rounded_rect(BP_W, BP_D, BP_H, BP_CORNER_R)

    # == 2. Center bore -- utility passthrough for wires ==
    center_hole = Part.makeCylinder(BP_CENTER_HOLE_DIA / 2.0, BP_H)
    base = base.cut(center_hole)

    # == 3. Four M5 mounting holes -- corner positions, 10mm inset ==
    # Counterbored from bottom face for flush mounting to workbench
    mount_positions = [
        (BP_W / 2 - BP_MOUNT_INSET,  BP_D / 2 - BP_MOUNT_INSET),
        (-BP_W / 2 + BP_MOUNT_INSET, BP_D / 2 - BP_MOUNT_INSET),
        (-BP_W / 2 + BP_MOUNT_INSET, -BP_D / 2 + BP_MOUNT_INSET),
        (BP_W / 2 - BP_MOUNT_INSET,  -BP_D / 2 + BP_MOUNT_INSET),
    ]
    for mx, my in mount_positions:
        # Through-hole
        hole = Part.makeCylinder(BP_MOUNT_DIA / 2.0, BP_H)
        hole.translate(FreeCAD.Vector(mx, my, 0))
        base = base.cut(hole)
        # Counterbore from bottom face (plate sits on bench)
        cbore = Part.makeCylinder(BP_MOUNT_CBORE_DIA / 2.0, BP_MOUNT_CBORE_DEPTH)
        cbore.translate(FreeCAD.Vector(mx, my, 0))
        base = base.cut(cbore)

    # == 4. Electromagnet annular groove -- Phase 2 prep ==
    # Machined in Phase 1 but left unpopulated
    # Groove on top face: ring between EMAG_ID and EMAG_OD, EMAG_DEPTH deep
    # Coil winding sits in this groove when Phase 2 upgrade kit installed
    emag_outer = Part.makeCylinder(EMAG_OD / 2.0, EMAG_DEPTH)
    emag_inner = Part.makeCylinder(EMAG_ID / 2.0, EMAG_DEPTH)
    emag_groove = emag_outer.cut(emag_inner)
    emag_groove.translate(FreeCAD.Vector(0, 0, BP_H - EMAG_DEPTH))
    base = base.cut(emag_groove)

    # == 5. Keeper ring bore -- Phase 2 prep ==
    # Annular recess on top face for steel keeper ring (pressed flush)
    keeper_outer = Part.makeCylinder(KEEPER_OD / 2.0, KEEPER_DEPTH)
    keeper_inner = Part.makeCylinder(KEEPER_ID / 2.0, KEEPER_DEPTH)
    keeper_recess = keeper_outer.cut(keeper_inner)
    keeper_recess.translate(FreeCAD.Vector(0, 0, BP_H - KEEPER_DEPTH))
    base = base.cut(keeper_recess)

    # == 6. Dowel pin holes -- 6 total (2 per cradle x 3 cradles) ==
    # Each cradle: two pins tangentially oriented on 17.5mm radius circle
    # Tangential orientation constrains ball radially and prevents
    # rotation about vertical axis at each contact point
    for angle in cradle_angles():
        cx, cy = polar_to_xy(KC_BOLT_CIRCLE_R, angle)

        # Tangential direction perpendicular to radial
        tang_angle = angle + 90.0
        tx = math.cos(math.radians(tang_angle))
        ty = math.sin(math.radians(tang_angle))

        half_span = PIN_SPACING / 2.0
        for sign in (+1, -1):
            px = cx + sign * half_span * tx
            py = cy + sign * half_span * ty

            # Blind hole from top face -- 3.27mm for H7/h6 press fit
            hole = Part.makeCylinder(PIN_HOLE_DIA / 2.0, PIN_DEPTH)
            hole.translate(FreeCAD.Vector(px, py, BP_H - PIN_DEPTH))
            base = base.cut(hole)

    # == 7. Hall effect sensor pocket -- top face at 60 deg ==
    # SS49E ratiometric sensor detects magnet displacement
    # Threshold 0.01-0.05mm set by LM393 comparator trim pot
    sx, sy = polar_to_xy(SENSOR_RADIUS, SENSOR_ANGLE)
    sensor_pocket = Part.makeCylinder(SENSOR_POCKET_DIA / 2.0, SENSOR_POCKET_DEPTH)
    sensor_pocket.translate(FreeCAD.Vector(sx, sy, BP_H - SENSOR_POCKET_DEPTH))
    base = base.cut(sensor_pocket)

    # M2 threaded holes flanking sensor for retention clip
    tang = SENSOR_ANGLE + 90.0
    for sign in (+1, -1):
        mx = sx + sign * (SENSOR_MOUNT_SPACING / 2.0) * math.cos(math.radians(tang))
        my = sy + sign * (SENSOR_MOUNT_SPACING / 2.0) * math.sin(math.radians(tang))
        m_hole = Part.makeCylinder(SENSOR_MOUNT_DIA / 2.0, SENSOR_MOUNT_DEPTH)
        m_hole.translate(FreeCAD.Vector(mx, my, BP_H - SENSOR_MOUNT_DEPTH))
        base = base.cut(m_hole)

    # Wire routing channel -- 3mm x 2mm radial slot from sensor to plate edge
    radial_x = math.cos(math.radians(SENSOR_ANGLE))
    radial_y = math.sin(math.radians(SENSOR_ANGLE))
    channel_len = (BP_W / 2.0) - SENSOR_RADIUS + 2.0
    channel = Part.makeBox(channel_len, WIRE_CHANNEL_W, WIRE_CHANNEL_D)
    channel.translate(FreeCAD.Vector(0, -WIRE_CHANNEL_W / 2.0, 0))
    # Rotate to radial direction and position
    channel.rotate(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(0, 0, 1), SENSOR_ANGLE)
    mid_r = SENSOR_RADIUS + channel_len / 2.0
    channel.translate(FreeCAD.Vector(mid_r * radial_x, mid_r * radial_y,
                                     BP_H - WIRE_CHANNEL_D))
    base = base.cut(channel)

    # == 8. PCB recess -- bottom face ==
    # 25x35mm signal conditioning board (LM393 comparator, 78L05 reg, LED driver)
    pcb_pocket = Part.makeBox(PCB_W, PCB_D, PCB_H,
                              FreeCAD.Vector(-PCB_W / 2 + PCB_OFFSET_X,
                                             -PCB_D / 2 + PCB_OFFSET_Y,
                                             0))
    base = base.cut(pcb_pocket)

    # == 9. LED window slots -- 3x on plate side faces at 120 deg ==
    # Angled 30 deg upward for visibility from standing operator at 1.5-3m
    # Machined slot with diffuser insert -- professional product appearance
    led_face_angles = [0.0, 120.0, 240.0]
    for la in led_face_angles:
        # Position on plate edge at mid-height
        led_r = BP_W / 2.0  # distance from center to side face
        lx = led_r * math.cos(math.radians(la))
        ly = led_r * math.sin(math.radians(la))

        slot = make_led_slot_shape(LED_SLOT_W, LED_SLOT_H, LED_SLOT_DEPTH, LED_ANGLE)
        # Rotate slot to face outward at this angle
        slot.rotate(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(0, 0, 1), la)
        slot.translate(FreeCAD.Vector(lx, ly, BP_H * 0.6))
        base = base.cut(slot)

    # == 10. Spring retention holes -- M3 threaded, 5mm deep from top face ==
    # Compression springs provide ~3N preload to maintain ball-on-pin contact
    for angle in spring_angles():
        sx, sy = polar_to_xy(SPRING_RADIUS, angle)
        spring_hole = Part.makeCylinder(SPRING_TAP_DIA / 2.0, SPRING_TAP_DEPTH)
        spring_hole.translate(FreeCAD.Vector(sx, sy, BP_H - SPRING_TAP_DEPTH))
        base = base.cut(spring_hole)

    # == Add to document ==
    base_obj = doc.addObject("Part::Feature", "BasePlate")
    base_obj.Shape = base
    set_color(base_obj, COLOR_BASE)
    return base_obj


def build_dowel_pins(doc, z_base=0.0):
    """Build 6 dowel pins protruding from base plate top face.

    3.3mm dia x 10mm long ground steel pins.
    8mm in blind hole, 2mm proud of top face.
    Each pair constrains one ball bearing with two tangent contact lines.
    """
    pins = []
    for ci, angle in enumerate(cradle_angles()):
        cx, cy = polar_to_xy(KC_BOLT_CIRCLE_R, angle)
        tang_angle = angle + 90.0
        tx = math.cos(math.radians(tang_angle))
        ty = math.sin(math.radians(tang_angle))
        half_span = PIN_SPACING / 2.0

        for pi, sign in enumerate((+1, -1)):
            px = cx + sign * half_span * tx
            py = cy + sign * half_span * ty

            # Pin: full length in hole + protrusion
            pin = Part.makeCylinder(PIN_DIA / 2.0, PIN_LENGTH)
            pin_z = z_base + BP_H - PIN_DEPTH
            pin.translate(FreeCAD.Vector(px, py, pin_z))

            name = "DowelPin_C%d_P%d" % (ci + 1, pi + 1)
            pin_obj = doc.addObject("Part::Feature", name)
            pin_obj.Shape = pin
            set_color(pin_obj, COLOR_PIN)
            pins.append(pin_obj)
    return pins


# =======================================================================
# NEST PLATE -- BLANK
# =======================================================================

def build_nest_plate_blank(doc, z_offset=0.0, name_suffix="Blank"):
    """Build blank nest plate with only kinematic and magnet features.

    80x80x8mm plate with:
      - 3x ball pockets on bottom face (mating face)
      - Magnet pocket on bottom face at 60 deg (faces hall sensor)
      - 3x spring through-holes with counterbore
      - Center bore

    This is the gateway product -- customer machines own locating features.
    Bottom face at z_offset, top face at z_offset + NP_H.
    Ball pockets cut from bottom face.
    """
    base = make_rounded_rect(NP_W, NP_D, NP_H, NP_CORNER_R)
    base.translate(FreeCAD.Vector(0, 0, z_offset))

    # Center bore
    center_hole = Part.makeCylinder(BP_CENTER_HOLE_DIA / 2.0, NP_H)
    center_hole.translate(FreeCAD.Vector(0, 0, z_offset))
    base = base.cut(center_hole)

    # Ball pockets -- 3x on bottom face matching cradle angular positions
    # 4.97mm dia x 3.5mm deep press-fit pockets for 5mm chrome steel balls
    for angle in cradle_angles():
        bx, by = polar_to_xy(KC_BOLT_CIRCLE_R, angle)
        pocket = Part.makeCylinder(BALL_POCKET_DIA / 2.0, BALL_POCKET_DEPTH)
        pocket.translate(FreeCAD.Vector(bx, by, z_offset))
        base = base.cut(pocket)

    # Magnet pocket -- bottom face at 60 deg to match hall sensor on base plate
    # 6mm x 3mm N52 neodymium disc magnet for crash/presence detection
    mx, my = polar_to_xy(SENSOR_RADIUS, SENSOR_ANGLE)
    mag_pocket = Part.makeCylinder(MAGNET_POCKET_DIA / 2.0, MAGNET_POCKET_DEPTH)
    mag_pocket.translate(FreeCAD.Vector(mx, my, z_offset))
    base = base.cut(mag_pocket)

    # Spring through-holes with counterbore on top face
    # M3 through for spring screw, counterbore for spring seat
    for angle in spring_angles():
        sx, sy = polar_to_xy(SPRING_RADIUS, angle)

        thru = Part.makeCylinder(SPRING_HOLE_DIA / 2.0, NP_H)
        thru.translate(FreeCAD.Vector(sx, sy, z_offset))
        base = base.cut(thru)

        cbore = Part.makeCylinder(SPRING_CBORE_DIA / 2.0, SPRING_CBORE_DEPTH)
        cbore.translate(FreeCAD.Vector(sx, sy, z_offset + NP_H - SPRING_CBORE_DEPTH))
        base = base.cut(cbore)

    obj_name = "NestPlate_%s" % name_suffix
    nest_obj = doc.addObject("Part::Feature", obj_name)
    nest_obj.Shape = base
    set_color(nest_obj, COLOR_NEST)
    return nest_obj


def build_balls(doc, z_offset=0.0):
    """Build 3 precision ball bearings seated in nest plate pockets.

    5mm dia chrome steel balls. Pocket on bottom face of nest plate.
    Ball protrudes 1.5mm below nest plate bottom face for pin contact.

    Ball center Z = z_offset + BALL_POCKET_DEPTH - BALL_DIA/2
                  = z_offset + 3.5 - 2.5 = z_offset + 1.0
    Ball bottom  = z_offset + 1.0 - 2.5 = z_offset - 1.5 (protrudes 1.5mm)
    """
    balls = []
    for ci, angle in enumerate(cradle_angles()):
        bx, by = polar_to_xy(KC_BOLT_CIRCLE_R, angle)
        ball_cz = z_offset + BALL_POCKET_DEPTH - BALL_DIA / 2.0

        ball = Part.makeSphere(BALL_DIA / 2.0)
        ball.translate(FreeCAD.Vector(bx, by, ball_cz))

        name = "Ball_%d" % (ci + 1)
        ball_obj = doc.addObject("Part::Feature", name)
        ball_obj.Shape = ball
        set_color(ball_obj, COLOR_BALL)
        balls.append(ball_obj)
    return balls


# =======================================================================
# NEST PLATE -- VARIANT A (PIN LOCATION)
# =======================================================================

def build_nest_plate_variant_a(doc, z_offset=0.0):
    """Variant A: Two precision locating pins for hole-located parts.

    3mm dia h6 ground pins on customer-specified centerline.
    Pins replaceable -- press fit, customer swaps for different hole patterns.
    Default: 25mm spacing along X axis, centered on plate.
    """
    nest = build_nest_plate_blank(doc, z_offset, name_suffix="VariantA")

    # Read back the shape to add pin holes
    shape = nest.Shape

    # Pin press-fit holes on top face
    for sign in (+1, -1):
        px = sign * VARIAN_A_PIN_SPACING / 2.0
        hole = Part.makeCylinder(VARIAN_A_PIN_HOLE_DIA / 2.0, VARIAN_A_PIN_DEPTH)
        hole.translate(FreeCAD.Vector(px, 0, z_offset + NP_H - VARIAN_A_PIN_DEPTH))
        shape = shape.cut(hole)

    nest.Shape = shape
    return nest


def build_locating_pins_a(doc, z_offset=0.0):
    """Build the two precision locating pins for Variant A."""
    pin_objs = []
    for pi, sign in enumerate((+1, -1)):
        px = sign * VARIAN_A_PIN_SPACING / 2.0
        total_len = VARIAN_A_PIN_DEPTH + VARIAN_A_PIN_PROTRUDE
        pin = Part.makeCylinder(VARIAN_A_PIN_DIA / 2.0, total_len)
        pin.translate(FreeCAD.Vector(px, 0,
                                     z_offset + NP_H - VARIAN_A_PIN_DEPTH))

        name = "LocatingPin_%d" % (pi + 1)
        pin_obj = doc.addObject("Part::Feature", name)
        pin_obj.Shape = pin
        set_color(pin_obj, COLOR_LOCATING_PIN)
        pin_objs.append(pin_obj)
    return pin_objs


# =======================================================================
# NEST PLATE -- VARIANT B (LEDGE LOCATION)
# =======================================================================

def build_nest_plate_variant_b(doc, z_offset=0.0):
    """Variant B: Three machined ledges at 120 deg for OD-located parts.

    Ledges tangent to reference circle. Part OD seats against ledges.
    Adjustable: M3 screws in radial slots (not modeled -- shown as
    fixed ledges at nominal position).
    """
    nest = build_nest_plate_blank(doc, z_offset, name_suffix="VariantB")
    shape = nest.Shape

    # Add three ledge bosses on top face at 120 deg spacing
    # Each ledge is a rectangular block tangent to the reference circle
    ledge_objs = []
    for i in range(3):
        angle = i * 120.0 + 60.0  # offset from cradle positions

        # Ledge center at reference circle radius along radial direction
        lx, ly = polar_to_xy(VARIAN_B_REF_CIRCLE_R, angle)

        # Tangential direction for ledge width
        tang = angle + 90.0

        # Build ledge block
        ledge = Part.makeBox(VARIAN_B_LEDGE_D, VARIAN_B_LEDGE_W, VARIAN_B_LEDGE_H,
                             FreeCAD.Vector(-VARIAN_B_LEDGE_D / 2,
                                            -VARIAN_B_LEDGE_W / 2, 0))
        # Rotate to align radially outward
        ledge.rotate(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(0, 0, 1), angle)
        ledge.translate(FreeCAD.Vector(lx, ly, z_offset + NP_H))

        name = "Ledge_%d" % (i + 1)
        ledge_obj = doc.addObject("Part::Feature", name)
        ledge_obj.Shape = ledge
        set_color(ledge_obj, COLOR_LEDGE)
        ledge_objs.append(ledge_obj)

    # Also add radial adjustment slots to the nest plate (M3 clearance slots)
    for i in range(3):
        angle = i * 120.0 + 60.0
        lx, ly = polar_to_xy(VARIAN_B_REF_CIRCLE_R, angle)
        radial_x = math.cos(math.radians(angle))
        radial_y = math.sin(math.radians(angle))

        # Radial slot: elongated hole for M3 adjustment screw
        slot = Part.makeBox(VARIAN_B_SLOT_W, VARIAN_B_SLOT_D, NP_H,
                            FreeCAD.Vector(-VARIAN_B_SLOT_W / 2,
                                           -VARIAN_B_SLOT_D / 2, 0))
        slot.rotate(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(0, 0, 1), angle)
        slot.translate(FreeCAD.Vector(lx, ly, z_offset))
        shape = shape.cut(slot)

    nest.Shape = shape
    return nest, ledge_objs


# =======================================================================
# LED DIFFUSER INSERTS (visual accent)
# =======================================================================

def build_led_diffusers(doc, z_base=0.0):
    """Build small LED diffuser cylinders in the LED window slots.

    Visual accent showing LED position. Not functional geometry --
    represents the diffuser insert in the machined slot.
    """
    led_objs = []
    led_face_angles = [0.0, 120.0, 240.0]
    for i, la in enumerate(led_face_angles):
        led_r = BP_W / 2.0 - LED_SLOT_DEPTH / 2.0
        lx = led_r * math.cos(math.radians(la))
        ly = led_r * math.sin(math.radians(la))

        # Small cylinder representing 5mm LED with diffuser
        led = Part.makeCylinder(2.5, 4.0)
        led.rotate(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(0, 1, 0), 90)
        led.rotate(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(0, 0, 1), la)
        led.translate(FreeCAD.Vector(lx, ly, z_base + BP_H * 0.6))

        name = "LED_Diffuser_%d" % (i + 1)
        led_obj = doc.addObject("Part::Feature", name)
        led_obj.Shape = led
        set_color(led_obj, COLOR_LED_RED)
        led_objs.append(led_obj)
    return led_objs


# =======================================================================
# ASSEMBLIES
# =======================================================================

def build_coupled_assembly(variant="blank"):
    """Build coupled state: nest plate seated on base plate.

    Base plate: bottom Z=0, top Z=12
    Pins protrude to Z = 12 + 2 = 14
    Nest plate bottom face contacts pins/balls
    Gap between plate faces = PIN_PROTRUDE = 2mm (ball protrudes 1.5mm,
    pins protrude 2mm -- ball seats between pins below pin tips)
    Nest plate bottom at Z = BP_H + PIN_PROTRUDE - BALL_PROTRUDE
                           = 12 + 2 - 1.5 = 12.5
    (ball protrusion fills most of gap, slight clearance)
    Simplification: nest bottom at Z = BP_H (faces almost touching,
    hardware interleaves in the gap zone)
    """
    suffix = variant.capitalize()
    doc = FreeCAD.newDocument("KIN_Coupled_%s" % suffix)

    base = build_base_plate(doc)
    pins = build_dowel_pins(doc)
    leds = build_led_diffusers(doc)

    # Nest plate bottom face at Z = BP_H + gap
    # Gap ~ PIN_PROTRUDE (pins set the standoff height)
    np_z = BP_H + PIN_PROTRUDE
    # But ball protrudes 1.5mm, and sits between pins that protrude 2mm
    # Ball contact is at approximately pin tip height
    # For visual clarity, use np_z = BP_H + 1.5 (slight gap visible)
    np_z = BP_H + 1.5

    if variant == "variant_a":
        nest = build_nest_plate_variant_a(doc, z_offset=np_z)
        loc_pins = build_locating_pins_a(doc, z_offset=np_z)
    elif variant == "variant_b":
        nest, ledges = build_nest_plate_variant_b(doc, z_offset=np_z)
    else:
        nest = build_nest_plate_blank(doc, z_offset=np_z)

    balls = build_balls(doc, z_offset=np_z)

    doc.recompute()
    return doc


def build_exploded_assembly(variant="blank"):
    """Build exploded view: nest plate offset 40mm above base plate.

    Both plates visible showing all features.
    """
    suffix = variant.capitalize()
    doc = FreeCAD.newDocument("KIN_Exploded_%s" % suffix)

    base = build_base_plate(doc)
    pins = build_dowel_pins(doc)
    leds = build_led_diffusers(doc)

    np_z = BP_H + 40.0  # 40mm separation for clear exploded view

    if variant == "variant_a":
        nest = build_nest_plate_variant_a(doc, z_offset=np_z)
        loc_pins = build_locating_pins_a(doc, z_offset=np_z)
    elif variant == "variant_b":
        nest, ledges = build_nest_plate_variant_b(doc, z_offset=np_z)
    else:
        nest = build_nest_plate_blank(doc, z_offset=np_z)

    balls = build_balls(doc, z_offset=np_z)

    doc.recompute()
    return doc


# =======================================================================
# STL EXPORT
# =======================================================================

def export_stl(doc, obj_name, filename):
    """Export a single document object to STL."""
    for obj in doc.Objects:
        if obj.Name == obj_name:
            mesh_obj = doc.addObject("Mesh::Feature", obj_name + "_Mesh")
            mesh_obj.Mesh = Mesh.Mesh(obj.Shape.tessellate(0.05))
            filepath = os.path.join(OUTPUT_DIR, filename)
            Mesh.export([mesh_obj], filepath)
            doc.removeObject(mesh_obj.Name)
            print("  Exported: %s" % filename)
            return True
    return False


def export_all_stls(doc, variant="blank"):
    """Export base plate and nest plate STLs from assembly."""
    export_stl(doc, "BasePlate", "base_plate.stl")

    nest_name = "NestPlate_%s" % variant.replace("variant_", "Variant").capitalize()
    if variant == "variant_a":
        nest_name = "NestPlate_VariantA"
    elif variant == "variant_b":
        nest_name = "NestPlate_VariantB"
    else:
        nest_name = "NestPlate_Blank"

    export_stl(doc, nest_name, "nest_plate_%s.stl" % variant)


# =======================================================================
# MAIN
# =======================================================================

def main():
    print("=" * 60)
    print("Kinematic Indicator Nest -- FreeCAD CAD Generation")
    print("=" * 60)
    print("Output directory:", OUTPUT_DIR)
    print()

    # == Coupled assembly with blank nest (primary) ==
    print("[1/6] Building coupled assembly (blank nest)...")
    coupled = build_coupled_assembly("blank")
    path = os.path.join(OUTPUT_DIR, "assembly_coupled_blank.FCStd")
    coupled.saveAs(path)
    print("  Saved:", path)

    # == Export STLs from coupled assembly ==
    print("[2/6] Exporting STLs...")
    export_all_stls(coupled, "blank")

    # == Exploded view (blank) ==
    print("[3/6] Building exploded view (blank)...")
    exploded = build_exploded_assembly("blank")
    path = os.path.join(OUTPUT_DIR, "assembly_exploded_blank.FCStd")
    exploded.saveAs(path)
    print("  Saved:", path)

    # == Variant A coupled ==
    print("[4/6] Building Variant A (pin location)...")
    var_a = build_coupled_assembly("variant_a")
    path = os.path.join(OUTPUT_DIR, "assembly_coupled_variant_a.FCStd")
    var_a.saveAs(path)
    print("  Saved:", path)
    export_stl(var_a, "NestPlate_VariantA", "nest_plate_variant_a.stl")

    # == Variant B coupled ==
    print("[5/6] Building Variant B (ledge location)...")
    var_b = build_coupled_assembly("variant_b")
    path = os.path.join(OUTPUT_DIR, "assembly_coupled_variant_b.FCStd")
    var_b.saveAs(path)
    print("  Saved:", path)
    export_stl(var_b, "NestPlate_VariantB", "nest_plate_variant_b.stl")

    # == Summary ==
    print()
    print("[6/6] Done!")
    print()
    print("Output files:")
    print("  assembly_coupled_blank.FCStd      -- Phase 1 blank nest, coupled")
    print("  assembly_exploded_blank.FCStd      -- Phase 1 blank nest, exploded")
    print("  assembly_coupled_variant_a.FCStd   -- Variant A pin location")
    print("  assembly_coupled_variant_b.FCStd   -- Variant B ledge location")
    print("  base_plate.stl                     -- Base plate mesh")
    print("  nest_plate_blank.stl               -- Blank nest plate mesh")
    print("  nest_plate_variant_a.stl           -- Variant A nest plate mesh")
    print("  nest_plate_variant_b.stl           -- Variant B nest plate mesh")
    print()
    print("Phase 2 electromagnet groove and keeper ring bore are")
    print("machined but unpopulated -- upgrade in field, no new base plate.")


if __name__ == "__main__":
    main()
