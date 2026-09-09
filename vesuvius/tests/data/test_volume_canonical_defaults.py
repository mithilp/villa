"""Canonical energy/resolution defaults must come from scrolls.yaml.

The regression these cover: ``Volume(type="scroll", scroll_id=3)`` and
``scroll_id=4`` -- the exact form the class docstring advertises -- raised
``ValueError: URL not found in config for scroll=3, energy=53, resolution=3.24``
on a clean checkout. A hardcoded defaults table asked for resolutions and
energies that the shipped config has never contained, so two of the five
scrolls were unreachable through the documented call.

These tests read the config that actually ships, so they fail if the table and
the config drift apart again, rather than only checking today's values.
"""

import os

import pytest
import yaml

from vesuvius.data.volume import Volume


CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "src", "vesuvius", "install", "configs", "scrolls.yaml",
)


def _shipped_config():
    with open(CONFIG_PATH, "r") as handle:
        return yaml.safe_load(handle) or {}


class _Stub(Volume):
    """A Volume with the resolution logic reachable without any network I/O.

    ``Volume.__init__`` resolves a URL and opens a zarr store, so it cannot run
    offline. The defaults are decided before any of that, so bypassing __init__
    exercises exactly the code under test and nothing else.
    """

    def __init__(self, scroll_id, configs=CONFIG_PATH, energy=None):
        self.scroll_id = scroll_id
        self.configs = configs
        self.energy = energy
        self.verbose = False


@pytest.mark.parametrize("scroll_id", ["1", "2", "3", "4", "5"])
def test_defaults_resolve_to_an_entry_that_exists(scroll_id):
    """Every shipped scroll's defaults must address a real config entry."""
    config = _shipped_config()
    if scroll_id not in config:
        pytest.skip(f"scroll {scroll_id} is not in the shipped config")

    vol = _Stub(scroll_id)
    energy = vol.grab_canonical_energy()
    vol.energy = energy
    resolution = vol.grab_canonical_resolution()

    assert energy is not None, f"no default energy for scroll {scroll_id}"
    assert resolution is not None, f"no default resolution for scroll {scroll_id}"

    entry = config[scroll_id]
    assert str(energy) in entry, (
        f"scroll {scroll_id}: default energy {energy} is not in the config, "
        f"which offers {sorted(entry)}"
    )
    resolutions = entry[str(energy)]
    assert str(resolution) in resolutions, (
        f"scroll {scroll_id}: default resolution {resolution} is not in the "
        f"config, which offers {sorted(resolutions)} at {energy} keV"
    )


@pytest.mark.parametrize("scroll_id", ["3", "4"])
def test_scrolls_3_and_4_no_longer_pick_a_missing_resolution(scroll_id):
    """The specific regression: 3.24 um was requested and never existed."""
    vol = _Stub(scroll_id)
    vol.energy = vol.grab_canonical_energy()
    assert vol.grab_canonical_resolution() != 3.24


def test_scroll_1_default_is_unchanged():
    """The scrolls that already worked must resolve to the same scan as before."""
    vol = _Stub("1")
    assert vol.grab_canonical_energy() == 54
    vol.energy = 54
    assert vol.grab_canonical_resolution() == 7.91


def test_integer_scroll_id_behaves_like_the_string_form():
    """Volume(scroll_id=3) and Volume(scroll_id="3") must agree."""
    as_int, as_str = _Stub(3), _Stub("3")
    assert as_int.grab_canonical_energy() == as_str.grab_canonical_energy()
    as_int.energy = as_int.grab_canonical_energy()
    as_str.energy = as_str.grab_canonical_energy()
    assert as_int.grab_canonical_resolution() == as_str.grab_canonical_resolution()


def test_historical_default_wins_when_the_config_still_offers_it(tmp_path):
    """With several energies available, the long-standing default is kept.

    Otherwise upgrading the library would silently repoint existing scripts at
    a different scan.
    """
    config = tmp_path / "scrolls.yaml"
    config.write_text(yaml.safe_dump({
        "1": {"54": {"7.91": {"volume": "u"}}, "88": {"3.24": {"volume": "u"}}},
    }))
    vol = _Stub("1", configs=str(config))
    assert vol.grab_canonical_energy() == 54
    vol.energy = 54
    assert vol.grab_canonical_resolution() == 7.91


def test_config_wins_when_the_historical_default_is_gone(tmp_path):
    """This is the bug. The table said 3.24; only 7.91 is offered."""
    config = tmp_path / "scrolls.yaml"
    config.write_text(yaml.safe_dump({
        "3": {"53": {"7.91": {"volume": "u"}}},
    }))
    vol = _Stub("3", configs=str(config))
    assert vol.grab_canonical_energy() == 53
    vol.energy = 53
    assert vol.grab_canonical_resolution() == 7.91


def test_energy_falls_back_when_the_table_value_is_absent(tmp_path):
    """Scroll 4's table entry is 88 keV; the config only lists 53."""
    config = tmp_path / "scrolls.yaml"
    config.write_text(yaml.safe_dump({
        "4": {"53": {"7.91": {"volume": "u"}}},
    }))
    vol = _Stub("4", configs=str(config))
    assert vol.grab_canonical_energy() == 53


def test_lowest_energy_chosen_when_no_table_entry_applies(tmp_path):
    """Choice must be deterministic and numeric, not dict-insertion order."""
    config = tmp_path / "scrolls.yaml"
    config.write_text(yaml.safe_dump({
        "9": {"88": {"7.91": {"volume": "u"}}, "53": {"3.24": {"volume": "u"}}},
    }))
    vol = _Stub("9", configs=str(config))
    assert vol.grab_canonical_energy() == 53
    vol.energy = 53
    assert vol.grab_canonical_resolution() == 3.24


def test_missing_config_falls_back_to_the_builtin_table():
    """A missing config must not turn default resolution into a crash."""
    vol = _Stub("3", configs="/nonexistent/scrolls.yaml")
    assert vol.grab_canonical_energy() == 53
    vol.energy = 53
    assert vol.grab_canonical_resolution() == 3.24


def test_unparseable_config_falls_back_to_the_builtin_table(tmp_path):
    config = tmp_path / "scrolls.yaml"
    config.write_text("this: is: not: valid: yaml:\n  - [unclosed\n")
    vol = _Stub("1", configs=str(config))
    assert vol.grab_canonical_energy() == 54


def test_empty_config_falls_back_to_the_builtin_table(tmp_path):
    """`yaml.safe_load` returns None for an empty file."""
    config = tmp_path / "scrolls.yaml"
    config.write_text("")
    vol = _Stub("1", configs=str(config))
    assert vol.grab_canonical_energy() == 54
    vol.energy = 54
    assert vol.grab_canonical_resolution() == 7.91


def test_non_numeric_keys_do_not_raise(tmp_path):
    """A hand-edited config must not make sorting blow up."""
    config = tmp_path / "scrolls.yaml"
    config.write_text(yaml.safe_dump({
        "7": {"draft": {"tbd": {"volume": "u"}}, "53": {"7.91": {"volume": "u"}}},
    }))
    vol = _Stub("7", configs=str(config))
    assert vol.grab_canonical_energy() == 53
    vol.energy = 53
    assert vol.grab_canonical_resolution() == 7.91


def test_unknown_scroll_returns_none_rather_than_guessing():
    vol = _Stub("does-not-exist")
    assert vol.grab_canonical_energy() is None
    assert vol.grab_canonical_resolution() is None
