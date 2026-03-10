"""
Generate KiCad 8 project files for the Kinematic Indicator Nest
signal conditioning PCB (25mm x 35mm).

Circuit: 24VDC -> 78L05 -> SS49E hall sensor -> LM393 comparator
         -> 2N7000 MOSFET LED drivers (amber steady / red 2Hz flash)

Run: python generate_kicad.py
Opens in: KiCad 8.0
"""

import os
import math
import json

OUT = os.path.dirname(os.path.abspath(__file__))
PROJECT_NAME = "kin_nest_pcb"


# ======================================================================
# CIRCUIT DESIGN NOTES
# ======================================================================
#
# Power: 24VDC in -> D1 reverse protection -> U1 78L05 -> 5V rail
#   C1 100nF input bypass, C2 100nF + C3 10uF output
#
# Sensor: U2 SS49E ratiometric hall effect (5V, GND, VOUT ~2.5V quiescent)
#   C4 100nF bypass on VCC
#
# Threshold: RV1 10k multi-turn trim pot (5V-GND, wiper = Vref)
#   Sets deflection threshold 0.01-1.0mm
#
# Comparator: U3 LM393 dual
#   U3A (threshold): IN+=RV1 wiper, IN-=SS49E VOUT
#     Seated (magnet close, VOUT high > Vref): OUT sinks -> LOW
#     Deflected (VOUT drops < Vref): OUT floats -> HIGH via R1 pullup
#
#   U3B (2Hz oscillator): astable multivibrator
#     R4 bias 100k to 5V, R5 bias 100k to GND -> Vcenter=2.5V
#     R6 1M positive feedback from OUT to IN+ (hysteresis)
#     C5 2.2uF timing cap on IN-
#     R7 680k timing resistor from OUT to IN-
#     R8 10k output pullup
#     ~2Hz square wave output
#
# Amber LED (seated indicator):
#   5V -> R2 150R -> D2 amber LED -> U3A OUT (open collector)
#   Seated: U3A sinks -> LED ON
#   Deflected: U3A floats HIGH -> no current -> LED OFF
#
# Red LED (deflection alarm, 2Hz flash):
#   Q1 2N7000: gate=U3A OUT via R9 1k, source=GND
#   U3B OUT -> R3 150R -> D3 red LED -> Q1 drain
#   Deflected: U3A HIGH -> Q1 ON -> red LED flashes with oscillator
#   Seated: U3A LOW -> Q1 OFF -> red LED dark
#
# Connectors:
#   J1: 2-pin 24VDC power input
#   J2: 3-pin sensor (VCC, OUT, GND) to SS49E on base plate
#   J3: 4-pin LED (GND, RED, AMB, 5V) to LED diffusers on base plate
#


# ======================================================================
# BOM
# ======================================================================

BOM = [
    # Ref, Value, Footprint, Description
    ("U1",  "78L05",     "SOT-89",        "5V 100mA LDO regulator"),
    ("U2",  "SS49E",     "TO-92",         "Ratiometric linear hall effect sensor"),
    ("U3",  "LM393",     "SOIC-8",        "Dual comparator, open collector output"),
    ("Q1",  "2N7000",    "TO-92",         "N-channel MOSFET, red LED driver"),
    ("D1",  "1N4148",    "SOD-123",       "Reverse polarity protection diode"),
    ("D2",  "LED_Amber", "LED_THT_5mm",   "Amber LED 1000mcd, seated indicator"),
    ("D3",  "LED_Red",   "LED_THT_5mm",   "Red LED 1000mcd, deflection alarm"),
    ("RV1", "10k",       "Trimmer_3296W", "10-turn trimmer, threshold adjust"),
    ("R1",  "10k",       "0603",          "LM393 U3A output pullup"),
    ("R2",  "150R",      "0603",          "Amber LED current limit (20mA)"),
    ("R3",  "150R",      "0603",          "Red LED current limit (20mA)"),
    ("R4",  "100k",      "0603",          "U3B IN+ bias to 5V"),
    ("R5",  "100k",      "0603",          "U3B IN+ bias to GND"),
    ("R6",  "1M",        "0603",          "U3B hysteresis feedback"),
    ("R7",  "680k",      "0603",          "U3B timing resistor"),
    ("R8",  "10k",       "0603",          "U3B output pullup"),
    ("R9",  "1k",        "0603",          "Q1 gate series resistor"),
    ("C1",  "100nF",     "0603",          "78L05 input bypass"),
    ("C2",  "100nF",     "0603",          "78L05 output bypass"),
    ("C3",  "10uF",      "0805",          "5V bulk decoupling"),
    ("C4",  "100nF",     "0603",          "SS49E VCC bypass"),
    ("C5",  "2.2uF",     "0603",          "U3B timing capacitor"),
    ("J1",  "Conn_01x02","PinHeader_1x02_P2.54mm", "24VDC power input"),
    ("J2",  "Conn_01x03","PinHeader_1x03_P2.54mm", "Hall sensor (VCC,OUT,GND)"),
    ("J3",  "Conn_01x04","PinHeader_1x04_P2.54mm", "LED output (GND,RED,AMB,5V)"),
]


# ======================================================================
# KiCad project file (.kicad_pro)
# ======================================================================

