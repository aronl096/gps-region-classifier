import copy
import json
import math
from pathlib import Path

import pytest

from tracker import Classifier, Sensor, load_config, run, signed_distance

CONFIG = Path(__file__).parents[1] / "config.json"


@pytest.mark.parametrize("shape, point, expected", [
    ({"shape": "circle", "center": [0, 0], "radius": 2}, (0, 0), -2),
    ({"shape": "circle", "center": [0, 0], "radius": 2}, (2, 0), 0),
    ({"shape": "circle", "center": [0, 0], "radius": 2}, (3, 0), 1),
    ({"shape": "rectangle", "center": [0, 0], "width": 4, "height": 2}, (0, 0), -1),
    ({"shape": "rectangle", "center": [0, 0], "width": 4, "height": 2}, (3, 2), math.sqrt(2)),
])
def test_distances(shape, point, expected):
    assert signed_distance(shape, *point) == pytest.approx(expected)


def test_classifier_enters_and_leaves_using_only_numbers():
    classifier = Classifier(0.1)
    readings = [1, 0.5, 0.05, 0.2, 0.5, 0.05, 0.2]
    assert [classifier.update(d, 10) for d in readings] == [
        "OUTSIDE", "OUTSIDE", "OUTSIDE", "IN A", "IN A", "IN A", "OUTSIDE",
    ]


def test_stopping_near_boundary_waits_until_moving_away():
    classifier = Classifier(0.1)
    for distance in (1, 0.05, 0.05, 0.05):
        assert classifier.update(distance, 10) == "OUTSIDE"
    assert classifier.update(0.2, 10) == "IN A"


def test_passing_near_region_without_entering():
    classifier = Classifier(0.1)
    for distance in (1, 0.5, 0.2, 0.5, 1):
        assert classifier.update(distance, 10) == "OUTSIDE"


def test_known_limitation_turning_back_close_looks_like_entry():
    classifier = Classifier(0.1)
    # These readings could come from turning back 5 cm before the boundary.
    for distance in (1, 0.5, 0.05, 0.5):
        state = classifier.update(distance, 10)
    assert state == "IN A"  # A documented false entry.


def test_unsigned_distances_can_be_ambiguous():
    a = {"shape": "circle", "center": [0, 0], "radius": 1}
    b = {"shape": "circle", "center": [4, 0], "radius": 1}
    inside = (0.5, 0)
    outside = (0.75, math.sqrt(27) / 4)
    assert signed_distance(a, *inside) < 0 < signed_distance(a, *outside)
    for region in (a, b):
        assert abs(signed_distance(region, *inside)) == pytest.approx(abs(signed_distance(region, *outside)))


def test_motion_changes_speed_and_moves_in_both_axes():
    sensor = Sensor(load_config(CONFIG))
    positions = []
    steps = []
    for _ in range(40):
        old_x = sensor.x
        sensor.advance(0.1)
        steps.append(sensor.x - old_x)
        positions.append(sensor.y)
    assert max(steps) - min(steps) > 0.05
    assert max(positions) - min(positions) > 0.5
    sensor = Sensor(load_config(CONFIG))
    # Check the average over one full speed cycle, using small steps.
    for _ in range(100):
        sensor.advance(2 * math.pi / 100)
    assert (sensor.x + 5) / sensor.time == pytest.approx(1.2)


def test_default_trip_visits_both_regions_and_tracks_with_short_delay():
    config = load_config(CONFIG)
    sensor = Sensor(config)
    classifier = Classifier(config["crossing_threshold"])
    predictions, truths = [], []
    while sensor.time <= config["duration"]:
        predicted = classifier.update(sensor.get_dist_a(), sensor.get_dist_b())
        truth = "OUTSIDE"
        for name, region in config["regions"].items():
            if signed_distance(region, sensor.x, sensor.y) <= 0:
                truth = f"IN {name}"
        if not predictions or predictions[-1][1] != predicted:
            predictions.append((sensor.time, predicted))
        if not truths or truths[-1][1] != truth:
            truths.append((sensor.time, truth))
        sensor.advance(config["interval"])
    assert [label for _, label in truths] == ["OUTSIDE", "IN A", "OUTSIDE", "IN B", "OUTSIDE"]
    assert [label for _, label in predictions] == [label for _, label in truths]
    for (predicted_time, _), (true_time, _) in zip(predictions, truths):
        assert -1e-9 <= predicted_time - true_time <= 2 * config["interval"] + 1e-9


@pytest.mark.parametrize("key, value", [("interval", 0), ("duration", -1), ("average_speed", "fast"),
                                         ("start", [float("inf"), 0]), ("start", [0, 0])])
def test_bad_settings_are_rejected(tmp_path, key, value):
    config = copy.deepcopy(load_config(CONFIG))
    config[key] = value
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError):
        load_config(path)


def test_overlapping_regions_are_rejected(tmp_path):
    config = load_config(CONFIG)
    config["regions"]["B"]["center"] = [0, 0]
    path = tmp_path / "overlap.json"
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match="overlap"):
        load_config(path)


def test_terminal_prints_live_results_without_sleep_in_fast_mode(capsys):
    config = load_config(CONFIG)
    run(config, fast=True)
    output = capsys.readouterr().out
    assert "IN A" in output and "IN B" in output and "OUTSIDE" in output
    assert "position=" in output and "distance A=" in output
