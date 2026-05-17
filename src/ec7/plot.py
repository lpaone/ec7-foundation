"""Schematic figures for a ``ShallowFoundation``.

Three entry points that all take a :class:`~ec7.foundation.ShallowFoundation`
instance and return a Matplotlib ``Figure``:

    - :func:`plot_geometry` — footing dimensions in side and top view.
    - :func:`plot_soil_profile` — stratigraphy with material properties and
      water table; the footing is overlaid.
    - :func:`plot_actions` — reference system with arrows for V, H_x, H_y,
      M_x, M_y and, optionally, the seismic inertial forces.

Axis convention follows the rest of the package: x parallel to B (short
side), y parallel to L (long side), z vertical positive upward; depth is
plotted as negative z so the ground surface sits at z = 0.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch

from .geometry import CircularFooting, Footing, StripFooting
from .profile import SoilLayer

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure

    from .foundation import ShallowFoundation


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _footing_B(footing: Footing) -> float:
    if isinstance(footing, CircularFooting):
        return 2 * footing.R
    return footing.B  # RectangularFooting / StripFooting


def _footing_L(footing: Footing) -> float | None:
    if isinstance(footing, StripFooting):
        return None  # conventionally infinite
    if isinstance(footing, CircularFooting):
        return 2 * footing.R
    return footing.L


def _profile_view_depth(foundation: ShallowFoundation) -> float:
    """Reasonable depth window for the side view."""
    D = foundation.footing.D
    B = _footing_B(foundation.footing)
    if foundation.profile is not None:
        last_bot = foundation.profile.layers[-1].bottom
        if math.isfinite(last_bot):
            return max(last_bot, D + 1.5 * B)
        # last layer is infinite: pick something reasonable
        prev = foundation.profile.layers[-1].top
        return max(prev + 2.0 * B, D + 2.0 * B)
    return D + 2.0 * B


# ---------------------------------------------------------------------------
# 1. Geometry
# ---------------------------------------------------------------------------


def plot_geometry(
    foundation: ShallowFoundation,
    figsize: tuple[float, float] = (11.0, 5.0),
) -> Figure:
    """Plot footing geometry (side + top view) with annotated dimensions.

    Args:
        foundation: ``ShallowFoundation`` whose footing should be drawn.
        figsize: Matplotlib figure size.

    Returns:
        The created ``Figure``.
    """
    footing = foundation.footing

    fig, axes = plt.subplots(1, 2, figsize=figsize)
    _draw_footing_side(axes[0], footing)
    _draw_footing_top(axes[1], footing)
    fig.suptitle("Foundation geometry", fontsize=13, fontweight="bold")
    fig.tight_layout()
    return fig


def _draw_footing_side(ax: Axes, footing: Footing) -> None:

    B = _footing_B(footing)
    D = footing.D
    t = max(0.1 * D, 0.15 * B, 0.3)  # representative slab thickness for drawing
    margin = 0.7 * B

    # background soil (above and at sides of the footing)
    soil_bot = -(D + t + 0.6 * B)
    ax.add_patch(
        plt.Rectangle(
            (-B / 2 - margin, soil_bot),
            B + 2 * margin,
            -soil_bot,
            facecolor="wheat",
            edgecolor="none",
            alpha=0.35,
            zorder=0,
        )
    )

    # ground surface
    ax.plot(
        [-B / 2 - margin, B / 2 + margin],
        [0, 0],
        color="black",
        linewidth=1.2,
        zorder=1,
    )

    # footing slab
    footing_top = -D + t
    ax.add_patch(
        plt.Rectangle(
            (-B / 2, -D),
            B,
            t,
            facecolor="lightgray",
            edgecolor="black",
            linewidth=1.6,
            zorder=3,
        )
    )

    # schematic column
    col_w = max(0.25 * B, 0.3)
    col_h = max(D - t, 0.3) + 0.35 * B
    ax.add_patch(
        plt.Rectangle(
            (-col_w / 2, footing_top),
            col_w,
            col_h,
            facecolor="lightgray",
            edgecolor="black",
            linewidth=1.0,
            zorder=3,
        )
    )

    # ---- dimensions ----
    # D — to the right of the footing
    x_dim = B / 2 + 0.35 * margin
    ax.annotate(
        "", xy=(x_dim, 0), xytext=(x_dim, -D),
        arrowprops={"arrowstyle": "<->", "color": "black", "lw": 1.2},
    )
    ax.text(
        x_dim + 0.06 * B, -D / 2,
        rf"$D = {D:.2f}\ \mathrm{{m}}$",
        va="center", ha="left", fontsize=10,
    )

    # B — below the footing
    y_dim = -D - t - 0.25 * B
    ax.annotate(
        "", xy=(-B / 2, y_dim), xytext=(B / 2, y_dim),
        arrowprops={"arrowstyle": "<->", "color": "black", "lw": 1.2},
    )
    ax.text(
        0, y_dim - 0.07 * B,
        rf"$B = {B:.2f}\ \mathrm{{m}}$",
        ha="center", va="top", fontsize=10,
    )

    title = "Side view"
    if isinstance(footing, CircularFooting):
        title += "  (diameter)"
    elif isinstance(footing, StripFooting):
        title += "  (strip, infinite along $y$)"
    ax.set_title(title)
    ax.set_xlabel(r"$x$ [m]")
    ax.set_ylabel(r"$z$ [m]")
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(-B / 2 - margin, B / 2 + margin)
    ax.set_ylim(soil_bot, max(D, 0.3) + col_h + 0.1 * B)


def _draw_footing_top(ax: Axes, footing: Footing) -> None:

    if isinstance(footing, CircularFooting):
        R = footing.R
        margin = 0.5 * R
        ax.add_patch(
            plt.Circle((0, 0), R, facecolor="lightgray", edgecolor="black", linewidth=1.6)
        )
        # diameter dimension
        ax.annotate(
            "", xy=(-R, 0), xytext=(R, 0),
            arrowprops={"arrowstyle": "<->", "color": "black", "lw": 1.2},
        )
        ax.text(
            0, -R - 0.2 * R,
            rf"$D_{{f}} = 2R = {2 * R:.2f}\ \mathrm{{m}}$",
            ha="center", va="top", fontsize=10,
        )
        # radius dimension
        ax.annotate(
            "", xy=(0, 0), xytext=(R, 0),
            arrowprops={"arrowstyle": "->", "color": "dimgray", "lw": 1.0},
        )
        ax.text(0.5 * R, 0.06 * R, rf"$R = {R:.2f}\ \mathrm{{m}}$",
                ha="center", va="bottom", fontsize=10, color="dimgray")
        lim = R + margin
        ax.set_xlim(-lim, lim)
        ax.set_ylim(-lim, lim)
        ax.set_title("Top view")
    elif isinstance(footing, StripFooting):
        B = footing.B
        # show a representative strip segment along y
        L_show = max(3 * B, 2.0)
        ax.add_patch(
            plt.Rectangle(
                (-B / 2, -L_show / 2), B, L_show,
                facecolor="lightgray", edgecolor="black", linewidth=1.6,
            )
        )
        # dashed extensions
        for sign in (-1, 1):
            ax.plot(
                [-B / 2, B / 2], [sign * L_show / 2, sign * L_show / 2 + 0.5 * B],
                color="black", linewidth=1.0, linestyle="--",
            )
            ax.plot(
                [-B / 2, -B / 2], [sign * L_show / 2, sign * L_show / 2 + 0.5 * B],
                color="black", linewidth=1.0, linestyle="--",
            )
            ax.plot(
                [B / 2, B / 2], [sign * L_show / 2, sign * L_show / 2 + 0.5 * B],
                color="black", linewidth=1.0, linestyle="--",
            )
        # B dimension
        ax.annotate(
            "", xy=(-B / 2, -L_show / 2 - 0.35 * B),
            xytext=(B / 2, -L_show / 2 - 0.35 * B),
            arrowprops={"arrowstyle": "<->", "color": "black", "lw": 1.2},
        )
        ax.text(0, -L_show / 2 - 0.5 * B,
                rf"$B = {B:.2f}\ \mathrm{{m}}$",
                ha="center", va="top", fontsize=10)
        ax.text(0.6 * B, 0, r"$L \to \infty$", fontsize=10, va="center")
        lim = max(B, L_show / 2 + B)
        ax.set_xlim(-lim, lim)
        ax.set_ylim(-L_show / 2 - 0.8 * B, L_show / 2 + 0.8 * B)
        ax.set_title("Top view (strip)")
    else:
        B = footing.B
        L = footing.L
        margin = 0.35 * max(B, L)
        ax.add_patch(
            plt.Rectangle(
                (-B / 2, -L / 2), B, L,
                facecolor="lightgray", edgecolor="black", linewidth=1.6,
            )
        )
        # B (along x) dimension below
        y_b = -L / 2 - 0.35 * margin
        ax.annotate(
            "", xy=(-B / 2, y_b), xytext=(B / 2, y_b),
            arrowprops={"arrowstyle": "<->", "color": "black", "lw": 1.2},
        )
        ax.text(0, y_b - 0.18 * margin,
                rf"$B = {B:.2f}\ \mathrm{{m}}$",
                ha="center", va="top", fontsize=10)
        # L (along y) dimension to the right
        x_l = B / 2 + 0.35 * margin
        ax.annotate(
            "", xy=(x_l, -L / 2), xytext=(x_l, L / 2),
            arrowprops={"arrowstyle": "<->", "color": "black", "lw": 1.2},
        )
        ax.text(x_l + 0.1 * margin, 0,
                rf"$L = {L:.2f}\ \mathrm{{m}}$",
                ha="left", va="center", fontsize=10, rotation=90)
        ax.set_xlim(-B / 2 - margin, B / 2 + margin)
        ax.set_ylim(-L / 2 - margin, L / 2 + margin)
        ax.set_title("Top view")

    ax.set_xlabel(r"$x$ [m]")
    ax.set_ylabel(r"$y$ [m]")
    ax.set_aspect("equal", adjustable="box")


# ---------------------------------------------------------------------------
# 2. Soil profile
# ---------------------------------------------------------------------------


# Cycling palette for layers; intentionally muted earth tones.
_LAYER_COLORS = (
    "#d9c39a", "#c7a984", "#b89070", "#a87a5c", "#94634a",
    "#d8b384", "#bfa17a", "#9c8268",
)


def plot_soil_profile(
    foundation: ShallowFoundation,
    figsize: tuple[float, float] = (10.0, 7.0),
    show_footing: bool = True,
) -> Figure:
    """Plot the stratigraphy with material properties and water table.

    Layers are drawn as horizontal bands. Each band carries the layer name
    and its main parameters ($\\phi_k$, $c_k$, $\\gamma$, $\\gamma_{sat}$,
    $E$). The footing position is overlaid by default.

    Args:
        foundation: ``ShallowFoundation`` to draw.
        figsize: Matplotlib figure size.
        show_footing: If True, overlay the footing slab at depth D.

    Returns:
        The created ``Figure``.
    """

    B = _footing_B(foundation.footing)
    z_max = _profile_view_depth(foundation)
    x_extent = max(3.0 * B, 4.0)
    x_lim = x_extent / 2

    fig, ax = plt.subplots(figsize=figsize)

    # layers: from profile if present, else single soil
    if foundation.profile is not None:
        water_depth = foundation.profile.water_depth
        layers: list[SoilLayer] = []
        for layer in foundation.profile.layers:
            bot = layer.bottom if math.isfinite(layer.bottom) else z_max
            bot = min(bot, z_max)
            if bot <= layer.top:
                continue
            layers.append(SoilLayer(top=layer.top, bottom=bot, soil=layer.soil))
    else:
        water_depth = foundation.soil.water_depth if foundation.soil else None
        layers = [SoilLayer(top=0.0, bottom=z_max, soil=foundation.soil)]

    # draw layers
    for i, layer in enumerate(layers):
        color = _LAYER_COLORS[i % len(_LAYER_COLORS)]
        ax.add_patch(
            plt.Rectangle(
                (-x_lim, -layer.bottom),
                2 * x_lim,
                layer.bottom - layer.top,
                facecolor=color,
                edgecolor="black",
                linewidth=0.8,
                alpha=0.55,
                zorder=1,
            )
        )
        _annotate_layer(ax, layer, x_lim)

    # water table
    if water_depth is not None and 0 < water_depth <= z_max:
        ax.plot(
            [-x_lim, x_lim], [-water_depth, -water_depth],
            color="#1f77b4", linewidth=1.4, linestyle="-", zorder=4,
        )
        ax.plot(
            [-x_lim * 0.6], [-water_depth],
            marker="v", color="#1f77b4", markersize=10, zorder=5,
        )
        ax.text(
            -x_lim * 0.55, -water_depth - 0.005 * z_max,
            rf"$z_w = {water_depth:.2f}\ \mathrm{{m}}$",
            color="#1f77b4", ha="left", va="top", fontsize=8.5,
        )

    # ground surface line
    ax.plot([-x_lim, x_lim], [0, 0], color="black", linewidth=1.2, zorder=3)

    # footing
    if show_footing:
        D = foundation.footing.D
        t = max(0.08 * D, 0.12 * B, 0.25)
        ax.add_patch(
            plt.Rectangle(
                (-B / 2, -D),
                B,
                t,
                facecolor="lightgray",
                edgecolor="black",
                linewidth=1.6,
                zorder=6,
            )
        )
        # D dimension: arrows traverse the soil, label sits in the empty
        # white band above the ground surface so it never clashes with the
        # per-layer property labels (which crowd thin top layers).
        x_dim = -B / 2 - 0.12 * x_lim
        ax.annotate(
            "", xy=(x_dim, 0), xytext=(x_dim, -D),
            arrowprops={"arrowstyle": "<->", "color": "black", "lw": 1.0},
        )
        sky = max(0.05 * z_max, 0.4)
        ax.text(
            x_dim, 0.5 * sky,
            rf"$D = {D:.2f}\ \mathrm{{m}}$",
            ha="center", va="center", fontsize=9,
        )

    ax.set_xlim(-x_lim, x_lim)
    ax.set_ylim(-z_max, max(0.05 * z_max, 0.4))
    ax.set_xlabel(r"$x$ [m]")
    ax.set_ylabel(r"$z$ [m]  (depth)")
    ax.set_title("Soil profile", fontsize=13, fontweight="bold")
    ax.grid(False)
    fig.tight_layout()
    return fig


def _annotate_layer(ax: Axes, layer: SoilLayer, x_lim: float) -> None:
    soil = layer.soil
    z_top = -layer.top

    # Layer name + depth range, single line, top-left of the layer band.
    header = (
        rf"$\bf{{{_latex_safe(soil.name)}}}$"
        + rf"   $z = {layer.top:.2f} - {layer.bottom:.2f}\ \mathrm{{m}}$"
    )
    ax.text(
        -x_lim * 0.97, z_top - 0.08,
        header,
        ha="left", va="top", fontsize=8.5, zorder=5,
    )

    # Material properties, single horizontal line, top-right of the layer band.
    parts: list[str] = []
    if soil.drained:
        parts.append(rf"$\phi_k\!=\!{soil.phi_k:.1f}^\circ$")
        parts.append(rf"$c_k\!=\!{soil.c_k:.1f}$ kPa")
    else:
        parts.append(rf"$c_{{u,k}}\!=\!{soil.cu_k:.1f}$ kPa")
    parts.append(rf"$\gamma\!=\!{soil.gamma:.1f}$")
    parts.append(rf"$\gamma_{{sat}}\!=\!{soil.gamma_sat:.1f}$ kN/m$^3$")
    if soil.E is not None:
        parts.append(rf"$E\!=\!{soil.E:.0f}$ kPa")
    ax.text(
        x_lim * 0.97, z_top - 0.08,
        "    ".join(parts),
        ha="right", va="top", fontsize=8.5, zorder=5,
    )


def _latex_safe(name: str) -> str:
    # mathtext interprets spaces oddly; replace with thin spaces inside \mathrm
    return r"\mathrm{" + name.replace(" ", r"\ ") + "}"


# ---------------------------------------------------------------------------
# 3. Design-actions reference system
# ---------------------------------------------------------------------------


def plot_actions(
    foundation: ShallowFoundation,
    show_seismic: bool | None = None,
    figsize: tuple[float, float] = (12.0, 5.5),
) -> Figure:
    """Plot the design-action reference system with vectors.

    Two subplots:
        - left: side view (x-z plane) with V, H_x and M_y;
        - right: top view (x-y plane) with H_x, H_y, M_x and M_y.

    Seismic inertial forces ($k_h V$ and $k_v V$, illustrative) are drawn
    when ``show_seismic`` is True (or auto-enabled when the foundation has
    a ``SeismicAction``).

    Args:
        foundation: ``ShallowFoundation`` to draw.
        show_seismic: Force-enable or force-disable seismic arrows.
            ``None`` (default) auto-enables them iff
            ``foundation.seismic`` is not ``None``.
        figsize: Matplotlib figure size.

    Returns:
        The created ``Figure``.
    """

    if show_seismic is None:
        show_seismic = (
            foundation.seismic is not None and foundation.seismic.is_seismic
        )

    fig, axes = plt.subplots(1, 2, figsize=figsize)
    _draw_actions_side(axes[0], foundation, show_seismic=show_seismic)
    _draw_actions_top(axes[1], foundation, show_seismic=show_seismic)

    title = "Design actions — reference system"
    if show_seismic:
        title += "  (static + seismic)"
    fig.suptitle(title, fontsize=13, fontweight="bold")
    fig.tight_layout()
    return fig


def _draw_actions_side(ax: Axes, foundation: ShallowFoundation, *, show_seismic: bool) -> None:
    footing = foundation.footing
    actions = foundation.actions

    B = _footing_B(footing)
    D = footing.D
    t = max(0.08 * D, 0.1 * B, 0.2)
    margin = 0.9 * B

    # ground & footing
    ax.add_patch(
        plt.Rectangle(
            (-B / 2 - margin, -(D + 2 * B)),
            B + 2 * margin, (D + 2 * B),
            facecolor="wheat", edgecolor="none", alpha=0.3, zorder=0,
        )
    )
    ax.plot([-B / 2 - margin, B / 2 + margin], [0, 0],
            color="black", linewidth=1.0, zorder=1)
    ax.add_patch(
        plt.Rectangle(
            (-B / 2, -D), B, t,
            facecolor="lightgray", edgecolor="black", linewidth=1.4, zorder=3,
        )
    )

    # column
    col_w = max(0.25 * B, 0.25)
    col_h = max(D - t, 0.3) + 0.6 * B
    ax.add_patch(
        plt.Rectangle(
            (-col_w / 2, -D + t), col_w, col_h,
            facecolor="lightgray", edgecolor="black", linewidth=1.0, zorder=3,
        )
    )

    z_app = -D + t + col_h  # action application point (top of column)
    scale = 0.55 * B  # arrow length unit

    # local axes inset
    _draw_axes_inset(
        ax,
        origin=(-B / 2 - 0.6 * margin, -D - 0.6 * B),
        size=0.4 * B,
        labels=(r"$x$", r"$z$"),
    )

    # V (down, applied from above)
    _vector(
        ax, (0, z_app + scale), (0, z_app),
        label=rf"$V = {actions.V:.0f}\ \mathrm{{kN}}$",
        label_pos=(0.05 * B, z_app + scale + 0.05 * B),
        color="black",
    )

    # H_x
    if actions.H_x != 0:
        sign = 1 if actions.H_x > 0 else -1
        _vector(
            ax,
            (-sign * scale, z_app), (0, z_app),
            label=rf"$H_x = {actions.H_x:.0f}\ \mathrm{{kN}}$",
            label_pos=(-sign * 1.1 * scale, z_app + 0.08 * B),
            color="black",
            label_ha="right" if sign > 0 else "left",
        )

    # M_y (moment about y-axis -> rotation in x-z plane)
    if actions.M_y != 0:
        _moment_arc(
            ax, center=(0, z_app), radius=0.45 * B,
            ccw=(actions.M_y > 0),
            label=rf"$M_y = {actions.M_y:.0f}\ \mathrm{{kN\cdot m}}$",
            label_pos=(0.55 * B, z_app + 0.5 * B),
            color="purple",
        )

    # seismic
    if show_seismic and foundation.seismic is not None:
        s = foundation.seismic
        z_cg = -D + t + 0.55 * col_h
        F_h = s.kh * actions.V
        _vector(
            ax,
            (-0.6 * scale, z_cg), (0, z_cg),
            label=rf"$k_h\,V = {F_h:.0f}\ \mathrm{{kN}}$",
            label_pos=(-0.7 * scale, z_cg + 0.08 * B),
            color="#d62728",
            label_ha="right",
        )
        if s.kv != 0:
            F_v = s.kv * actions.V
            _vector(
                ax,
                (0.35 * B, z_cg + 0.6 * scale),
                (0.35 * B, z_cg),
                label=rf"$k_v\,V = {F_v:.0f}\ \mathrm{{kN}}$",
                label_pos=(0.4 * B, z_cg + 0.7 * scale),
                color="#d62728",
                label_ha="left",
            )

    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(-B / 2 - margin, B / 2 + margin)
    ax.set_ylim(-(D + 2 * B), z_app + 1.4 * scale)
    ax.set_xlabel(r"$x$ [m]")
    ax.set_ylabel(r"$z$ [m]")
    ax.set_title("Side view  (x-z plane)")


def _draw_actions_top(ax: Axes, foundation: ShallowFoundation, *, show_seismic: bool) -> None:
    footing = foundation.footing
    actions = foundation.actions

    B = _footing_B(footing)
    L = _footing_L(footing) if not isinstance(footing, StripFooting) else 2.5 * B
    if L is None:
        L = 2.5 * B
    margin = 0.45 * max(B, L)

    if isinstance(footing, CircularFooting):
        ax.add_patch(
            plt.Circle((0, 0), footing.R, facecolor="lightgray",
                       edgecolor="black", linewidth=1.4)
        )
    else:
        ax.add_patch(
            plt.Rectangle(
                (-B / 2, -L / 2), B, L,
                facecolor="lightgray", edgecolor="black", linewidth=1.4,
            )
        )

    arrow_len = 0.45 * min(B, L)

    # local axes inset
    _draw_axes_inset(
        ax,
        origin=(-B / 2 - 0.5 * margin, -L / 2 - 0.5 * margin),
        size=0.35 * min(B, L),
        labels=(r"$x$", r"$y$"),
    )

    # H_x
    if actions.H_x != 0:
        sign = 1 if actions.H_x > 0 else -1
        _vector(
            ax,
            (-sign * arrow_len, 0), (0, 0),
            label=rf"$H_x = {actions.H_x:.0f}\ \mathrm{{kN}}$",
            label_pos=(-sign * 1.15 * arrow_len, 0.06 * L),
            color="black",
            label_ha="right" if sign > 0 else "left",
        )

    # H_y
    if actions.H_y != 0:
        sign = 1 if actions.H_y > 0 else -1
        _vector(
            ax,
            (0, -sign * arrow_len), (0, 0),
            label=rf"$H_y = {actions.H_y:.0f}\ \mathrm{{kN}}$",
            label_pos=(0.06 * B, -sign * 1.15 * arrow_len),
            color="black",
            label_va="bottom" if sign > 0 else "top",
        )

    # V at center (out of page)
    ax.scatter([0], [0], s=90, facecolor="white",
               edgecolor="black", linewidth=1.4, zorder=6)
    ax.scatter([0], [0], s=15, facecolor="black", zorder=7)
    ax.text(0.08 * B, 0.08 * L,
            rf"$V = {actions.V:.0f}\ \mathrm{{kN}}\ (\downarrow)$",
            fontsize=9, ha="left", va="bottom")

    # M_x: rotation about x-axis -> arc in y-z plane;
    # in top view we draw a double-head arrow along +x (right-hand rule).
    if actions.M_x != 0:
        sign = 1 if actions.M_x > 0 else -1
        x1, x2 = -sign * 0.35 * arrow_len, sign * 0.35 * arrow_len
        y0 = 0.35 * L
        ax.annotate(
            "", xy=(x2, y0), xytext=(x1, y0),
            arrowprops={"arrowstyle": "<|-|>", "color": "purple", "lw": 2.2,
                            "mutation_scale": 18},
        )
        ax.text(
            0, y0 + 0.05 * L,
            rf"$M_x = {actions.M_x:.0f}\ \mathrm{{kN\cdot m}}$",
            color="purple", ha="center", va="bottom", fontsize=9,
        )

    # M_y: same convention, double-head arrow along +y
    if actions.M_y != 0:
        sign = 1 if actions.M_y > 0 else -1
        y1, y2 = -sign * 0.35 * arrow_len, sign * 0.35 * arrow_len
        x0 = 0.35 * B
        ax.annotate(
            "", xy=(x0, y2), xytext=(x0, y1),
            arrowprops={"arrowstyle": "<|-|>", "color": "purple", "lw": 2.2,
                            "mutation_scale": 18},
        )
        ax.text(
            x0 + 0.05 * B, 0,
            rf"$M_y = {actions.M_y:.0f}\ \mathrm{{kN\cdot m}}$",
            color="purple", ha="left", va="center", fontsize=9, rotation=90,
        )

    if show_seismic and foundation.seismic is not None:
        s = foundation.seismic
        F_h = s.kh * actions.V
        ax.text(
            -B / 2, L / 2 + 0.25 * margin,
            (rf"seismic: $k_h = {s.kh:.3f}$, "
             rf"$k_v = {s.kv:.3f}$, "
             rf"$k_h V = {F_h:.0f}\ \mathrm{{kN}}$"),
            color="#d62728", fontsize=9, ha="left", va="bottom",
        )

    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(-B / 2 - margin, B / 2 + margin)
    ax.set_ylim(-L / 2 - margin, L / 2 + margin)
    ax.set_xlabel(r"$x$ [m]")
    ax.set_ylabel(r"$y$ [m]")
    ax.set_title("Top view  (x-y plane)")


# ---------------------------------------------------------------------------
# arrow / axes-inset primitives
# ---------------------------------------------------------------------------


def _vector(
    ax: Axes,
    tail: tuple[float, float],
    head: tuple[float, float],
    *,
    label: str,
    label_pos: tuple[float, float],
    color: str = "black",
    label_ha: str = "center",
    label_va: str = "center",
) -> None:
    ax.annotate(
        "", xy=head, xytext=tail,
        arrowprops={"arrowstyle": "-|>", "color": color, "lw": 2.2,
                        "mutation_scale": 18},
        zorder=6,
    )
    ax.text(
        label_pos[0], label_pos[1], label,
        color=color, ha=label_ha, va=label_va, fontsize=9,
    )


def _moment_arc(
    ax: Axes,
    center: tuple[float, float],
    radius: float,
    *,
    ccw: bool,
    label: str,
    label_pos: tuple[float, float],
    color: str = "purple",
) -> None:
    """Draw a curved arrow representing a moment vector."""

    if ccw:
        theta1, theta2 = math.radians(20), math.radians(290)
    else:
        theta1, theta2 = math.radians(290), math.radians(20)

    p1 = (center[0] + radius * math.cos(theta1),
          center[1] + radius * math.sin(theta1))
    p2 = (center[0] + radius * math.cos(theta2),
          center[1] + radius * math.sin(theta2))
    connectionstyle = f"arc3,rad={0.6 if ccw else -0.6}"
    arrow = FancyArrowPatch(
        p1, p2,
        connectionstyle=connectionstyle,
        arrowstyle="-|>", mutation_scale=15,
        color=color, lw=2.0, zorder=5,
    )
    ax.add_patch(arrow)
    ax.text(label_pos[0], label_pos[1], label,
            color=color, ha="left", va="center", fontsize=9)


def _draw_axes_inset(
    ax: Axes,
    *,
    origin: tuple[float, float],
    size: float,
    labels: tuple[str, str],
) -> None:
    """Tiny coordinate axes triad as a reference, drawn in data coords."""
    x0, y0 = origin
    ax.annotate(
        "", xy=(x0 + size, y0), xytext=(x0, y0),
        arrowprops={"arrowstyle": "-|>", "color": "red", "lw": 1.6,
                        "mutation_scale": 12},
    )
    ax.annotate(
        "", xy=(x0, y0 + size), xytext=(x0, y0),
        arrowprops={"arrowstyle": "-|>", "color": "blue", "lw": 1.6,
                        "mutation_scale": 12},
    )
    ax.text(x0 + 1.15 * size, y0, labels[0], color="red",
            va="center", ha="left", fontsize=10)
    ax.text(x0, y0 + 1.15 * size, labels[1], color="blue",
            va="bottom", ha="center", fontsize=10)


# ---------------------------------------------------------------------------
# convenience
# ---------------------------------------------------------------------------


def plot_all(
    foundation: ShallowFoundation,
    show_seismic: bool | None = None,
) -> tuple[Figure, Figure, Figure]:
    """Return all three figures at once.

    Equivalent to calling :func:`plot_geometry`, :func:`plot_soil_profile`
    and :func:`plot_actions` in sequence.
    """
    return (
        plot_geometry(foundation),
        plot_soil_profile(foundation),
        plot_actions(foundation, show_seismic=show_seismic),
    )


__all__ = [
    "plot_geometry",
    "plot_soil_profile",
    "plot_actions",
    "plot_all",
]
