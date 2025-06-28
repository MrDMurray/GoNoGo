from flask import Flask, render_template, request, jsonify
import csv
import math
import requests

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


def parse_qual_levels(qual_str):
    """Return a set of coach levels mentioned in the qualification string."""
    qual_str = qual_str.lower()
    levels = set()
    if "level 1" in qual_str:
        levels.add(1)
    if "level 3" in qual_str:
        levels.add(3)
    return levels


def load_conditions(path="Conditions_and_Ratios.csv"):
    """Return a dict keyed by condition name with limits and ratios."""
    conditions = {}
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            op, wind_val = parse_wind_limit(row["Winds"])
            distance_raw = row["Distance from Shore (m)"].strip()
            distance = None if distance_raw.lower() == "any" else float(distance_raw)
            qualifications = row.get("Coach Minimum Qualifications", row.get("Suggested Minimum Qualifications", ""))
            conditions[row["Conditions"]] = {
                "definition": row["Definition"],
                "wind_op": op,
                "wind_val": wind_val,
                "direction": row["Direction"],
                "distance": distance,
                "ratio_solo": parse_ratio(row["Solo Crafe Coach/Leader to Participant ratio"]),
                "ratio_crew": parse_ratio(row["Crew Crafe Coach/Leader to Participant ratio"]),
                "qualifications": qualifications,
                "qual_levels": parse_qual_levels(qualifications),
            }
    return conditions


LOCATIONS = load_locations()
CONDITIONS = load_conditions()

def load_tides(path="static/SkerriesTides.csv"):
    """Return list of {'location','dtg','type'} dicts for tide predictions."""
    tides = []
    try:
        with open(path, newline="") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 3:
                    continue
                tides.append({"location": row[0], "dtg": row[1], "type": row[2]})
    except FileNotFoundError:
        pass
    return tides

TIDES = load_tides()


# ------------------------------
# External data fetch
# ------------------------------

def fetch_latest_wind_data():
    """Return (speed_kmh, direction_deg) from Dublin Airport or (None, None)."""
    url = "https://www.met.ie/Open_Data/json/dublin_airport.json"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        stations = data.get("stations", [])
        if not stations:
            return None, None
        station = stations[0]
        time_items = station.get("timeseries", {}).get("timeItems", [])
        if not time_items:
            return None, None
        latest = time_items[-1]
        params = latest.get("weatherparameters", [])
        wind_speed = None
        wind_direction = None
        for param in params:
            if "Wind speed [m/s]" in param:
                wind_speed = param["Wind speed [m/s]"]
            if "Wind direction [deg]" in param:
                wind_direction = param["Wind direction [deg]"]
        if wind_speed is not None:
            wind_speed = round(wind_speed * 3.6, 1)
        return wind_speed, wind_direction
    except Exception:
        return None, None


def fetch_forecast_data():
    """Return list of {'dtg', 'speed', 'direction', 'temperature'} dicts from Dublin Airport."""
    url = "https://www.met.ie/Open_Data/json/dublin_airport.json"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("stations", [{}])[0].get("timeseries", {}).get("timeItems", [])
        forecast = []
        for it in items:
            params = it.get("weatherparameters", [])
            wind_speed = None
            wind_dir = None
            temp = None
            for p in params:
                if "Wind speed [m/s]" in p:
                    wind_speed = round(p["Wind speed [m/s]"] * 3.6, 1)
                if "Wind direction [deg]" in p:
                    wind_dir = p["Wind direction [deg]"]
                if "Temperature [C]" in p:
                    temp = p["Temperature [C]"]
            if wind_speed is not None and wind_dir is not None:
                entry = {"dtg": it.get("dtg"), "speed": wind_speed, "direction": wind_dir}
                if temp is not None:
                    entry["temperature"] = temp
                forecast.append(entry)
        return forecast
    except Exception:
        return []

