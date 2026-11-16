"""Move a simulated sensor and print IN A, IN B, or OUTSIDE."""

import argparse
import json
import math
import time
from pathlib import Path


def signed_distance(region, x, y):
    """Distance to the boundary: negative inside, positive outside."""
    cx, cy = region["center"]
    if region["shape"] == "circle":
        return math.hypot(x - cx, y - cy) - region["radius"]
    dx = abs(x - cx) - region["width"] / 2
    dy = abs(y - cy) - region["height"] / 2
    if dx > 0 or dy > 0:
        return math.hypot(max(dx, 0), max(dy, 0))
    return max(dx, dy)


def region_gap(a, b):
    """A positive gap means the regions are separate."""
    if a["shape"] == "circle":
        return signed_distance(b, *a["center"]) - a["radius"]
    if b["shape"] == "circle":
        return signed_distance(a, *b["center"]) - b["radius"]
    dx = abs(a["center"][0] - b["center"][0]) - (a["width"] + b["width"]) / 2
    dy = abs(a["center"][1] - b["center"][1]) - (a["height"] + b["height"]) / 2
    if dx > 0 or dy > 0:
        return math.hypot(max(dx, 0), max(dy, 0))
    return max(dx, dy)


def number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return value


def point(value, name):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{name} must be [x, y]")
    for coordinate in value:
        number(coordinate, name)


def load_config(path):
    with open(path, encoding="utf-8") as file:
        config = json.load(file)
    for name in ("A", "B"):
        region = config["regions"][name]
        point(region["center"], f"{name}.center")
        shape = region["shape"]
        if shape not in ("circle", "rectangle"):
            raise ValueError(f"{name}.shape must be circle or rectangle")
        dimensions = ("radius",) if shape == "circle" else ("width", "height")
        for key in dimensions:
            if number(region[key], f"{name}.{key}") <= 0:
                raise ValueError(f"{name}.{key} must be positive")
    if region_gap(config["regions"]["A"], config["regions"]["B"]) <= 0:
        raise ValueError("regions must not touch or overlap")
    point(config["start"], "start")
    for key in ("average_speed", "duration", "interval", "crossing_threshold"):
        if number(config[key], key) <= 0:
            raise ValueError(f"{key} must be positive")
    for region in config["regions"].values():
        if signed_distance(region, *config["start"]) <= 0:
            raise ValueError("the sensor must start outside both regions")
    return config


class Sensor:
    """Move the sensor and return its distances to the two boundaries."""

    def __init__(self, config):
        self.config = config
        self.time = 0.0
        self.x, self.y = config["start"]

    def advance(self, seconds):
        # Change the speed a little at each step.
        speed = self.config["average_speed"] * (1 + 0.4 * math.sin(self.time))
        self.x += speed * seconds
        # Move up and down too, so the path is in 2D.
        forward = self.x - self.config["start"][0]
        self.y = self.config["start"][1] + math.sin(forward / 2)
        self.time += seconds

    def get_dist_a(self):
        return abs(signed_distance(self.config["regions"]["A"], self.x, self.y))

    def get_dist_b(self):
        return abs(signed_distance(self.config["regions"]["B"], self.x, self.y))


class Classifier:
    """Keep track of the region using only the distance readings."""

    def __init__(self, threshold):
        self.threshold = threshold
        self.state = "OUTSIDE"
        self.previous = {"A": None, "B": None}
        self.closest = {"A": None, "B": None}

    def update(self, dist_a, dist_b):
        for name, distance in (("A", dist_a), ("B", dist_b)):
            previous = self.previous[name]
            closest = self.closest[name]
            if previous is not None:
                if distance < previous:
                    # Keep the smallest distance while getting closer.
                    if closest is None or distance < closest:
                        closest = distance
                elif distance > previous and closest is not None:
                    # Getting farther after coming close may mean a crossing.
                    if closest <= self.threshold:
                        label = f"IN {name}"
                        if self.state == label:
                            self.state = "OUTSIDE"
                        else:
                            self.state = label
                    closest = None
            self.closest[name] = closest
            self.previous[name] = distance
        return self.state


def run(config, fast=False):
    sensor = Sensor(config)
    classifier = Classifier(config["crossing_threshold"])
    start_time = time.monotonic()
    while sensor.time <= config["duration"]:
        dist_a = sensor.get_dist_a()
        dist_b = sensor.get_dist_b()
        state = classifier.update(dist_a, dist_b)
        print(f"t={sensor.time:5.1f}s  position=({sensor.x:6.2f}, {sensor.y:5.2f})  "
              f"distance A={dist_a:5.2f}  B={dist_b:5.2f}  {state}", flush=True)
        sensor.advance(config["interval"])
        if not fast:
            # Wait until the next step is due.
            time.sleep(max(0, start_time + sensor.time - time.monotonic()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(Path(__file__).with_name("config.json")))
    parser.add_argument("--fast", action="store_true", help="skip real-time waits")
    args = parser.parse_args()
    try:
        config = load_config(args.config)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, f"Configuration error: {error}\n")
    try:
        run(config, args.fast)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
