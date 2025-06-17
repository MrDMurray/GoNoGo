from flask import Flask, render_template, request

app = Flask(__name__)

# Simplified location data with orientation (direction the shore faces)
LOCATIONS = {
    "Skerries Sailing Club": {"orientation": 270},  # west facing
    "Howth Harbour": {"orientation": 90},          # east facing
    "Dun Laoghaire": {"orientation": 120}          # south-east facing
}


def is_onshore(orientation, wind_direction):
    """Return True if wind is onshore for the given orientation."""
    diff = (wind_direction - orientation) % 360
    return diff <= 90 or diff >= 270


def check_guidelines(location, wind_speed, wind_direction,
                      novice_students, experienced_students,
                      senior_instructors, assistant_instructors):
    reasons = []
    orientation = LOCATIONS[location]["orientation"]
    onshore = is_onshore(orientation, wind_direction)

    # Wind limits (dummy values as actual PDF not available)
    if onshore:
        if novice_students > 0 and wind_speed > 8:
            reasons.append("Onshore wind speed too high for novices.")
        if experienced_students > 0 and wind_speed > 10:
            reasons.append("Onshore wind speed too high for experienced paddlers.")
    else:  # offshore
        if novice_students > 0 and wind_speed > 12:
            reasons.append("Offshore wind speed too high for novices.")
        if experienced_students > 0 and wind_speed > 14:
            reasons.append("Offshore wind speed too high for experienced paddlers.")

    # Instructor ratios (dummy values)
    required_for_novice = (novice_students + 5) // 6
    required_for_experienced = (experienced_students + 7) // 8
    required_instructors = max(required_for_novice, required_for_experienced)

    total_instructors = senior_instructors + assistant_instructors

    if total_instructors < required_instructors:
        reasons.append(
            f"Need at least {required_instructors} instructors for {novice_students + experienced_students} students.")

    if novice_students > 0 and senior_instructors < 1:
        reasons.append("At least one senior instructor required for novice students.")

    if reasons:
        return "NO GO", reasons
    return "GO", ["Conditions meet guidelines."]


@app.route('/', methods=['GET', 'POST'])
def index():
    decision = None
    decision_class = ''
    reasons = []

    if request.method == 'POST':
        loc = request.form.get('location')
        wind_speed = float(request.form.get('wind_speed', 0))
        wind_direction = float(request.form.get('wind_direction', 0))
        novice_students = int(request.form.get('novice_students', 0))
        experienced_students = int(request.form.get('experienced_students', 0))
        senior_instructors = int(request.form.get('senior_instructors', 0))
        assistant_instructors = int(request.form.get('assistant_instructors', 0))

        decision, reasons = check_guidelines(
            loc, wind_speed, wind_direction,
            novice_students, experienced_students,
            senior_instructors, assistant_instructors)

        decision_class = 'status-go' if decision == 'GO' else 'status-nogo'

    return render_template(
        'index.html',
        locations=LOCATIONS.keys(),
        decision=decision,
        decision_class=decision_class,
        reasons=reasons)


if __name__ == '__main__':
    app.run(debug=True, port=5004)