def write_project():
    pro = {
        "meta": {"filename": PROJECT_NAME + ".kicad_pro", "version": 1},
        "schematic": {"drawing": {"default_line_thickness": 6}},
        "boards": [],
        "text_variables": {}
    }
    path = os.path.join(OUT, PROJECT_NAME + ".kicad_pro")
    with open(path, "w") as f:
        json.dump(pro, f, indent=2)
    print("  Written:", path)


# ======================================================================
# KiCad schematic (.kicad_sch)
# ======================================================================

def uid():
    """Generate a simple unique ID for KiCad elements."""
    uid.counter += 1
    return "%08x-0000-0000-0000-%012x" % (uid.counter, uid.counter)
uid.counter = 0


def sch_symbol(ref, value, lib_id, x, y, angle=0, mirror=False,
               pins_override=None, properties_extra=None):
    """Generate a KiCad schematic symbol instance."""
    # For schematic-level symbols, we use a simplified approach
    # that KiCad 8 can import
    u = uid()

    # Build transform
    if angle == 90:
        mat = "(0 -1 1 0)"
    elif angle == 180:
        mat = "(-1 0 0 -1)"
    elif angle == 270:
        mat = "(0 1 -1 0)"
    else:
        mat = "(1 0 0 1)"

    mirror_str = ' (mirror y)' if mirror else ''

    props = []
    props.append(f'    (property "Reference" "{ref}" (at 0 -1.5 0) (effects (font (size 1.27 1.27))))')
    props.append(f'    (property "Value" "{value}" (at 0 1.5 0) (effects (font (size 1.27 1.27))))')

    if properties_extra:
        for k, v in properties_extra.items():
            props.append(f'    (property "{k}" "{v}" (at 0 3 0) (effects (font (size 1.27 1.27)) hide))')

    props_str = "\n".join(props)

    return f"""  (symbol
    (lib_id "{lib_id}")
    (at {x} {y} {angle})
    (uuid "{u}")
    {props_str}
    (instances
      (project "{PROJECT_NAME}"
        (path "/"
          (reference "{ref}")
          (unit 1)
        )
      )
    )
  )"""


def sch_wire(x1, y1, x2, y2):
    u = uid()
    return f'  (wire (pts (xy {x1} {y1}) (xy {x2} {y2})) (uuid "{u}"))'


def sch_label(name, x, y, angle=0):
    u = uid()
    return f'  (label "{name}" (at {x} {y} {angle}) (uuid "{u}") (effects (font (size 1.27 1.27))))'


def sch_net_label(name, x, y, angle=0):
    u = uid()
    return f'  (net_label "{name}" (at {x} {y} {angle}) (uuid "{u}") (effects (font (size 1.27 1.27))))'


def sch_gnd(x, y):
    u = uid()
    return f'  (power_port "GND" (at {x} {y} 0) (uuid "{u}"))'


def sch_vcc(x, y):
    u = uid()
    return f'  (power_port "+5V" (at {x} {y} 0) (uuid "{u}"))'


def write_schematic():
    """Write a KiCad 8 schematic as a text-based netlist/notes file.

    KiCad 8 schematic format is complex with embedded symbol definitions.
    Instead, we write a clean netlist + schematic PDF-equivalent as a
    structured text file that documents the complete circuit, and a
    minimal .kicad_sch that KiCad can open.
    """
    path = os.path.join(OUT, PROJECT_NAME + ".kicad_sch")

    # Write a minimal valid KiCad 8 schematic
    # This won't have graphical symbol placements but will define the project
    content = f"""(kicad_sch
  (version 20231120)
  (generator "kinematic_nest_gen")
  (generator_version "1.0")
  (uuid "00000001-0000-0000-0000-000000000001")
  (paper "A4")

  (title_block
    (title "Kinematic Indicator Nest - Signal Conditioning")
    (date "2026-03-10")
    (rev "1.0")
    (comment 1 "24VDC -> 78L05 -> SS49E -> LM393 -> LED drivers")
    (comment 2 "Phase 1: Passive indicator (hall + comparator + LED)")
    (comment 3 "PCB: 25mm x 35mm, mounts in base plate recess")
  )

  (text "CIRCUIT NOTES:\\n\\n"
    "Power: 24VDC -> D1 (1N4148) -> U1 (78L05) -> 5V\\n"
    "Sensor: U2 (SS49E) VOUT to U3A IN-\\n"
    "Threshold: RV1 (10k trim) wiper to U3A IN+\\n"
    "Comparator: U3 (LM393) dual\\n"
    "  U3A: threshold detect (seated/deflected)\\n"
    "  U3B: 2Hz astable oscillator\\n"
    "Amber LED: 5V->R2->D2->U3A OUT (ON when seated)\\n"
    "Red LED: U3B OUT->R3->D3->Q1 drain (flash when deflected)\\n"
    "Q1 gate: U3A OUT via R9 (ON when deflected)"
    (at 20 40)
    (effects (font (size 2 2)))
  )
)
"""
    with open(path, "w") as f:
        f.write(content)
    print("  Written:", path)


# ======================================================================
# NETLIST (machine-readable circuit connectivity)
# ======================================================================

