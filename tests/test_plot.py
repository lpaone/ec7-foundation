"""Tests for ``ec7.plot``.

These tests verify that the three plotting helpers run end-to-end across
every supported footing/soil/action combination, that figure structure is
sensible (right number of axes, expected titles, expected number of
arrows/patches) and that the convenience methods on ``ShallowFoundation``
delegate correctly.

The tests run with the non-interactive Agg backend so they work headless
in CI.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")  # must be set before pyplot is imported anywhere else

import matplotlib.pyplot as plt
import pytest
from matplotlib.figure import Figure

from ec7 import (
    NTC2018_A2,
    CircularFooting,
    DesignActions,
    NTC2018_Seismic_Reduced,
    RectangularFooting,
    SeismicAction,
    ShallowFoundation,
    Soil,
    SoilLayer,
    SoilProfile,
    StripFooting,
    plot_actions,
    plot_all,
    plot_geometry,
    plot_soil_profile,
)

# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def monolayer_soil() -> Soil:
    return Soil(phi_k=32, c_k=5, gamma=19, gamma_sat=20, E=25_000, name="Sabbia")


@pytest.fixture
def undrained_soil() -> Soil:
    return Soil(
        phi_k=0, c_k=0, cu_k=80, gamma=18, gamma_sat=19,
        drained=False, E=8_000, name="Argilla",
    )


@pytest.fixture
def layered_profile() -> SoilProfile:
    return SoilProfile(
        layers=[
            SoilLayer(0, 2.0, Soil(phi_k=28, c_k=0, gamma=18, gamma_sat=19.5,
                                   E=15_000, name="Sabbia limosa")),
            SoilLayer(2.0, 8.0, Soil(phi_k=34, c_k=0, gamma=19, gamma_sat=20,
                                     E=30_000, name="Sabbia densa")),
            SoilLayer(8.0, 30.0, Soil(phi_k=36, c_k=0, gamma=20, gamma_sat=21,
                                      E=50_000, name="Ghiaia")),
        ],
        water_depth=3.0,
    )


@pytest.fixture
def static_actions() -> DesignActions:
    return DesignActions(V=1200, H_x=150, M_y=100)


@pytest.fixture
def full_actions() -> DesignActions:
    """Actions with all six components non-zero to exercise every branch."""
    return DesignActions(V=1500, H_x=300, H_y=80, M_x=120, M_y=200)


@pytest.fixture
def seismic_action() -> SeismicAction:
    return SeismicAction(kh=0.06, kv=0.03)


@pytest.fixture
def rect_foundation(monolayer_soil, static_actions) -> ShallowFoundation:
    return ShallowFoundation(
        RectangularFooting(B=2.5, L=3.5, D=1.5),
        soil=monolayer_soil,
        actions=static_actions,
        code=NTC2018_A2(),
    )


@pytest.fixture
def strip_foundation(monolayer_soil) -> ShallowFoundation:
    return ShallowFoundation(
        StripFooting(B=1.0, D=0.8),
        soil=monolayer_soil,
        actions=DesignActions(V=200, H_x=30),
        code=NTC2018_A2(),
    )


@pytest.fixture
def circular_foundation(monolayer_soil) -> ShallowFoundation:
    return ShallowFoundation(
        CircularFooting(R=1.5, D=1.2),
        soil=monolayer_soil,
        actions=DesignActions(V=800, H_x=50, M_y=60),
        code=NTC2018_A2(),
    )


@pytest.fixture
def seismic_layered_foundation(layered_profile, full_actions, seismic_action):
    return ShallowFoundation(
        RectangularFooting(B=2.5, L=3.5, D=1.5),
        profile=layered_profile,
        actions=full_actions,
        seismic=seismic_action,
        code=NTC2018_Seismic_Reduced(),
    )


@pytest.fixture(autouse=True)
def _close_figures():
    """Make sure tests don't leak figures across cases."""
    yield
    plt.close("all")


