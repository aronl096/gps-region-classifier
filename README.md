# GPS Region Classifier

A small Python program that simulates a GPS sensor in 2D and prints **IN A**, **IN B**,
or **OUTSIDE**. The speed changes during the run. No graphics or extra packages
are needed to run it.

## Run

Requires Python 3.8 or newer. From the project folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
python tracker.py
```

The demo takes about 16 seconds. Use `--fast` to skip waiting, or Ctrl+C to stop.

## Settings

Edit `config.json` to change the region shapes and sizes. A circle uses `center`
and `radius`; a rectangle uses `center`, `width`, and `height`.
The regions must not touch or overlap.

The file also sets the starting point, average forward speed, duration, time
between readings, and crossing threshold. Distances are in meters; time is in seconds.
To use another file: `python tracker.py --config other.json`.

## Approach

`get_dist_a()` and `get_dist_b()` return distances without a sign and take no
arguments. The classifier compares each reading with the previous one. If the
distance decreases, gets close to zero, and then increases, it counts a likely
crossing and switches the remembered region. It prints the result at each step.
The position is shown in the output but is not given to the classifier.

The sensor must start outside both regions. This method can mistake turning back
near a boundary for crossing it. Fast movement can also skip a crossing between
readings. A wrong state may persist, and detection can be delayed. The simulation
uses exact distances; it does not handle sensor noise.

## Tests

With the virtual environment active, install the test dependency and run the tests:

```bash
pip install -r requirements-dev.txt
pytest -q
```