def write_netlist():
    """Write complete netlist as structured text for PCB layout."""
    path = os.path.join(OUT, "netlist.txt")

    nets = {
        "24V_IN":  ["J1.1", "D1.A"],
        "24V":     ["D1.K", "U1.IN", "C1.1"],
        "+5V":     ["U1.OUT", "C2.1", "C3.1", "C4.1",
                    "U2.VCC", "U3.VCC",
                    "R1.1", "R2.1", "R4.1", "R8.1",
                    "RV1.H", "J2.1", "J3.4"],
        "GND":     ["J1.2", "C1.2", "C2.2", "C3.2", "C4.2",
                    "U1.GND", "U2.GND", "U3.GND",
                    "R5.2", "Q1.S",
                    "C5.2", "RV1.L", "J2.3", "J3.1"],
        "HALL_OUT":["U2.OUT", "U3A.IN-", "J2.2"],
        "VREF":    ["RV1.W", "U3A.IN+"],
        "COMP_A":  ["U3A.OUT", "R1.2", "R2.2_via_LED", "R9.1"],
        "AMB_LED_A":["R2.2", "D2.A"],
        "AMB_LED_K":["D2.K", "U3A.OUT"],  # LED sinks into open collector
        "Q1_GATE": ["R9.2", "Q1.G"],
        "RED_LED_DRIVE":["U3B.OUT", "R8.2", "R3.1"],
        "RED_LED_A":["R3.2", "D3.A"],
        "RED_LED_K":["D3.K", "Q1.D"],
        "OSC_INP": ["R4.2", "R5.1", "R6.1", "U3B.IN+"],
        "OSC_INM": ["R7.2", "C5.1", "U3B.IN-"],
        "OSC_FB":  ["R6.2", "R7.1", "U3B.OUT"],  # feedback from OUT
    }

    with open(path, "w") as f:
        f.write("# Kinematic Indicator Nest - Signal Conditioning PCB\n")
        f.write("# Netlist v1.0 - 2026-03-10\n")
        f.write("# Board: 25mm x 35mm, 2-layer, 1oz Cu\n\n")

        f.write("=" * 60 + "\n")
        f.write("BILL OF MATERIALS\n")
        f.write("=" * 60 + "\n")
        f.write(f"{'Ref':<6} {'Value':<12} {'Package':<20} {'Description'}\n")
        f.write("-" * 70 + "\n")
        for ref, val, fp, desc in BOM:
            f.write(f"{ref:<6} {val:<12} {fp:<20} {desc}\n")
        f.write(f"\nTotal components: {len(BOM)}\n\n")

        f.write("=" * 60 + "\n")
        f.write("NETLIST\n")
        f.write("=" * 60 + "\n")
        for net_name, pins in nets.items():
            f.write(f"\nNet: {net_name}\n")
            for pin in pins:
                f.write(f"  {pin}\n")

        f.write("\n\n")
        f.write("=" * 60 + "\n")
        f.write("CIRCUIT DESCRIPTION\n")
        f.write("=" * 60 + "\n")
        f.write("""
POWER SUPPLY:
  24VDC (J1) -> D1 (1N4148, reverse protection) -> U1 (78L05)
  C1 100nF on input, C2 100nF + C3 10uF on 5V output
  Max current: ~60mA (sensor 10mA + LEDs 40mA + logic 10mA)

HALL EFFECT SENSOR:
  U2 (SS49E) ratiometric output: ~2.5V quiescent, +/-0.6V/mT
  C4 100nF bypass on VCC pin
  Sensor mounted on base plate, connected via J2 (3-pin header)
  Wire run ~50mm from PCB pocket to sensor pocket

THRESHOLD COMPARATOR (U3A):
  Non-inverting input (IN+): RV1 wiper (adjustable 0-5V reference)
  Inverting input (IN-): SS49E analog output
  Open collector output with R1 10k pullup to 5V

  Seated state: magnet close to sensor, VOUT > VREF
    -> IN- > IN+ -> U3A output transistor ON -> OUT = LOW (~0.2V)
    -> Current flows: 5V -> R2 -> amber LED -> U3A OUT -> GND
    -> Amber LED ON (steady)

  Deflected state: magnet moves away, VOUT drops < VREF
    -> IN- < IN+ -> U3A output transistor OFF -> OUT = HIGH (5V via R1)
    -> No current through amber LED (both sides at 5V)
    -> Amber LED OFF
    -> Q1 gate HIGH -> Q1 ON -> red LED circuit enabled

2Hz OSCILLATOR (U3B):
  Relaxation oscillator using positive feedback (hysteresis)
  R4 100k + R5 100k: bias IN+ to 2.5V center
  R6 1M: positive feedback from OUT to IN+ (hysteresis ~0.45V)
  R7 680k + C5 2.2uF: RC timing on IN-
  R8 10k: output pullup

  Thresholds: ~2.27V / ~2.73V (from hysteresis)
  Frequency: ~2Hz (adjustable by C5 value)

  Output square wave drives red LED through R3 when Q1 is ON

RED LED FLASH DRIVER:
  Q1 (2N7000) gate driven by U3A output via R9 (1k gate resistor)
  Deflected -> Q1 ON -> red LED cathode to GND
  U3B oscillator output -> R3 150R -> red LED anode
  Red LED flashes at ~2Hz when nest is deflected

  Seated -> Q1 OFF -> red LED dark regardless of oscillator

LED CONNECTIONS:
  D2 (amber) and D3 (red) are 5mm THT LEDs
  Mounted remotely on base plate edge via J3 (4-pin header)
  J3 pinout: 1=GND, 2=RED_K, 3=AMB_K, 4=+5V
  Note: LED anodes connected to signal lines on PCB,
  cathodes returned via J3 to PCB open collectors/MOSFETs

TRIM POT CALIBRATION:
  RV1 (Bourns 3296W, 10-turn) sets detection threshold
  CW rotation: higher threshold -> less sensitive
  CCW rotation: lower threshold -> more sensitive (0.01mm)
  Factory set: ~50% (2.5V) then fine-tune with test magnet/gap
  10-turn resolution: ~0.5mV per turn -> ~0.001mm per turn
""")
    print("  Written:", path)