@pytest.fixture
def save_fig(tmp_path, request):
    """Persist a Matplotlib figure to the pytest ``tmp_path``.

    Returns a callable ``save(fig, suffix=None) -> Path`` so each test can
    drop its figure(s) under its own per-test temporary directory. The
    filename defaults to the test name; pass ``suffix`` to disambiguate
    when a test creates several figures.
    """
    def _save(fig, suffix: str | None = None):
        stem = request.node.name if suffix is None else f"{request.node.name}_{suffix}"
        path = tmp_path / f"{stem}.png"
        fig.savefig(path, dpi=110)
        assert path.is_file() and path.stat().st_size > 0
        return path

    return _save


# ---------------------------------------------------------------------------
# plot_geometry
# ---------------------------------------------------------------------------


def test_plot_geometry_rectangular_returns_figure_with_two_axes(rect_foundation, save_fig):
    fig = plot_geometry(rect_foundation)
    save_fig(fig)
    assert isinstance(fig, Figure)
    assert len(fig.axes) == 2
    titles = [ax.get_title() for ax in fig.axes]
    assert "Side view" in titles[0]
    assert "Top view" in titles[1]


def test_plot_geometry_rectangular_annotates_B_L_D(rect_foundation, save_fig):
    fig = plot_geometry(rect_foundation)
    save_fig(fig)
    text_blob = "\n".join(t.get_text() for ax in fig.axes for t in ax.texts)
    # numeric dimensions appear in the labels
    assert "B = 2.50" in text_blob
    assert "L = 3.50" in text_blob
    assert "D = 1.50" in text_blob


def test_plot_geometry_strip_marks_infinite_length(strip_foundation, save_fig):
    fig = plot_geometry(strip_foundation)
    save_fig(fig)
    text_blob = " ".join(t.get_text() for ax in fig.axes for t in ax.texts)
    assert "B = 1.00" in text_blob
    assert "D = 0.80" in text_blob
    # strip plots advertise L -> infinity
    assert "\\infty" in text_blob or "infty" in text_blob


def test_plot_geometry_circular_uses_diameter_and_radius(circular_foundation, save_fig):
    fig = plot_geometry(circular_foundation)
    save_fig(fig)
    text_blob = " ".join(t.get_text() for ax in fig.axes for t in ax.texts)
    assert "R = 1.50" in text_blob
    assert "2R = 3.00" in text_blob
    assert "D = 1.20" in text_blob


def test_plot_geometry_axes_equal_for_side_view(rect_foundation, save_fig):
    fig = plot_geometry(rect_foundation)
    save_fig(fig)
    # equal aspect is essential so dimensions read true
    assert fig.axes[0].get_aspect() == 1.0
    assert fig.axes[1].get_aspect() == 1.0


# ---------------------------------------------------------------------------
# plot_soil_profile
# ---------------------------------------------------------------------------


def test_plot_soil_profile_monolayer(rect_foundation, save_fig):
    fig = plot_soil_profile(rect_foundation)
    save_fig(fig)
    assert isinstance(fig, Figure)
    text_blob = " ".join(t.get_text() for ax in fig.axes for t in ax.texts)
    # monolayer is drawn with one band; D annotation present
    assert "D = 1.50" in text_blob
    assert "32.0" in text_blob  # phi_k of the test soil
    assert "Sabbia" in text_blob


def test_plot_soil_profile_layered_lists_every_layer(seismic_layered_foundation, save_fig):
    fig = plot_soil_profile(seismic_layered_foundation)
    save_fig(fig)
    text_blob = " ".join(t.get_text() for ax in fig.axes for t in ax.texts)
    # names get wrapped by \mathrm{...} with spaces escaped as `\ `
    for name in (r"Sabbia\ limosa", r"Sabbia\ densa", "Ghiaia"):
        assert name in text_blob
    # water table label
    assert "z_w = 3.00" in text_blob


def test_plot_soil_profile_undrained_shows_cu(undrained_soil, save_fig):
    f = ShallowFoundation(
        RectangularFooting(B=2.0, L=2.0, D=1.0),
        soil=undrained_soil,
        actions=DesignActions(V=500),
        code=NTC2018_A2(),
    )
    fig = plot_soil_profile(f)
    save_fig(fig)
    text_blob = " ".join(t.get_text() for ax in fig.axes for t in ax.texts)
    # undrained: c_{u,k} appears instead of phi_k / c_k
    assert "c_{u,k}" in text_blob
    assert "80.0" in text_blob
    assert "\\phi_k" not in text_blob


