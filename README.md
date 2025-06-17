# GoNoGo

A simple Flask application that helps water sport instructors evaluate whether conditions and supervision ratios meet safety guidelines.

## Usage
1. Install dependencies:
   ```bash
   pip install flask
   ```
2. Run the application:
   ```bash
   python app.py
   ```
3. Open a browser to `http://localhost:5000` and fill in the form.

## About
The form allows you to choose a location, enter wind details and participant numbers. The application reads `Locations_onshore_offshore.csv` to determine when the wind is onshore for a location and `Conditions_and_Ratios.csv` for the wind limits and instructor ratios. The result is displayed as `GO` or `NO GO` with the reason and the matched condition category from the CSV data.