# ======================================================================
# PCB layout (.kicad_pcb)
# ======================================================================

def write_pcb():
    """Write KiCad 8 PCB file with component placement and board outline.

    Board: 25mm x 35mm, 2-layer, fits in base plate recess (30x40x5mm).
    Origin at board center.
    """
    path = os.path.join(OUT, PROJECT_NAME + ".kicad_pcb")

    BW = 25.0   # board width (mm)
    BH = 35.0   # board height (mm)
    CR = 1.5    # corner radius

    # Board outline points (rounded rectangle approximation with arcs)
    hw, hh = BW / 2.0, BH / 2.0

    # Component placement (x, y relative to board center, angle)
    # Organized for short signal paths and thermal management
    placements = {
        # Power section - top of board
        "J1":  (-8.0, -14.0, 0),    # 24V input header, board edge
        "D1":  (-4.0, -14.0, 0),    # protection diode near input
        "U1":  (0.0,  -12.0, 0),    # 78L05 regulator
        "C1":  (-3.0, -10.5, 0),    # input bypass near U1
        "C2":  (3.0,  -10.5, 0),    # output bypass near U1
        "C3":  (6.0,  -10.5, 0),    # bulk cap

        # Sensor connection - right side
        "J2":  (9.5,  -4.0, 0),     # sensor header, board edge

        # Comparator - center of board
        "U3":  (0.0,  -2.0, 0),     # LM393 SOIC-8, center
        "R1":  (-5.0, -4.0, 0),     # U3A pullup
        "C4":  (5.0,  -4.0, 0),     # sensor bypass

        # Threshold adjust - left side, accessible
        "RV1": (-8.0, -2.0, 0),     # trim pot, accessible from edge

        # Oscillator components - center-right
        "R4":  (6.0,  0.0, 0),      # bias resistors clustered
        "R5":  (6.0,  2.0, 0),
        "R6":  (3.0,  2.0, 0),      # hysteresis feedback
        "R7":  (3.0,  4.0, 0),      # timing resistor
        "C5":  (6.0,  4.0, 0),      # timing cap
        "R8":  (-3.0, 2.0, 0),      # osc pullup

        # LED driver - bottom of board
        "Q1":  (-3.0, 8.0, 0),      # MOSFET
        "R9":  (-6.0, 6.0, 0),      # gate resistor
        "R2":  (-6.0, 10.0, 0),     # amber current limit
        "R3":  (0.0,  10.0, 0),     # red current limit
        "D2":  (-6.0, 13.0, 0),     # amber LED (or via J3)
        "D3":  (0.0,  13.0, 0),     # red LED (or via J3)

        # LED/output connector - bottom edge
        "J3":  (6.0,  14.0, 0),     # LED output header, board edge
    }

    # KiCad 8 PCB format
    content = f"""(kicad_pcb
  (version 20240108)
  (generator "kinematic_nest_gen")
  (generator_version "1.0")

  (general
    (thickness 1.6)
    (legacy_teardrops no)
  )

  (paper "A4")

  (title_block
    (title "KIN Nest Signal Conditioning")
    (date "2026-03-10")
    (rev "1.0")
    (comment 1 "25mm x 35mm, 2-layer, 1oz Cu")
    (comment 2 "Fits in base plate PCB recess")
  )

  (layers
    (0 "F.Cu" signal)
    (31 "B.Cu" signal)
    (32 "B.Adhes" user "B.Adhesive")
    (33 "F.Adhes" user "F.Adhesive")
    (34 "B.Paste" user)
    (35 "F.Paste" user)
    (36 "B.SilkS" user "B.Silkscreen")
    (37 "F.SilkS" user "F.Silkscreen")
    (38 "B.Mask" user "B.Mask")
    (39 "F.Mask" user "F.Mask")
    (40 "Dwgs.User" user "User.Drawings")
    (41 "Cmts.User" user "User.Comments")
    (44 "Edge.Cuts" user)
  )

  (setup
    (pad_to_mask_clearance 0.05)
    (allow_soldermask_bridges_in_footprints no)
    (pcbplotparams
      (layerselection 0x00010fc_ffffffff)
      (plot_on_all_layers_selection 0x0000000_00000000)
    )
  )

  ;; Board outline - 25mm x 35mm rounded rectangle
  (gr_rect
    (start {-hw} {-hh})
    (end {hw} {hh})
    (stroke (width 0.15) (type solid))
    (fill none)
    (layer "Edge.Cuts")
  )

  ;; Board dimensions annotation
  (gr_text "25mm"
    (at 0 {-hh - 2})
    (layer "Cmts.User")
    (effects (font (size 1.5 1.5) (thickness 0.15)))
  )
  (gr_text "35mm"
    (at {hw + 3} 0 90)
    (layer "Cmts.User")
    (effects (font (size 1.5 1.5) (thickness 0.15)))
  )

  ;; Mounting holes - 2x M2, diagonal corners
  (footprint "MountingHole:MountingHole_2.2mm_M2_Pad"
    (at {-hw + 2.5} {-hh + 2.5})
    (layer "F.Cu")
    (property "Reference" "MH1")
    (pad "1" thru_hole circle (at 0 0) (size 4.4 4.4) (drill 2.2)
      (layers "*.Cu" "*.Mask"))
  )
  (footprint "MountingHole:MountingHole_2.2mm_M2_Pad"
    (at {hw - 2.5} {hh - 2.5})
    (layer "F.Cu")
    (property "Reference" "MH2")
    (pad "1" thru_hole circle (at 0 0) (size 4.4 4.4) (drill 2.2)
      (layers "*.Cu" "*.Mask"))
  )

  ;; Ground pour zone - back copper
  (zone
    (net 0)
    (net_name "GND")
    (layer "B.Cu")
    (filled_polygon
      (pts
        (xy {-hw + 0.5} {-hh + 0.5})
        (xy {hw - 0.5} {-hh + 0.5})
        (xy {hw - 0.5} {hh - 0.5})
        (xy {-hw + 0.5} {hh - 0.5})
      )
    )
  )

"""

    # Add placement markers as silkscreen text for each component
    for ref, (x, y, angle) in placements.items():
        # Find the component value
        val = ""
        for bref, bval, bfp, bdesc in BOM:
            if bref == ref:
                val = bval
                break

        content += f"""  ;; {ref} ({val})
  (gr_text "{ref}"
    (at {x} {y} {angle})
    (layer "F.SilkS")
    (effects (font (size 1 1) (thickness 0.15)))
  )
  (gr_circle
    (center {x} {y})
    (end {x + 1.5} {y})
    (stroke (width 0.1) (type solid))
    (fill none)
    (layer "Cmts.User")
  )
"""

    # Add copper text labels for key nets
    net_labels = [
        (0, -15, "+24V", "F.SilkS"),
        (0, -8, "+5V", "F.SilkS"),
        (-8, 5, "VREF", "F.SilkS"),
        (0, 6, "COMP_A", "F.SilkS"),
    ]
    for nx, ny, nname, nlayer in net_labels:
        content += f"""  (gr_text "{nname}"
    (at {nx} {ny})
    (layer "{nlayer}")
    (effects (font (size 0.8 0.8) (thickness 0.12)))
  )
"""

    content += ")\n"

    with open(path, "w") as f:
        f.write(content)
    print("  Written:", path)


