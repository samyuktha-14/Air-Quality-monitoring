import os
from flask import Flask, jsonify, request, render_template, session, redirect, url_for, flash
import mysql.connector
from dotenv import load_dotenv
from datetime import datetime
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-very-secret-key-change-this-in-env')

# Login Required Decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json:
                return jsonify({'error': 'Unauthorized. Please login.'}), 401
            return redirect(url_for('login_page', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def get_db_connection():
    url = os.getenv('MYSQL_URL')
    if url:
        # Parse the connection URL: mysql://user:pass@host:port/db
        try:
            # Remove the protocol
            if '://' in url:
                url = url.split('://')[1]
            
            # Split auth and host/db
            auth, rest = url.split('@')
            user, password = auth.split(':')
            
            # Split host:port and db
            host_port, db_name = rest.split('/')
            if ':' in host_port:
                host, port = host_port.split(':')
            else:
                host, port = host_port, 3306
                
            return mysql.connector.connect(
                host=host,
                user=user,
                password=password,
                database=db_name,
                port=int(port)
            )
        except Exception as e:
            print(f"Error parsing MYSQL_URL: {e}")

    return mysql.connector.connect(
        host=os.getenv('DB_HOST', os.getenv('MYSQLHOST', 'localhost')),
        user=os.getenv('DB_USER', os.getenv('MYSQLUSER', 'root')),
        password=os.getenv('DB_PASS', os.getenv('MYSQLPASSWORD', '')),
        database=os.getenv('DB_NAME', os.getenv('MYSQLDATABASE', 'aqi_db')),
        port=int(os.getenv('DB_PORT', os.getenv('MYSQLPORT', 3306)))
    )

@app.route('/')
def dashboard():
    return render_template('index.html')

@app.route('/add_data')
@login_required
def add_data():
    return render_template('add_data.html')

@app.route('/login')
def login_page():
    if 'user_id' in session:
        return redirect(url_for('add_data'))
    return render_template('login.html')

@app.route('/api/login', methods=['POST'])
def login():
    data = request.form
    username = data.get('username')
    password = data.get('password')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['user_id']
            session['username'] = user['username']
            session['role'] = user['role']
            flash(f"Welcome back, {user['username']}!", "success")
            return redirect(url_for('add_data'))
        else:
            return render_template('login.html', error="Invalid username or password")
    finally:
        cursor.close()
        conn.close()

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('dashboard'))

@app.route('/reports')
def reports():
    return render_template('reports.html')

@app.route('/queries')
def query_page():
    return render_template('queries.html')

# API Endpoints

@app.route('/api/metadata', methods=['GET'])
def get_metadata():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM city")
        cities = cursor.fetchall()
        
        cursor.execute("SELECT * FROM monitoring_station")
        stations = cursor.fetchall()
        
        cursor.execute("SELECT * FROM pollutant")
        pollutants = cursor.fetchall()
        
        return jsonify({
            'cities': cities,
            'stations': stations,
            'pollutants': pollutants
        })
    finally:
        cursor.close()
        conn.close()

@app.route('/api/measurements', methods=['POST'])
@login_required
def add_measurement():
    data = request.json
    station_id = data.get('station_id')
    measured_at_str = data.get('measured_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    pollutant_data = data.get('pollutants', {})

    # Backend Validation: Prevent past/future dates
    try:
        measured_at_dt = datetime.strptime(measured_at_str, '%Y-%m-%d %H:%M:%S')
        now = datetime.now()
        diff = abs((now - measured_at_dt).total_seconds())
        # Buffer of 5 minutes (300 seconds) for clock drift
        if diff > 300:
            return jsonify({'error': 'Data can only be entered for the current time. Past or future entries are blocked.'}), 400
    except ValueError:
        return jsonify({'error': 'Invalid date format'}), 400

    if not station_id or not pollutant_data:
        return jsonify({'error': 'Missing required fields (station_id or pollutants)'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        inserted_count = 0
        for p_id, val in pollutant_data.items():
            if val is not None and str(val).strip() != "":
                # Basic validation
                if float(val) < 0:
                    continue # Skip negative values
                
                query = """
                    INSERT INTO measurement (station_id, pollutant_id, measured_at, measured_value) 
                    VALUES (%s, %s, %s, %s)
                """
                cursor.execute(query, (station_id, p_id, measured_at_str, val))
                inserted_count += 1
        
        if inserted_count == 0:
            return jsonify({'error': 'No valid measurements provided'}), 400

        conn.commit()
        return jsonify({'message': f'Successfully added {inserted_count} measurement(s)'}), 201
    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/dashboard_stats', methods=['GET'])
def dashboard_stats():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        today = datetime.now().date()
        
        # Average AQI across all stations for TODAY according to system time
        cursor.execute("""
            SELECT AVG(final_aqi) as avg_aqi 
            FROM aqi_result 
            WHERE measured_date = %s
        """, (today,))
        avg_aqi = cursor.fetchone()['avg_aqi']
        
        # Total Monitoring Stations
        cursor.execute("SELECT COUNT(*) as total_stations FROM monitoring_station")
        total_stations = cursor.fetchone()['total_stations']

        # Most Polluted City TODAY according to system time
        cursor.execute("""
            SELECT c.city_name, MAX(a.final_aqi) as max_aqi
            FROM aqi_result a
            JOIN monitoring_station s ON a.station_id = s.station_id
            JOIN city c ON s.city_id = c.city_id
            WHERE a.measured_date = %s
            GROUP BY c.city_name
            ORDER BY max_aqi DESC LIMIT 1
        """, (today,))
        most_polluted = cursor.fetchone()
        
        return jsonify({
            'average_aqi': round(float(avg_aqi)) if avg_aqi else 0,
            'total_stations': total_stations,
            'most_polluted_city': most_polluted['city_name'] if most_polluted else 'N/A'
        })
    finally:
        cursor.close()
        conn.close()

@app.route('/api/aqi_results', methods=['GET'])
def aqi_results():
    city_id = request.args.get('city_id')
    date = request.args.get('date')
    
    query = """
        SELECT a.measured_date, a.final_aqi, a.category, a.dominant_pollutant, s.station_name, c.city_name
        FROM aqi_result a
        JOIN monitoring_station s ON a.station_id = s.station_id
        JOIN city c ON s.city_id = c.city_id
        WHERE 1=1
    """
    params = []
    if city_id:
        query += " AND c.city_id = %s"
        params.append(city_id)
    if date:
        query += " AND a.measured_date = %s"
        params.append(date)
        
    query += " ORDER BY a.measured_date DESC, a.final_aqi DESC"
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(query, params)
        results = cursor.fetchall()
        # format date
        for row in results:
            if row['measured_date']:
                row['measured_date'] = row['measured_date'].strftime('%Y-%m-%d')
        return jsonify(results)
    finally:
        cursor.close()
        conn.close()

@app.route('/api/reports/city_trends', methods=['GET'])
def city_trends():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        query = """
            SELECT c.city_name, a.measured_date, AVG(a.final_aqi) as avg_aqi
            FROM aqi_result a
            JOIN monitoring_station s ON a.station_id = s.station_id
            JOIN city c ON s.city_id = c.city_id
            GROUP BY c.city_name, a.measured_date
            ORDER BY a.measured_date ASC
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        
        # Structure data for charts
        data = {}
        for row in rows:
            city = row['city_name']
            date = row['measured_date'].strftime('%Y-%m-%d')
            aqi = float(row['avg_aqi'])
            if city not in data:
                data[city] = {'dates': [], 'aqi': []}
            data[city]['dates'].append(date)
            data[city]['aqi'].append(aqi)
            
        return jsonify(data)
    finally:
        cursor.close()
        conn.close()

@app.route('/api/reports/hotspots', methods=['GET'])
def hotspots():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        query = """
            SELECT s.station_name, c.city_name, AVG(a.final_aqi) as avg_aqi
            FROM aqi_result a
            JOIN monitoring_station s ON a.station_id = s.station_id
            JOIN city c ON s.city_id = c.city_id
            GROUP BY s.station_name, c.city_name
            ORDER BY avg_aqi DESC
            LIMIT 5
        """
        cursor.execute(query)
        results = cursor.fetchall()
        for row in results:
            row['avg_aqi'] = round(float(row['avg_aqi']))
        return jsonify(results)
    finally:
        cursor.close()
        conn.close()

@app.route('/api/custom_query', methods=['GET'])
def custom_query():
    query_type = request.args.get('type')
    city_id = request.args.get('city_id')
    station_id = request.args.get('station_id')
    date = request.args.get('date')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        if (query_type == 'city_avg'):
            # First, get city name for display
            cursor.execute("SELECT city_name FROM city WHERE city_id = %s", (city_id,))
            city_row = cursor.fetchone()
            sub = city_row['city_name'] if city_row else "Unknown City"

            cursor.execute("""
                SELECT AVG(a.final_aqi) as result
                FROM aqi_result a
                JOIN monitoring_station s ON a.station_id = s.station_id
                WHERE s.city_id = %s AND a.measured_date = (
                    SELECT MAX(measured_date) 
                    FROM aqi_result a2
                    JOIN monitoring_station s2 ON a2.station_id = s2.station_id
                    WHERE s2.city_id = %s
                )
            """, (city_id, city_id))
            data = cursor.fetchone()
            val = round(float(data['result'])) if data and data['result'] is not None else 0
            return jsonify({'type': 'summary', 'label': f"Current Average AQI for {sub}", 'value': val})

        elif query_type == 'daily_avg':
            cursor.execute("SELECT AVG(final_aqi) as result FROM aqi_result WHERE measured_date = %s", (date,))
            data = cursor.fetchone()
            return jsonify({'type': 'summary', 'label': f"National Average on {date}", 'value': round(float(data['result'])) if data['result'] else 0})

        elif query_type == 'detailed_logs':
            cursor.execute("""
                SELECT m.measured_at, p.pollutant_name, m.measured_value, p.unit
                FROM measurement m
                JOIN pollutant p ON m.pollutant_id = p.pollutant_id
                WHERE m.station_id = %s AND DATE(m.measured_at) = %s
                ORDER BY m.measured_at DESC
            """, (station_id, date))
            rows = cursor.fetchall()
            for r in rows: r['measured_at'] = r['measured_at'].strftime('%Y-%m-%d %H:%M:%S')
            return jsonify({'type': 'table', 'data': rows, 'headers': ['Timestamp', 'Pollutant', 'Value', 'Unit']})

        elif query_type == 'daily_peak':
            today = datetime.now().date()
            cursor.execute("""
                SELECT c.city_name, ROUND(AVG(a.final_aqi)) as avg_aqi
                FROM aqi_result a
                JOIN monitoring_station s ON a.station_id = s.station_id
                JOIN city c ON s.city_id = c.city_id
                WHERE a.measured_date = %s
                GROUP BY c.city_name
                ORDER BY avg_aqi DESC
            """, (today,))
            rows = cursor.fetchall()
            return jsonify({'type': 'table', 'data': rows, 'headers': ['City Name', 'Average AQI Today']})

        elif query_type == 'dominant_stats':
            cursor.execute("""
                SELECT dominant_pollutant as label, COUNT(*) as value
                FROM aqi_result
                WHERE dominant_pollutant IS NOT NULL
                GROUP BY dominant_pollutant
                ORDER BY value DESC
            """)
            rows = cursor.fetchall()
            return jsonify({'type': 'table', 'data': rows, 'headers': ['Pollutant', 'Times as Dominant']})

        return jsonify({'error': 'Invalid query type'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