def test_plot_soil_profile_can_hide_footing(rect_foundation, save_fig):
    fig = plot_soil_profile(rect_foundation, show_footing=False)
    save_fig(fig)
    text_blob = " ".join(t.get_text() for ax in fig.axes for t in ax.texts)
    # the D label is part of the footing overlay
    assert "D = " not in text_blob


# ---------------------------------------------------------------------------
# plot_actions
# ---------------------------------------------------------------------------


def test_plot_actions_static(rect_foundation, save_fig):
    fig = plot_actions(rect_foundation)
    save_fig(fig)
    assert isinstance(fig, Figure)
    assert len(fig.axes) == 2
    text_blob = " ".join(t.get_text() for ax in fig.axes for t in ax.texts)
    assert "V = 1200" in text_blob
    assert "H_x = 150" in text_blob
    assert "M_y = 100" in text_blob
    # static: title must not advertise the seismic combination
    assert "seismic" not in fig.get_suptitle()


def test_plot_actions_auto_enables_seismic(seismic_layered_foundation, save_fig):
    fig = plot_actions(seismic_layered_foundation)
    save_fig(fig)
    text_blob = " ".join(t.get_text() for ax in fig.axes for t in ax.texts)
    assert "k_h" in text_blob and "k_v" in text_blob
    # 6% of V = 1500 = 90 kN
    assert "90" in text_blob
    assert "seismic" in fig.get_suptitle()


def test_plot_actions_show_seismic_force_off(seismic_layered_foundation, save_fig):
    fig = plot_actions(seismic_layered_foundation, show_seismic=False)
    save_fig(fig)
    text_blob = " ".join(t.get_text() for ax in fig.axes for t in ax.texts)
    assert "k_h" not in text_blob


def test_plot_actions_show_seismic_force_on_without_action(rect_foundation, save_fig):
    # rect_foundation has no SeismicAction, but the user can still force the
    # title flag on; this must not raise even though no seismic arrows draw.
    fig = plot_actions(rect_foundation, show_seismic=False)
    save_fig(fig)
    assert isinstance(fig, Figure)


def test_plot_actions_labels_every_component(full_actions, seismic_action,
                                              layered_profile, save_fig):
    """Every non-zero component must produce a labelled annotation."""
    f = ShallowFoundation(
        RectangularFooting(B=2.5, L=3.5, D=1.5),
        profile=layered_profile,
        actions=full_actions,
        seismic=seismic_action,
        code=NTC2018_Seismic_Reduced(),
    )
    fig = plot_actions(f)
    save_fig(fig)
    text_blob = " ".join(t.get_text() for ax in fig.axes for t in ax.texts)
    for needle in (
        f"V = {int(full_actions.V)}",
        f"H_x = {int(full_actions.H_x)}",
        f"H_y = {int(full_actions.H_y)}",
        f"M_x = {int(full_actions.M_x)}",
        f"M_y = {int(full_actions.M_y)}",
        "k_h",
        "k_v",
    ):
        assert needle in text_blob, f"missing label: {needle!r}"


# ---------------------------------------------------------------------------
# ShallowFoundation methods + plot_all
# ---------------------------------------------------------------------------


def test_shallow_foundation_methods_delegate(rect_foundation, save_fig):
    f1 = rect_foundation.plot_geometry()
    f2 = rect_foundation.plot_soil_profile()
    f3 = rect_foundation.plot_actions()
    save_fig(f1, suffix="geometry")
    save_fig(f2, suffix="soil")
    save_fig(f3, suffix="actions")
    for fig in (f1, f2, f3):
        assert isinstance(fig, Figure)


def test_plot_all_returns_three_figures(seismic_layered_foundation, save_fig):
    figs = plot_all(seismic_layered_foundation)
    for fig, suffix in zip(figs, ("geometry", "soil", "actions"), strict=True):
        save_fig(fig, suffix=suffix)
    assert len(figs) == 3
    assert all(isinstance(f, Figure) for f in figs)
    # the third one is the actions plot and must include seismic since the
    # foundation carries a SeismicAction
    assert "seismic" in figs[2].get_suptitle()