# ======================================================================
# Schematic diagram as SVG (human-readable circuit drawing)
# ======================================================================

def write_schematic_svg():
    """Generate an SVG schematic diagram of the circuit.

    This is the primary human-readable schematic since KiCad 8
    S-expression schematics require embedded symbol libraries.
    """
    path = os.path.join(OUT, "schematic.svg")

    W, H = 800, 600
    # Scale: 1 unit = ~1mm on schematic

    svg_parts = []
    svg_parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
                     f'width="{W}" height="{H}" '
                     f'style="background:#fff;font-family:monospace">')

    # Title block
    svg_parts.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="white" stroke="black" stroke-width="2"/>')
    svg_parts.append(f'<text x="{W//2}" y="25" text-anchor="middle" font-size="16" font-weight="bold">'
                     f'Kinematic Indicator Nest - Signal Conditioning PCB</text>')
    svg_parts.append(f'<text x="{W//2}" y="42" text-anchor="middle" font-size="11" fill="#666">'
                     f'Rev 1.0 | 25x35mm | 24VDC input | Phase 1 passive indicator</text>')

    def line(x1, y1, x2, y2, color="black", width=1.5):
        return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}"/>'

    def rect(x, y, w, h, fill="none", stroke="black", sw=1.5):
        return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" rx="2"/>'

    def text(x, y, t, size=10, anchor="middle", color="black", bold=False):
        fw = ' font-weight="bold"' if bold else ''
        return f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-size="{size}" fill="{color}"{fw}>{t}</text>'

    def circle(cx, cy, r, fill="none", stroke="black", sw=1.5):
        return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'

    def pin_dot(x, y):
        return circle(x, y, 2.5, fill="black", stroke="black", sw=0)

    # ── POWER SECTION (top-left) ──
    bx, by = 40, 90
    svg_parts.append(text(bx + 80, by - 20, "POWER SUPPLY", 12, bold=True))

    # J1 connector
    svg_parts.append(rect(bx, by, 30, 40, fill="#f0f0f0"))
    svg_parts.append(text(bx + 15, by + 15, "J1", 9, bold=True))
    svg_parts.append(text(bx + 15, by + 28, "24VDC", 8))
    svg_parts.append(line(bx + 30, by + 10, bx + 50, by + 10))  # +24V out
    svg_parts.append(text(bx + 35, by + 7, "+", 8, "start"))
    svg_parts.append(line(bx + 30, by + 30, bx + 50, by + 30))  # GND out
    svg_parts.append(text(bx + 35, by + 27, "-", 8, "start"))

    # D1 protection diode
    svg_parts.append(line(bx + 50, by + 10, bx + 60, by + 10))
    # Diode symbol
    svg_parts.append(f'<polygon points="{bx+60},{by+5} {bx+60},{by+15} {bx+72},{by+10}" fill="none" stroke="black" stroke-width="1.5"/>')
    svg_parts.append(line(bx + 72, by + 5, bx + 72, by + 15))
    svg_parts.append(text(bx + 66, by + 3, "D1", 8))
    svg_parts.append(text(bx + 66, by + 22, "1N4148", 7, color="#666"))
    svg_parts.append(line(bx + 72, by + 10, bx + 90, by + 10))

    # C1 input cap
    svg_parts.append(line(bx + 85, by + 10, bx + 85, by + 17))
    svg_parts.append(line(bx + 80, by + 17, bx + 90, by + 17))
    svg_parts.append(line(bx + 80, by + 20, bx + 90, by + 20))
    svg_parts.append(line(bx + 85, by + 20, bx + 85, by + 30))
    svg_parts.append(text(bx + 95, by + 19, "C1", 7, "start"))
    svg_parts.append(text(bx + 95, by + 27, "100nF", 7, "start", "#666"))

    # U1 78L05 box
    svg_parts.append(rect(bx + 100, by + 2, 50, 36, fill="#e8f4e8"))
    svg_parts.append(text(bx + 125, by + 18, "U1", 9, bold=True))
    svg_parts.append(text(bx + 125, by + 30, "78L05", 8, color="#666"))
    svg_parts.append(text(bx + 98, by + 14, "IN", 7, "end"))
    svg_parts.append(text(bx + 152, by + 14, "OUT", 7, "start"))
    svg_parts.append(text(bx + 125, by + 42, "GND", 7))
    svg_parts.append(line(bx + 90, by + 10, bx + 100, by + 10))  # IN
    svg_parts.append(line(bx + 150, by + 10, bx + 200, by + 10))  # OUT -> 5V
    svg_parts.append(line(bx + 125, by + 38, bx + 125, by + 50))  # GND down
    svg_parts.append(pin_dot(bx + 85, by + 10))

    # 5V label
    svg_parts.append(text(bx + 200, by + 7, "+5V", 10, "start", "red", True))
    svg_parts.append(line(bx + 200, by + 10, bx + 220, by + 10, "red", 2))

    # C2 output cap
    svg_parts.append(line(bx + 165, by + 10, bx + 165, by + 17))
    svg_parts.append(line(bx + 160, by + 17, bx + 170, by + 17))
    svg_parts.append(line(bx + 160, by + 20, bx + 170, by + 20))
    svg_parts.append(line(bx + 165, by + 20, bx + 165, by + 30))
    svg_parts.append(text(bx + 175, by + 19, "C2 100nF", 7, "start", "#666"))
    svg_parts.append(pin_dot(bx + 165, by + 10))

    # C3 bulk cap
    svg_parts.append(line(bx + 185, by + 10, bx + 185, by + 17))
    svg_parts.append(line(bx + 180, by + 17, bx + 190, by + 17))
    svg_parts.append(line(bx + 180, by + 20, bx + 190, by + 20))
    svg_parts.append(line(bx + 185, by + 20, bx + 185, by + 30))
    svg_parts.append(text(bx + 195, by + 19, "C3 10uF", 7, "start", "#666"))
    svg_parts.append(pin_dot(bx + 185, by + 10))

    # GND bus
    svg_parts.append(line(bx + 50, by + 30, bx + 185, by + 30))
    svg_parts.append(text(bx + 120, by + 45, "GND", 9, color="#444"))
    # GND symbol
    for gx in [bx + 85, bx + 125, bx + 165, bx + 185]:
        svg_parts.append(line(gx - 4, by + 30, gx + 4, by + 30))

    # ── SENSOR SECTION (top-right) ──
    sx, sy = 420, 90
    svg_parts.append(text(sx + 60, sy - 20, "HALL EFFECT SENSOR", 12, bold=True))

    # U2 SS49E
    svg_parts.append(rect(sx, sy, 50, 50, fill="#e8e8f4"))
    svg_parts.append(text(sx + 25, sy + 20, "U2", 9, bold=True))
    svg_parts.append(text(sx + 25, sy + 35, "SS49E", 8, color="#666"))
    svg_parts.append(text(sx - 2, sy + 14, "VCC", 7, "end"))
    svg_parts.append(text(sx - 2, sy + 44, "GND", 7, "end"))
    svg_parts.append(text(sx + 52, sy + 30, "OUT", 7, "start"))

    # Connections
    svg_parts.append(line(sx - 20, sy + 10, sx, sy + 10))  # VCC from 5V
    svg_parts.append(text(sx - 22, sy + 7, "+5V", 9, "end", "red"))
    svg_parts.append(line(sx - 20, sy + 40, sx, sy + 40))  # GND
    svg_parts.append(line(sx + 50, sy + 26, sx + 90, sy + 26))  # VOUT
    svg_parts.append(text(sx + 92, sy + 23, "HALL_OUT", 8, "start", "blue"))

    # C4 bypass
    svg_parts.append(line(sx - 10, sy + 10, sx - 10, sy + 17))
    svg_parts.append(line(sx - 15, sy + 17, sx - 5, sy + 17))
    svg_parts.append(line(sx - 15, sy + 20, sx - 5, sy + 20))
    svg_parts.append(line(sx - 10, sy + 20, sx - 10, sy + 40))
    svg_parts.append(text(sx - 22, sy + 22, "C4", 7, "end"))
    svg_parts.append(text(sx - 22, sy + 30, "100nF", 7, "end", "#666"))
    svg_parts.append(pin_dot(sx - 10, sy + 10))
    svg_parts.append(pin_dot(sx - 10, sy + 40))

    # J2 sensor connector
    svg_parts.append(rect(sx + 90, sy - 5, 35, 60, fill="#f0f0f0"))
    svg_parts.append(text(sx + 107, sy + 10, "J2", 9, bold=True))
    svg_parts.append(text(sx + 107, sy + 22, "SENSOR", 7))
    svg_parts.append(text(sx + 107, sy + 33, "3-pin", 7, color="#666"))
    svg_parts.append(text(sx + 107, sy + 45, "header", 7, color="#666"))

    # ── COMPARATOR SECTION (middle) ──
    cx, cy = 80, 220
    svg_parts.append(text(cx + 120, cy - 25, "THRESHOLD COMPARATOR", 12, bold=True))

    # RV1 trim pot
    svg_parts.append(rect(cx, cy, 40, 50, fill="#fff8e0"))
    svg_parts.append(text(cx + 20, cy + 20, "RV1", 9, bold=True))
    svg_parts.append(text(cx + 20, cy + 35, "10k", 8, color="#666"))
    svg_parts.append(text(cx + 20, cy + 45, "10-turn", 7, color="#999"))
    svg_parts.append(line(cx + 20, cy - 5, cx + 20, cy))  # H to +5V
    svg_parts.append(text(cx + 22, cy - 8, "+5V", 8, "start", "red"))
    svg_parts.append(line(cx + 20, cy + 50, cx + 20, cy + 60))  # L to GND
    svg_parts.append(text(cx + 22, cy + 62, "GND", 8, "start"))
    svg_parts.append(line(cx + 40, cy + 25, cx + 70, cy + 25))  # W to comp
    svg_parts.append(text(cx + 55, cy + 22, "VREF", 8, color="blue"))
    svg_parts.append(pin_dot(cx + 40, cy + 25))

    # U3A comparator triangle
    u3x, u3y = cx + 100, cy + 10
    # Triangle pointing right
    svg_parts.append(f'<polygon points="{u3x},{u3y} {u3x},{u3y+50} {u3x+50},{u3y+25}" '
                     f'fill="#f4e8e8" stroke="black" stroke-width="1.5"/>')
    svg_parts.append(text(u3x + 20, u3y + 22, "U3A", 9, bold=True))
    svg_parts.append(text(u3x + 20, u3y + 35, "LM393", 7, color="#666"))
    svg_parts.append(text(u3x + 5, u3y + 17, "+", 10, "start"))
    svg_parts.append(text(u3x + 5, u3y + 40, "-", 10, "start"))

    # IN+ from trim pot
    svg_parts.append(line(cx + 70, cy + 25, u3x, u3y + 12))

    # IN- from hall sensor
    svg_parts.append(line(u3x - 30, u3y + 38, u3x, u3y + 38))
    svg_parts.append(text(u3x - 32, u3y + 35, "HALL_OUT", 8, "end", "blue"))

    # Output
    svg_parts.append(line(u3x + 50, u3y + 25, u3x + 80, u3y + 25))
    svg_parts.append(text(u3x + 82, u3y + 22, "COMP_A", 8, "start", "#c00", True))

    # R1 pullup
    svg_parts.append(line(u3x + 65, u3y + 25, u3x + 65, u3y + 10))
    svg_parts.append(rect(u3x + 62, u3y + 2, 6, 8, fill="#f0f0f0", sw=1))
    svg_parts.append(line(u3x + 65, u3y + 2, u3x + 65, u3y - 5))
    svg_parts.append(text(u3x + 73, u3y + 8, "R1 10k", 7, "start", "#666"))
    svg_parts.append(text(u3x + 67, u3y - 8, "+5V", 8, "start", "red"))
    svg_parts.append(pin_dot(u3x + 65, u3y + 25))

    # ── OSCILLATOR SECTION (middle-right) ──
    ox, oy = 420, 210
    svg_parts.append(text(ox + 60, oy - 25, "2Hz OSCILLATOR", 12, bold=True))

    # U3B comparator triangle
    svg_parts.append(f'<polygon points="{ox},{oy} {ox},{oy+50} {ox+50},{oy+25}" '
                     f'fill="#f4e8e8" stroke="black" stroke-width="1.5"/>')
    svg_parts.append(text(ox + 20, oy + 22, "U3B", 9, bold=True))
    svg_parts.append(text(ox + 5, oy + 17, "+", 10, "start"))
    svg_parts.append(text(ox + 5, oy + 40, "-", 10, "start"))

    # Bias resistors to IN+
    svg_parts.append(line(ox - 40, oy + 12, ox, oy + 12))
    svg_parts.append(text(ox - 50, oy + 5, "R4 100k", 7, "start", "#666"))
    svg_parts.append(text(ox - 50, oy - 2, "to +5V", 7, "start", "red"))
    svg_parts.append(text(ox - 50, oy + 20, "R5 100k", 7, "start", "#666"))
    svg_parts.append(text(ox - 50, oy + 27, "to GND", 7, "start"))

    # Feedback R6 from OUT to IN+
    svg_parts.append(line(ox + 50, oy + 25, ox + 70, oy + 25))
    svg_parts.append(line(ox + 70, oy + 25, ox + 70, oy - 10))
    svg_parts.append(line(ox + 70, oy - 10, ox - 10, oy - 10))
    svg_parts.append(line(ox - 10, oy - 10, ox - 10, oy + 12))
    svg_parts.append(text(ox + 30, oy - 13, "R6 1M (feedback)", 7, color="#666"))
    svg_parts.append(pin_dot(ox - 10, oy + 12))

    # Timing RC on IN-
    svg_parts.append(line(ox - 30, oy + 38, ox, oy + 38))
    svg_parts.append(text(ox - 32, oy + 35, "R7 680k", 7, "end", "#666"))
    svg_parts.append(text(ox - 32, oy + 45, "C5 2.2uF", 7, "end", "#666"))

    # Output with pullup
    svg_parts.append(text(ox + 72, oy + 22, "OSC_OUT", 8, "start", "#c00"))
    svg_parts.append(text(ox + 55, oy + 15, "R8 10k", 7, "start", "#666"))

    # ── LED DRIVER SECTION (bottom) ──
    lx, ly = 80, 380
    svg_parts.append(text(lx + 180, ly - 25, "LED DRIVERS", 12, bold=True))

    # Amber LED (steady when seated)
    svg_parts.append(text(lx, ly, "AMBER LED (seated indicator):", 10, "start", bold=True))
    svg_parts.append(text(lx, ly + 18, "+5V --> R2 (150R) --> D2 (amber) --> U3A OUT (open collector)", 9, "start"))
    svg_parts.append(text(lx, ly + 32, "Seated: U3A sinks current --> LED ON (steady)", 9, "start", "#080"))
    svg_parts.append(text(lx, ly + 44, "Deflected: U3A floats HIGH --> no current --> LED OFF", 9, "start", "#800"))

    # Red LED (flash when deflected)
    svg_parts.append(text(lx, ly + 70, "RED LED (deflection alarm, 2Hz flash):", 10, "start", bold=True))
    svg_parts.append(text(lx, ly + 88, "OSC_OUT --> R3 (150R) --> D3 (red) --> Q1 drain", 9, "start"))
    svg_parts.append(text(lx, ly + 100, "Q1 (2N7000) gate = COMP_A via R9 (1k), source = GND", 9, "start"))
    svg_parts.append(text(lx, ly + 114, "Deflected: COMP_A HIGH --> Q1 ON --> LED flashes at 2Hz", 9, "start", "#800"))
    svg_parts.append(text(lx, ly + 126, "Seated: COMP_A LOW --> Q1 OFF --> LED dark", 9, "start", "#080"))

    # J3 connector pinout
    svg_parts.append(text(lx + 450, ly + 10, "J3 PINOUT:", 10, "start", bold=True))
    svg_parts.append(text(lx + 450, ly + 28, "1: GND", 9, "start"))
    svg_parts.append(text(lx + 450, ly + 40, "2: RED_LED_K", 9, "start"))
    svg_parts.append(text(lx + 450, ly + 52, "3: AMB_LED_K", 9, "start"))
    svg_parts.append(text(lx + 450, ly + 64, "4: +5V", 9, "start"))

    # ── COMPONENT COUNT ──
    svg_parts.append(text(W - 20, H - 40, f"Total components: {len(BOM)}", 10, "end", "#666"))
    svg_parts.append(text(W - 20, H - 25, "Board: 25mm x 35mm, 2-layer, 1oz Cu", 10, "end", "#666"))
    svg_parts.append(text(W - 20, H - 10, "Kinematic Indicator Nest - Rev 1.0", 10, "end", "#999"))

    svg_parts.append('</svg>')

    with open(path, "w") as f:
        f.write("\n".join(svg_parts))
    print("  Written:", path)


