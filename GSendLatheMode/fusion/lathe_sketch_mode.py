"""Lathe Mode: right-click a sketch centerline, dims become diameters.

The adsk half of lib/lathe_sketch.py. Right-clicking a sketch line in
the DESIGN workspace offers "G-SEND.IO: Lathe Mode"; toggling it on
marks the sketch with the line's entityToken, converts every existing
qualifying dimension into Fusion's native linear diameter dimension
WITHOUT moving geometry, and from then on a watcher converts each newly
placed centerline dimension so the number the user typed is the
DIAMETER (the geometry halves - "any line parallel to the center line
will be divided by two", Shane, 8/25/26).

API surface verified live against Fusion's own API documentation,
8/25/26: SketchDimensions.addLinearDiameterDimension ("the first line
acts as the center line... the second entity can be a point or a line
that is parallel to the first"), UserInterface.markingMenuDisplaying,
UserInterface.commandTerminated.

Ordering rule inside a conversion: the old dimension is DELETED before
the diameter dimension is added - both alive at once double-constrains
the same distance and the add fails. If the add then fails anyway, a
plain distance dimension is restored best-effort so toggling the mode
can never eat a user's dimension.
"""

import os
import traceback

import adsk.core
import adsk.fusion

from ..lib import lathe_sketch

CMD_ID = "gsendio_lathe_mode"
DIA_CMD_ID = "gsendio_lathe_dia_dim"

# G00 logo (16/32/64 png) so the Lathe Mode row stands out from native
# Fusion entries in the marking menu - same folder and reasoning as
# material_menu. Absolute path: relative resource paths are not
# reliable from a subpackage.
RESOURCE_FOLDER = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "resources", "gsendio")

_handlers = []
_menu_handler = None
_terminated_handler = None
_context_line = None       # the SketchLine under the cursor at right-click
_converting = False        # re-entrancy guard: conversions fire commands too


def _log(message):
    try:
        adsk.core.Application.get().log("GSendIO lathe mode: %s" % message)
    except Exception:
        pass


def _in_design_workspace(ui):
    """Only Design offers the mode (Shane: never in Manufacture). A
    sketch can be edited from inside Manufacture too - the gate is the
    workspace, not the edit object."""
    try:
        workspace = ui.activeWorkspace
        return bool(workspace) and workspace.id == lathe_sketch.DESIGN_WORKSPACE_ID
    except Exception:
        return False


def _active_sketch():
    try:
        edit = adsk.core.Application.get().activeEditObject
        return adsk.fusion.Sketch.cast(edit)
    except Exception:
        return None


def _centerline_of(sketch):
    """The sketch's marked centerline, or None when the mode is off (or
    the marked line no longer exists - deleting the centerline turns the
    mode off by absence)."""
    try:
        attribute = sketch.attributes.itemByName(
            lathe_sketch.ATTR_GROUP, lathe_sketch.ATTR_CENTERLINE)
        if not attribute or not attribute.value:
            return None
        design = sketch.parentComponent.parentDesign
        for entity in design.findEntityByToken(attribute.value) or []:
            line = adsk.fusion.SketchLine.cast(entity)
            if line:
                return line
    except Exception:
        _log("centerline lookup failed\n" + traceback.format_exc())
    return None


def _direction(line):
    start = line.startSketchPoint.geometry
    end = line.endSketchPoint.geometry
    return (end.x - start.x, end.y - start.y, end.z - start.z)


def _is_line(entity):
    return entity is not None and \
        entity.objectType == adsk.fusion.SketchLine.classType()


def _is_point(entity):
    return entity is not None and \
        entity.objectType == adsk.fusion.SketchPoint.classType()


def _point(sketch_point):
    geometry = sketch_point.geometry
    return (geometry.x, geometry.y, geometry.z)


def _axis_distance(entity, centerline):
    """Perpendicular distance of a point (or a line's start point) from
    the centerline's infinite axis - the entity's RADIUS."""
    if _is_point(entity):
        geometry = entity.geometry
    elif _is_line(entity):
        geometry = entity.startSketchPoint.geometry
    else:
        return None
    return lathe_sketch.distance_to_axis(
        (geometry.x, geometry.y, geometry.z),
        _point(centerline.startSketchPoint), _direction(centerline))


