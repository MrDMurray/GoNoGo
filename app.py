from flask import Flask, render_template, request
import csv
import math

app = Flask(__name__)


# ------------------------------
# Data loading helpers
# ------------------------------

def load_locations(path="Locations_onshore_offshore.csv"):
    """Return a dict mapping location names to onshore wind angle ranges."""
    locations = {}
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            locations[row["Location"]] = {
                "min": float(row["Onshore wind direction min angle"]),
                "max": float(row["Onshore wind direction max angle"]),
            }
    return locations


def parse_wind_limit(value):
    """Parse a wind limit like '<19km/h' into (op, float(km/h))."""
    value = value.strip().lower().replace("km/h", "")
    if value.startswith("<"):
        return "<", float(value[1:])
    if value.startswith(">"):
        return ">", float(value[1:])
    raise ValueError(f"Unrecognised wind limit: {value}")


def parse_ratio(value):
    """Parse a ratio string like '1:8' into the numeric participant count."""
    return float(value.split(":", 1)[1])


def load_conditions(path="Conditions_and_Ratios.csv"):
    """Return a dict keyed by condition name with limits and ratios."""
    conditions = {}
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            op, wind_val = parse_wind_limit(row["Winds"])
            distance_raw = row["Distance from Shore (m)"].strip()
            distance = None if distance_raw.lower() == "any" else float(distance_raw)
            conditions[row["Conditions"]] = {
                "wind_op": op,
                "wind_val": wind_val,
                "direction": row["Direction"],
                "distance": distance,
                "ratio_solo": parse_ratio(row["Solo Crafe Coach/Leader to Participant ratio"]),
                "ratio_crew": parse_ratio(row["Crew Crafe Coach/Leader to Participant ratio"]),
                "qualifications": row["Suggested Minimum Qualifications"],
            }
    return conditions


LOCATIONS = load_locations()
CONDITIONS = load_conditions()


# ------------------------------
# Utility functions
# ------------------------------

def is_onshore(range_min, range_max, direction):
    """Return True if direction falls within the onshore range."""
    range_min %= 360
    range_max %= 360
    direction %= 360
    if range_min <= range_max:
        return range_min <= direction <= range_max
    return direction >= range_min or direction <= range_max


def evaluate(location, environment, distance, wind_speed, wind_dir,
             solo_participants, crew_participants, coaches):
    """Return (GO/NO GO, reasons list) based on CSV guidance."""
    reasons = []

    loc = LOCATIONS[location]
    env = CONDITIONS[environment]

    # Wind direction check
    onshore = is_onshore(loc["min"], loc["max"], wind_dir)
    if env["direction"].lower() == "onshore" and not onshore:
        reasons.append("Wind direction is not onshore as required.")

    # Wind speed check
    if env["wind_op"] == "<" and not wind_speed < env["wind_val"]:
        reasons.append(f"Wind speed must be less than {env['wind_val']} km/h.")
    if env["wind_op"] == ">" and not wind_speed > env["wind_val"]:
        reasons.append(f"Wind speed must be greater than {env['wind_val']} km/h.")

    # Distance check
    if env["distance"] is not None and distance > env["distance"]:
        reasons.append(
            f"Distance from shore exceeds allowed {env['distance']} m for this environment.")

    # Ratio check
    required_solo = math.ceil(solo_participants / env["ratio_solo"])
    required_crew = math.ceil(crew_participants / env["ratio_crew"])
    required_total = required_solo + required_crew
    if coaches < required_total:
        reasons.append(
            f"Need at least {required_total} qualified coaches/leaders (solo {env['ratio_solo']} and crew {env['ratio_crew']} ratios).")
        reasons.append(f"Suggested minimum qualifications: {env['qualifications']}")

    if reasons:
        return "NO GO", reasons
    return "GO", ["Conditions meet guidelines."]


# ------------------------------
# Routes
# ------------------------------

@app.route('/', methods=['GET', 'POST'])
def index():
    decision = None
    decision_class = ''
    reasons = []

    if request.method == 'POST':
        loc = request.form.get('location')
        env = request.form.get('environment')
        distance = float(request.form.get('distance', 0))
        wind_speed = float(request.form.get('wind_speed', 0))
        wind_direction = float(request.form.get('wind_direction', 0))
        solo_participants = int(request.form.get('solo_participants', 0))
        crew_participants = int(request.form.get('crew_participants', 0))
        coaches = int(request.form.get('coaches', 0))

        decision, reasons = evaluate(
            loc, env, distance, wind_speed, wind_direction,
            solo_participants, crew_participants, coaches)
        decision_class = 'status-go' if decision == 'GO' else 'status-nogo'

    return render_template(
        'index.html',
        locations=LOCATIONS.keys(),
        environments=CONDITIONS.keys(),
        decision=decision,
        decision_class=decision_class,
        reasons=reasons)


if __name__ == '__main__':
    app.run(debug=True, port=5004)
