"""Lathe Mode for a sketch - the pure half. Stdlib only, no adsk.

Shane, 8/25/26: "what if when user is in a sketch a center line can be
drawn... user can right click the center line and there will be a G-SEND
button for 'Lathe Mode'. Any line parallel to the center line will be
divided by two." The point: a lathe print reads in DIAMETERS, and
Fusion's sketch dims read in radii unless every single dimension is
right-clicked into a diameter dimension by hand.

The mode is an attribute on the sketch naming its centerline. While it
is on, the add-in converts qualifying dimensions - a linear dimension
between the centerline and a parallel line or a point - into Fusion's
native linear DIAMETER dimension. Two directions of conversion exist and
they are different on purpose:

  activation  dims that existed before the mode was turned on were
              honestly entered as radii, so the GEOMETRY is right -
              convert the display, leave the part alone.
  watcher     a dim placed while the mode is on was TYPED as a diameter
              (that is what the mode is for) - keep the typed number as
              the diameter, so the geometry halves.

Only in the DESIGN workspace (Shane, same day: "make sure the button
doesn't come up if Fusion is in Manufacture").
"""

import math

#: Attribute group and name marking a sketch's Lathe Mode. The value is
#: the centerline's entityToken.
ATTR_GROUP = "GSendIO"
ATTR_CENTERLINE = "lathe_mode_centerline"

#: Fusion workspace ids. The right-click button and the watcher both gate
#: on Design; Manufacture never sees either.
DESIGN_WORKSPACE_ID = "FusionSolidEnvironment"

MENU_ON = "G-SEND.IO: Lathe Mode (Diameter Mode)"
MENU_OFF = "G-SEND.IO: Lathe Mode off"

#: The one-click diameter dimension, offered when right-clicking a line
#: parallel to the marked centerline (Shane, 8/25/26: pasted lines need
#: a way into diameter mode without the two-entity dimension dance).
MENU_DIA = "G-SEND.IO: ⌀ Dimension to Centerline"


def menu_label(active):
    """What the right-click row reads: the action it will take."""
    return MENU_OFF if active else MENU_ON


def watcher_value(initial_value):
    """The parameter value that makes a fresh diameter dimension show the
    TYPED number as the diameter.

    Deliberately semantic-independent: whether the API parameter stores
    the diameter or the centerline distance, it scales linearly with the
    geometry, and the fresh dimension was created on geometry sitting at
    the typed number as a DISTANCE. Halving the parameter halves the
    distance, which lands the diameter exactly on the typed number - in
    either semantic, without ever knowing which one Fusion uses.
    """
    return float(initial_value) / 2.0


def distance_to_axis(point, axis_start, axis_direction):
    """Perpendicular distance from ``point`` to the infinite line through
    ``axis_start`` along ``axis_direction`` (3-tuples, sketch units).

    The axis is the spindle centerline, so this is the RADIUS of a point.
    A zero-length direction has no axis to measure against and raises -
    the caller already refuses zero-length centerlines via parallel().
    """
    px, py, pz = (float(v) for v in point)
    ax, ay, az = (float(v) for v in axis_start)
    dx, dy, dz = (float(v) for v in axis_direction)
    mag = math.sqrt(dx * dx + dy * dy + dz * dz)
    if mag <= 0.0:
        raise ValueError("zero-length axis direction")
    vx, vy, vz = px - ax, py - ay, pz - az
    cx = vy * dz - vz * dy
    cy = vz * dx - vx * dz
    cz = vx * dy - vy * dx
    return math.sqrt(cx * cx + cy * cy + cz * cz) / mag


#: A sketch point this close to the axis (sketch units, cm) IS on the
#: axis, and a dimension value this close to a radius IS that radius.
#: Solved sketch geometry is exact to well below this.
AXIS_TOLERANCE = 1e-5


def dia_text_point(line_mid, axis_start, axis_direction):
    """Where a one-click diameter dimension's text lands: halfway
    between the line's midpoint and its projection onto the axis, so
    the label sits inside the gap it measures. The user can drag it
    afterwards; this only has to be sensible, not perfect.
    """
    mx, my, mz = (float(v) for v in line_mid)
    ax, ay, az = (float(v) for v in axis_start)
    dx, dy, dz = (float(v) for v in axis_direction)
    mag2 = dx * dx + dy * dy + dz * dz
    if mag2 <= 0.0:
        raise ValueError("zero-length axis direction")
    t = ((mx - ax) * dx + (my - ay) * dy + (mz - az) * dz) / mag2
    px, py, pz = ax + t * dx, ay + t * dy, az + t * dz
    return ((mx + px) / 2.0, (my + py) / 2.0, (mz + pz) / 2.0)


def measures_the_radius(value, radius, tolerance=AXIS_TOLERANCE):
    """Whether a dimension's value is the perpendicular distance of its
    far entity from the axis - i.e. the dim measures the RADIUS.

    The guard that keeps a diagonal or a length dimension out: a
    point-to-point dimension from an on-axis corner to an off-axis
    corner can measure any direction, and only the one measuring the
    radius may become a diameter dimension.
    """
    return abs(float(value) - float(radius)) <= tolerance


def parallel(direction_a, direction_b, tolerance=1e-7):
    """Two 3-vectors parallel (either sense) within ``tolerance``.

    Scale-invariant: the cross product's magnitude over the product of
    the magnitudes, so a long centerline and a short wall compare the
    same as two unit vectors. Zero-length input is never parallel to
    anything - it has no direction to agree with.
    """
    ax, ay, az = (float(v) for v in direction_a)
    bx, by, bz = (float(v) for v in direction_b)
    mag_a = math.sqrt(ax * ax + ay * ay + az * az)
    mag_b = math.sqrt(bx * bx + by * by + bz * bz)
    if mag_a <= 0.0 or mag_b <= 0.0:
        return False
    cx = ay * bz - az * by
    cy = az * bx - ax * bz
    cz = ax * by - ay * bx
    return math.sqrt(cx * cx + cy * cy + cz * cz) / (mag_a * mag_b) <= tolerance