def _on_axis(entity, centerline_token, centerline):
    """Whether ``entity`` stands for the spindle axis: the centerline
    itself, a point ON the axis, or a line collinear with it. Measured
    live 8/25/26: Shane's first real dimension referenced the axis only
    through a POINT sitting on it - the centerline's own entityToken
    appeared in no dimension at all."""
    if getattr(entity, "entityToken", "") == centerline_token:
        return True
    try:
        if _is_point(entity):
            return _axis_distance(entity, centerline) <= lathe_sketch.AXIS_TOLERANCE
        if _is_line(entity):
            return lathe_sketch.parallel(
                _direction(centerline), _direction(entity)) and \
                _axis_distance(entity, centerline) <= lathe_sketch.AXIS_TOLERANCE
    except Exception:
        return False
    return False


def _far_side_ok(entity, centerline):
    """The far entity must be something a diameter dimension can hold:
    a line parallel to the axis, or a point off the axis."""
    if _is_line(entity):
        return lathe_sketch.parallel(_direction(centerline), _direction(entity))
    return _is_point(entity)


def _qualifies(dimension, centerline_token, centerline):
    """The far entity when ``dimension`` measures a RADIUS - a distance
    between the axis (the centerline, a collinear line, or a point on
    the axis) and a parallel line or off-axis point; None otherwise.
    Diameter dims never qualify - they are the OUTPUT.

    Both plain dimension types qualify. Fusion creates a
    SketchOffsetDimension for line-to-line and line-to-point picks -
    which is what dimensioning a wall against the centerline actually
    produces (measured live 8/25/26) - and a SketchLinearDimension for
    point-to-point picks. A point-to-point dimension can measure any
    direction, so it must additionally prove its value IS the far
    point's radius (lathe_sketch.measures_the_radius) - a diagonal or a
    length along the axis must never become a diameter."""
    kind = dimension.objectType
    if kind == adsk.fusion.SketchOffsetDimension.classType():
        try:
            one, two = dimension.line, dimension.entityTwo
        except Exception:
            return None
        needs_radius_proof = False
    elif kind == adsk.fusion.SketchLinearDimension.classType():
        try:
            one, two = dimension.entityOne, dimension.entityTwo
        except Exception:
            return None
        needs_radius_proof = True
    else:
        return None
    if _on_axis(one, centerline_token, centerline):
        other = two
    elif _on_axis(two, centerline_token, centerline):
        other = one
    else:
        return None
    if _on_axis(other, centerline_token, centerline):
        return None                      # both sides on the axis: a length
    if not _far_side_ok(other, centerline):
        return None
    if needs_radius_proof:
        try:
            radius = _axis_distance(other, centerline)
            if radius is None or not lathe_sketch.measures_the_radius(
                    dimension.parameter.value, radius):
                return None
        except Exception:
            return None
    return other


def _restore_distance(sketch, centerline, other, text_point, value):
    """Best effort: put a plain distance dimension back after a failed
    conversion, so the user's dimension is never simply gone."""
    try:
        anchor = other if other.objectType == adsk.fusion.SketchPoint.classType() \
            else other.startSketchPoint
        dim = sketch.sketchDimensions.addDistanceDimension(
            centerline.startSketchPoint, anchor,
            adsk.fusion.DimensionOrientations.AlignedDimensionOrientation,
            text_point)
        if dim is not None:
            dim.parameter.value = value
    except Exception:
        _log("restore after failed conversion also failed\n"
             + traceback.format_exc())


def convert_all(sketch, centerline, preserve_geometry):
    """Convert every qualifying dimension; returns how many.

    ``preserve_geometry`` is the activation pass: existing dims were
    entered as radii, so the diameter dim keeps whatever value it is
    born with on the unchanged geometry. The watcher pass halves the
    fresh dimension's parameter instead (lathe_sketch.watcher_value), so
    the number the user just typed becomes the DIAMETER.
    """
    global _converting
    if _converting:
        return 0
    _converting = True
    count = 0
    try:
        token = centerline.entityToken
        for dimension in list(sketch.sketchDimensions):
            try:
                other = _qualifies(dimension, token, centerline)
                if other is None:
                    continue
                # The property really is textPosition. The first ship
                # asked the dimension for the add METHOD'S parameter
                # name instead ("textPoint" - a property no dimension
                # type has), so every conversion raised and was
                # swallowed; nothing ever converted.
                text_point = dimension.textPosition
                old_value = dimension.parameter.value
                driving = bool(getattr(dimension, "isDriving", True))
                dimension.deleteMe()
                new = None
                try:
                    new = sketch.sketchDimensions.addLinearDiameterDimension(
                        centerline, other, text_point, driving)
                except TypeError:
                    # No isDriving parameter in this Fusion build: the
                    # 3-arg form creates a DRIVING dim, so it may only
                    # stand in for one.
                    if driving:
                        try:
                            new = sketch.sketchDimensions\
                                .addLinearDiameterDimension(
                                    centerline, other, text_point)
                        except Exception:
                            new = None
                except Exception:
                    new = None
                if new is None:
                    _restore_distance(sketch, centerline, other,
                                      text_point, old_value)
                    continue
                if not preserve_geometry and driving:
                    try:
                        new.parameter.value = lathe_sketch.watcher_value(
                            new.parameter.value)
                    except Exception:
                        _log("could not halve the fresh dimension; left as-is")
                count += 1
            except Exception:
                _log("one dimension conversion failed\n"
                     + traceback.format_exc())
    finally:
        _converting = False
    return count


