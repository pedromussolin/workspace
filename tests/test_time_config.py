import pytest

from ws import userconfig
from ws.userconfig import ConfigInvalid, TimeConfig, load_config, load_time

BASE = '[standup]\nrepo_roots = ["/nowhere"]\n'


def write(ws_config, text):
    (ws_config / "config.toml").write_text(BASE + text, encoding="utf-8")


def test_the_defaults_are_the_floor_of_8h48_and_30_idle_minutes(ws_config):
    write(ws_config, "")

    assert load_config().time == TimeConfig(day_floor_minutes=528, idle_minutes=30)
    assert load_time() == TimeConfig(528, 30)


@pytest.mark.parametrize(
    ("text", "minutes"),
    [("8h48", 528), ("8h 48m", 528), ("8h48m", 528), ("8h", 480), ("528m", 528), ("24h", 1440)],
)
def test_the_floor_reads_hours_and_minutes(ws_config, text, minutes):
    write(ws_config, f'[time]\nday_floor = "{text}"\nidle_minutes = 45\n')

    assert load_time() == TimeConfig(minutes, 45)
    assert load_config().time.day_floor_minutes == minutes


@pytest.mark.parametrize(
    "text",
    ["day_floor = 528", 'day_floor = "soon"', 'day_floor = "0h"', 'day_floor = "25h"',
     'day_floor = "8h75"', 'day_floor = ""', "idle_minutes = 0", "idle_minutes = true",
     'idle_minutes = "30"', "idle_minutes = 1.5"],
)  # fmt: skip
def test_a_bad_time_table_is_refused(ws_config, text):
    write(ws_config, f"[time]\n{text}\n")

    with pytest.raises(ConfigInvalid, match=r"time\."):
        load_time()
    with pytest.raises(ConfigInvalid, match=r"time\."):
        load_config()


def test_time_must_be_a_table(ws_config):
    write(ws_config, "")
    (ws_config / "config.toml").write_text('time = "x"\n' + BASE, encoding="utf-8")

    with pytest.raises(ConfigInvalid, match=r"\[time\] must be a table"):
        load_time()


def test_marking_time_needs_no_config_file(ws_config):
    assert load_time() == TimeConfig()
    with pytest.raises(userconfig.ConfigMissing):
        load_config()
