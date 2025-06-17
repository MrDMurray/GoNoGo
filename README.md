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
The form allows you to choose a location, specify wind information and list numbers of students and instructors. The app then displays `GO` or `NO GO` with reasons based on basic rules for wind limits and instructor ratios. The rules are illustrative only – replace them with the official guidance from your "Guidance For Instructors" PDF.