class _MarkingMenuHandler(adsk.core.MarkingMenuEventHandler):
    def notify(self, args):
        global _context_line
        try:
            _context_line = None
            ui = adsk.core.Application.get().userInterface
            if not _in_design_workspace(ui):
                return
            sketch = _active_sketch()
            if sketch is None:
                return
            event_args = adsk.core.MarkingMenuEventArgs.cast(args)
            line = None
            for entity in event_args.selectedEntities or []:
                line = adsk.fusion.SketchLine.cast(entity)
                if line:
                    break
            if not line:
                return
            _context_line = line
            marked = _centerline_of(sketch)
            active = bool(marked) and marked.entityToken == line.entityToken
            cmd_def = ui.commandDefinitions.itemById(CMD_ID)
            if not cmd_def:
                return
            try:
                cmd_def.name = lathe_sketch.menu_label(active)
            except Exception:
                pass
            menu = event_args.linearMarkingMenu
            if menu and not menu.controls.itemById(CMD_ID):
                menu.controls.addCommand(cmd_def)
            # The one-click diameter dimension: only on a line PARALLEL
            # to the marked centerline and off the axis - the shape a
            # pasted wall has (Shane, 8/25/26: pasted lines need a way
            # into diameter mode without the two-entity pick).
            if marked and not active and \
                    _far_side_ok(line, marked) and \
                    not _on_axis(line, marked.entityToken, marked):
                dia_def = ui.commandDefinitions.itemById(DIA_CMD_ID)
                if dia_def and menu and not menu.controls.itemById(DIA_CMD_ID):
                    menu.controls.addCommand(dia_def)
        except Exception:
            _log("marking menu failed\n" + traceback.format_exc())


class _CommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            on_execute = _ExecuteHandler()
            args.command.execute.add(on_execute)
            _handlers.append(on_execute)
        except Exception:
            _log("command created failed\n" + traceback.format_exc())


class _ExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        try:
            ui = adsk.core.Application.get().userInterface
            sketch = _active_sketch()
            line = _context_line
            if sketch is None or line is None:
                return
            attribute = sketch.attributes.itemByName(
                lathe_sketch.ATTR_GROUP, lathe_sketch.ATTR_CENTERLINE)
            if attribute and attribute.value == line.entityToken:
                attribute.deleteMe()
                _log("lathe mode OFF for sketch %r" % sketch.name)
                return
            if attribute:
                attribute.deleteMe()
            sketch.attributes.add(lathe_sketch.ATTR_GROUP,
                                  lathe_sketch.ATTR_CENTERLINE,
                                  line.entityToken)
            try:
                # A centerline should read as one; cosmetic, never blocking.
                line.isConstruction = True
            except Exception:
                pass
            converted = convert_all(sketch, line, preserve_geometry=True)
            _log("lathe mode ON for sketch %r; %d dimension(s) converted"
                 % (sketch.name, converted))
            ui.messageBox(
                "Lathe Mode is ON for this sketch.\n\n"
                "%d existing dimension(s) now read as diameters (geometry "
                "unchanged).\n\nNew dimensions between the centerline and a "
                "parallel line take DIAMETER values - type the print's "
                "number and the line lands at half."
                % converted, "G-SEND.IO")
        except Exception:
            _log("lathe mode toggle failed\n" + traceback.format_exc())


class _DiaCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            on_execute = _DiaExecuteHandler()
            args.command.execute.add(on_execute)
            _handlers.append(on_execute)
        except Exception:
            _log("dia command created failed\n" + traceback.format_exc())


