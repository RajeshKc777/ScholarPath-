"""Ripple geometry for the animated mic button (G125)."""

from scholarpath.ui.mic_button import ripple_rings


def test_two_rings_within_bounds() -> None:
    for step in range(20):
        phase = step / 20.0
        rings = ripple_rings(phase)
        assert len(rings) == 2
        for radius, opacity in rings:
            assert 0.55 <= radius <= 1.0
            assert 0.0 <= opacity <= 1.0


def test_rings_expand_and_fade_over_the_loop() -> None:
    previous_radius = 0.0
    previous_opacity = 1.1
    for step in range(19):  # one full loop, excluding the wrap point
        phase = step / 20.0
        radius, opacity = ripple_rings(phase)[0]
        assert radius > previous_radius
        assert opacity < previous_opacity
        previous_radius, previous_opacity = radius, opacity


def test_loop_wraps_back_to_the_start() -> None:
    assert ripple_rings(0.0) == ripple_rings(1.0)
    assert ripple_rings(0.0)[0] == (0.55, 1.0)


def test_the_two_rings_are_half_a_cycle_apart() -> None:
    first, second = ripple_rings(0.0)
    assert first == (0.55, 1.0)
    assert second == (0.775, 0.5)