# ======================================================================
# BOM as CSV
# ======================================================================

def write_bom_csv():
    path = os.path.join(OUT, "bom.csv")
    with open(path, "w") as f:
        f.write("Reference,Value,Package,Description,Qty\n")
        for ref, val, fp, desc in BOM:
            f.write(f"{ref},{val},{fp},{desc},1\n")
    print("  Written:", path)


# ======================================================================
# MAIN
# ======================================================================

def main():
    print("Generating KiCad project files...")
    print("Output:", OUT)
    print()

    write_project()
    write_schematic()
    write_pcb()
    write_schematic_svg()
    write_netlist()
    write_bom_csv()

    print()
    print("Files generated:")
    print(f"  {PROJECT_NAME}.kicad_pro   -- KiCad project (open in KiCad 8)")
    print(f"  {PROJECT_NAME}.kicad_sch   -- Schematic (minimal, see SVG)")
    print(f"  {PROJECT_NAME}.kicad_pcb   -- PCB layout with placements")
    print(f"  schematic.svg              -- Circuit diagram (open in browser)")
    print(f"  netlist.txt                -- Complete netlist + circuit notes")
    print(f"  bom.csv                    -- Bill of materials")
    print()
    print("Next steps:")
    print("  1. Open schematic.svg to review circuit")
    print("  2. Open .kicad_pcb in KiCad for PCB layout")
    print("  3. Import footprints and route traces")


if __name__ == "__main__":
    main()
