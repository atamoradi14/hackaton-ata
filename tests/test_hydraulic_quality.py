import numpy as np
import pytest

from floodtwin.hydraulics.quality import CASES, check_history, fixture_arrays


def test_equivalent_initial_storage_at_two_resolutions():
    volumes = []
    for name in ["weir", "weir_fine"]:
        case = CASES[name]
        _, _, bed, level = fixture_arrays(case)
        volumes.append(((level - bed) * case["dx"] ** 2).sum())
    assert volumes == pytest.approx([140, 140])


def test_mass_check_catches_transient_drift_even_if_final_recovers():
    with pytest.raises(ValueError, match="volume drift"):
        check_history([[0.2, 0.2], [0.3, 0.2], [0.2, 0.2]], [0, 0], 0.4, 1)


@pytest.mark.parametrize("levels, message", [
    ([[np.nan, 0.2]], "nonfinite"),
    ([[0.2]], "Missing"),
    ([[-0.1, 0.5]], "Negative"),
])
def test_bad_hydraulic_states_rejected(levels, message):
    with pytest.raises(ValueError, match=message):
        check_history(levels, [0, 0], 0.4, 1)