def fetch_water_quality_status(beach_name="Skerries, South Beach"):
    """Return latest sample_water_quality_status string or None."""
    base_url = "https://data.epa.ie/bw/api/v1/measurements?page={}"
    # The API does not appear to provide direct filtering, so scan
    # recent pages starting from the end (approx 454 as of 2025).
    for page in range(454, 439, -1):
        try:
            resp = requests.get(base_url.format(page), timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            continue
        for rec in data.get("list", []):
            if rec.get("beach_name") == beach_name:
                return rec.get("sample_water_quality_status")
    return None


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
             solo_participants, crew_participants, level1_coaches, level3_coaches):
    """Return (GO/NO GO, reasons list) based on CSV guidance."""
    reasons = []

    loc = LOCATIONS[location]
    env = CONDITIONS[environment]

    # Wind direction check
    onshore = is_onshore(loc["min"], loc["max"], wind_dir)
    if env["direction"].lower() == "onshore" and not onshore:
        reasons.append("Wind direction is not onshore as required. Try the South Beach?")
        if wind_speed < 11:
            reasons.append("<em>(Special Case: Wind speed is Force 2 or less in Dublin Airport so maybe negligible on site)</em>")

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

    if env["qual_levels"] == {3}:
        if level3_coaches < 1:
            reasons.append("At least one Level 3 coach is required for this environment.")
        available = level3_coaches + level1_coaches
    else:
        # Level 3 coaches are considered qualified for Level 1 environments
        available = level1_coaches + level3_coaches

    if available < required_total:
        reasons.append(
            f"Need at least {required_total} qualified coaches/leaders (solo {env['ratio_solo']} and crew {env['ratio_crew']} ratios).")
        reasons.append(f"Suggested minimum qualifications: {env['qualifications']}")

    if reasons:
        return "NO GO", reasons
    return "GO", ["Conditions meet guidelines."]


# ------------------------------
# Routes
# ------------------------------

def render_activity(template, autosubmit=True):
    decision = None
    decision_class = ''
    reasons = []

    # Default values for the form fields
    form_data = {
        'location': next(iter(LOCATIONS.keys())),
        'environment': next(iter(CONDITIONS.keys())),
        'distance': 50,
        'wind_speed': '',
        'wind_direction': '',
        'solo_participants': 6,
        'crew_participants': 0,
        'level1_coaches': 1,
        'level3_coaches': 0,
    }

    if request.method == 'POST':
        # Preserve submitted values
        form_data['location'] = request.form.get('location', form_data['location'])
        form_data['environment'] = request.form.get('environment', form_data['environment'])
        form_data['distance'] = request.form.get('distance', form_data['distance'])
        form_data['wind_speed'] = request.form.get('wind_speed', form_data['wind_speed'])
        form_data['wind_direction'] = request.form.get('wind_direction', form_data['wind_direction'])
        form_data['solo_participants'] = request.form.get('solo_participants', form_data['solo_participants'])
        form_data['crew_participants'] = request.form.get('crew_participants', form_data['crew_participants'])
        form_data['level1_coaches'] = request.form.get('level1_coaches', form_data['level1_coaches'])
        form_data['level3_coaches'] = request.form.get('level3_coaches', form_data['level3_coaches'])

        decision, reasons = evaluate(
            form_data['location'],
            form_data['environment'],
            float(form_data['distance'] or 0),
            float(form_data['wind_speed'] or 0),
            float(form_data['wind_direction'] or 0),
            int(form_data['solo_participants'] or 0),
            int(form_data['crew_participants'] or 0),
            int(form_data['level1_coaches'] or 0),
            int(form_data['level3_coaches'] or 0))
        decision_class = 'status-go' if decision == 'GO' else 'status-nogo'

    return render_template(
        template,
        locations=LOCATIONS.keys(),
        environments=CONDITIONS.keys(),
        env_definitions={name: data['definition'] for name, data in CONDITIONS.items()},
        decision=decision,
        decision_class=decision_class,
        reasons=reasons,
        form_data=form_data,
        autosubmit=autosubmit)


@app.route('/', methods=['GET', 'POST'])
def index():
    return render_activity('index.html', autosubmit=False)


@app.route('/paddle', methods=['GET', 'POST'])
def paddle():
    return render_activity('paddle.html')


@app.route('/swim', methods=['GET', 'POST'])
def swim():
    return render_activity('swim.html')


@app.route('/row', methods=['GET', 'POST'])
def row_page():  # avoid conflict with row function maybe
    return render_activity('row.html')


@app.route('/sail', methods=['GET', 'POST'])
def sail():
    return render_activity('sail.html')


@app.route('/wind')
def wind():
    """Return latest wind data from Dublin Airport as JSON."""
    speed, direction = fetch_latest_wind_data()
    if speed is None or direction is None:
        return jsonify({'error': 'Failed to fetch data'}), 500
    return jsonify({'speed': speed, 'direction': direction})


@app.route('/forecast')
def forecast():
    """Return hourly forecast data as JSON."""
    data = fetch_forecast_data()
    if not data:
        return jsonify({'error': 'Failed to fetch data'}), 500
    return jsonify(data)


@app.route('/tides')
def tides():
    """Return tide prediction data as JSON."""
    return jsonify(TIDES)


@app.route('/water_quality')
def water_quality():
    """Return latest water quality status for Skerries, South Beach."""
    status = fetch_water_quality_status()
    if not status:
        return jsonify({'error': 'Failed to fetch data'}), 500
    return jsonify({'status': status})


if __name__ == '__main__':
    app.run(debug=True, port=5005)