class _DiaExecuteHandler(adsk.core.CommandEventHandler):
    """Drop a diameter dimension from the right-clicked parallel line to
    the marked centerline - one click instead of the two-entity pick.
    Geometry does not move: the dim is born reading the line's current
    diameter, and editing its value from then on takes the typed number
    as the DIAMETER, natively."""

    def notify(self, args):
        global _converting
        try:
            ui = adsk.core.Application.get().userInterface
            sketch = _active_sketch()
            line = _context_line
            if sketch is None or line is None:
                return
            centerline = _centerline_of(sketch)
            if centerline is None:
                return
            start = line.startSketchPoint.geometry
            end = line.endSketchPoint.geometry
            mid = ((start.x + end.x) / 2.0, (start.y + end.y) / 2.0,
                   (start.z + end.z) / 2.0)
            tx, ty, tz = lathe_sketch.dia_text_point(
                mid, _point(centerline.startSketchPoint),
                _direction(centerline))
            _converting = True
            try:
                new = sketch.sketchDimensions.addLinearDiameterDimension(
                    centerline, line, adsk.core.Point3D.create(tx, ty, tz))
            finally:
                _converting = False
            if new is None:
                ui.messageBox(
                    "Could not place the diameter dimension - the line "
                    "may already be fully constrained.", "G-SEND.IO")
        except Exception:
            _log("dia dimension failed\n" + traceback.format_exc())


class _CommandTerminatedHandler(adsk.core.ApplicationCommandEventHandler):
    """After any command ends inside a lathe-mode sketch, sweep for fresh
    plain dims to the centerline and convert them. Sweeping beats
    filtering on command ids: a dimension can arrive through several
    commands, and a sweep of a sketch's dimension list is cheap."""

    def notify(self, args):
        try:
            if _converting:
                return
            event_args = adsk.core.ApplicationCommandEventArgs.cast(args)
            if event_args and event_args.commandId in (CMD_ID, DIA_CMD_ID):
                return
            ui = adsk.core.Application.get().userInterface
            if not _in_design_workspace(ui):
                return
            sketch = _active_sketch()
            if sketch is None:
                return
            centerline = _centerline_of(sketch)
            if centerline is None:
                return
            converted = convert_all(sketch, centerline,
                                    preserve_geometry=False)
            if converted:
                _log("converted %d new dimension(s) to diameters" % converted)
        except Exception:
            _log("watcher failed\n" + traceback.format_exc())


def start(app, ui):
    """Wire the mode up. Called from GSendIO.run, guarded there."""
    global _menu_handler, _terminated_handler
    cmd_def = ui.commandDefinitions.itemById(CMD_ID)
    if not cmd_def:
        cmd_def = ui.commandDefinitions.addButtonDefinition(
            CMD_ID, lathe_sketch.MENU_ON,
            "Mark this line as the spindle centerline: dimensions to it "
            "read as diameters, the way a lathe print does.",
            RESOURCE_FOLDER)
    else:
        try:
            cmd_def.resourceFolder = RESOURCE_FOLDER
        except Exception:
            pass
    on_created = _CommandCreatedHandler()
    cmd_def.commandCreated.add(on_created)
    _handlers.append(on_created)

    dia_def = ui.commandDefinitions.itemById(DIA_CMD_ID)
    if not dia_def:
        dia_def = ui.commandDefinitions.addButtonDefinition(
            DIA_CMD_ID, lathe_sketch.MENU_DIA,
            "Drop a diameter dimension from this line to the marked "
            "centerline - the dim then reads and takes DIAMETER values.",
            RESOURCE_FOLDER)
    else:
        try:
            dia_def.resourceFolder = RESOURCE_FOLDER
        except Exception:
            pass
    on_dia_created = _DiaCommandCreatedHandler()
    dia_def.commandCreated.add(on_dia_created)
    _handlers.append(on_dia_created)

    _menu_handler = _MarkingMenuHandler()
    ui.markingMenuDisplaying.add(_menu_handler)
    _handlers.append(_menu_handler)

    _terminated_handler = _CommandTerminatedHandler()
    ui.commandTerminated.add(_terminated_handler)
    _handlers.append(_terminated_handler)


def uninstall(ui):
    global _menu_handler, _terminated_handler
    try:
        if _menu_handler is not None:
            ui.markingMenuDisplaying.remove(_menu_handler)
    except Exception:
        pass
    try:
        if _terminated_handler is not None:
            ui.commandTerminated.remove(_terminated_handler)
    except Exception:
        pass
    _menu_handler = None
    _terminated_handler = None
    for cmd_id in (CMD_ID, DIA_CMD_ID):
        try:
            cmd_def = ui.commandDefinitions.itemById(cmd_id)
            if cmd_def:
                cmd_def.deleteMe()
        except Exception:
            pass
