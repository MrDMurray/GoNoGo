from flask import Flask, render_template, request
import csv
import math
import re

app = Flask(__name__)


def load_locations(filename="Locations_onshore_offshore.csv"):
    locations = {}
    with open(filename) as f:
        reader = csv.DictReader(f)
        for row in reader:
            locations[row["Location"]] = {
                "min_angle": float(row["Onshore wind direction min angle"]),
                "max_angle": float(row["Onshore wind direction max angle"]),
            }
    return locations


def parse_ratio(ratio):
    try:
        return int(ratio.split(":")[1])
    except Exception:
        return 1


def load_conditions(filename="Conditions_and_Ratios.csv"):
    conditions = []
    with open(filename) as f:
        reader = csv.DictReader(f)
        for row in reader:
            conditions.append({
                "name": row["Conditions"],
                "wind": row["Winds"],
                "direction": row["Direction"],
                "solo_ratio": parse_ratio(row["Solo Crafe Coach/Leader to Participant ratio"]),
                "crew_ratio": parse_ratio(row["Crew Crafe Coach/Leader to Participant ratio"]),
            })
    return conditions


LOCATIONS = load_locations()
CONDITIONS = load_conditions()


def is_onshore(min_angle, max_angle, wind_direction):
    if min_angle <= max_angle:
        return min_angle <= wind_direction <= max_angle
    return wind_direction >= min_angle or wind_direction <= max_angle


def wind_match(limit_str, speed_kmh):
    s = limit_str.lower()
    if s == "any":
        return True
    m = re.match(r"([<>])\s*(\d+)", s)
    if not m:
        return False
    op, val = m.groups()
    val = float(val)
    if op == "<":
        return speed_kmh < val
    return speed_kmh > val


def choose_condition(onshore, speed_kmh):
    for c in CONDITIONS:
        if c["direction"].lower() == "onshore" and not onshore:
            continue
        if wind_match(c["wind"], speed_kmh):
            return c
    return CONDITIONS[-1]


def check_guidelines(location, wind_speed_ms, wind_direction_deg,
                      solo_participants, crew_participants,
                      senior_instructors, assistant_instructors):
    reasons = []
    loc = LOCATIONS[location]
    onshore = is_onshore(loc["min_angle"], loc["max_angle"], wind_direction_deg)
    speed_kmh = wind_speed_ms * 3.6

    cond = choose_condition(onshore, speed_kmh)

    required_solo = math.ceil(solo_participants / cond["solo_ratio"])
    required_crew = math.ceil(crew_participants / cond["crew_ratio"])
    required = max(required_solo, required_crew)

    total_instructors = senior_instructors + assistant_instructors

    if total_instructors < required:
        reasons.append(
            f"Need at least {required} instructors for {solo_participants + crew_participants} participants.")

    if cond["direction"].lower() == "onshore" and not onshore:
        reasons.append("Wind direction is offshore for this condition.")

    if not wind_match(cond["wind"], speed_kmh):
        if cond["wind"].startswith("<"):
            limit = cond["wind"][1:]
            reasons.append(f"Wind speed exceeds {limit}")
        elif cond["wind"].startswith(">"):
            limit = cond["wind"][1:]
            reasons.append(f"Wind speed below required >{limit}")

    decision = "GO" if not reasons else "NO GO"
    return decision, reasons, cond["name"]


@app.route('/', methods=['GET', 'POST'])
def index():
    decision = None
    decision_class = ''
    reasons = []
    condition_name = None

    if request.method == 'POST':
        loc = request.form.get('location')
        wind_speed = float(request.form.get('wind_speed', 0))
        wind_direction = float(request.form.get('wind_direction', 0))
        solo_participants = int(request.form.get('solo_participants', 0))
        crew_participants = int(request.form.get('crew_participants', 0))
        senior_instructors = int(request.form.get('senior_instructors', 0))
        assistant_instructors = int(request.form.get('assistant_instructors', 0))

        decision, reasons, condition_name = check_guidelines(
            loc, wind_speed, wind_direction,
            solo_participants, crew_participants,
            senior_instructors, assistant_instructors)

        decision_class = 'status-go' if decision == 'GO' else 'status-nogo'

    return render_template(
        'index.html',
        locations=LOCATIONS.keys(),
        decision=decision,
        decision_class=decision_class,
        reasons=reasons,
        condition_name=condition_name)


if __name__ == '__main__':
    app.run(debug=True, port=5004)
