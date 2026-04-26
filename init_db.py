import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

def init_db():
    try:
        # First connect without specifying database to create it
        conn = mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASS', '')
        )
        cursor = conn.cursor()
        
        # Read the schema.sql file
        with open('schema.sql', 'r') as f:
            schema_sql = f.read()
            
        print("Creating Core Schema (Tables)...")
        # Split by semicolon and execute
        queries = schema_sql.split(';')
        for q in queries:
            if q.strip():
                try:
                    cursor.execute(q)
                except Exception as e:
                    print(f"Error executing schema query: {e}")
                    
        conn.commit()
        
        # Now define and insert triggers individually
        # Switch to database explicitly
        cursor.execute("USE aqi_db;")
        
        print("Creating Trigger trg_calculate_aqi...")
        cursor.execute("DROP TRIGGER IF EXISTS trg_calculate_aqi")
        
        # The trigger logic adapted for timestamps and daily aggregation
        trigger_sql = """
        CREATE TRIGGER trg_calculate_aqi
        AFTER INSERT ON measurement
        FOR EACH ROW
        BEGIN
            DECLARE max_aqi FLOAT;
            DECLARE dom_pollutant VARCHAR(100);
            DECLARE target_date DATE;

            SET target_date = DATE(NEW.measured_at);

            -- Find MAX AQI and corresponding pollutant for the specific date
            SELECT 
                MAX(sub_index),
                (SELECT p.pollutant_name
                 FROM measurement m2
                 JOIN aqi_breakpoint b2 ON m2.pollutant_id = b2.pollutant_id
                 JOIN pollutant p ON m2.pollutant_id = p.pollutant_id
                 WHERE m2.station_id = NEW.station_id
                   AND DATE(m2.measured_at) = target_date
                   AND m2.measured_value BETWEEN b2.concentration_low AND b2.concentration_high
                 ORDER BY 
                    ((b2.aqi_high - b2.aqi_low) / (b2.concentration_high - b2.concentration_low)) 
                    * (m2.measured_value - b2.concentration_low) + b2.aqi_low DESC
                 LIMIT 1)
            INTO max_aqi, dom_pollutant
            FROM (
                SELECT 
                    ((b.aqi_high - b.aqi_low) / (b.concentration_high - b.concentration_low)) 
                    * (m.measured_value - b.concentration_low) + b.aqi_low AS sub_index
                FROM measurement m
                JOIN aqi_breakpoint b 
                    ON m.pollutant_id = b.pollutant_id
                WHERE m.station_id = NEW.station_id
                  AND DATE(m.measured_at) = target_date
                  AND m.measured_value BETWEEN b.concentration_low AND b.concentration_high
            ) AS temp;

            -- Insert/update daily AQI result
            INSERT INTO aqi_result (station_id, measured_date, final_aqi, category, dominant_pollutant)
            VALUES (
                NEW.station_id,
                target_date,
                max_aqi,
                CASE
                    WHEN max_aqi <= 50 THEN 'Good'
                    WHEN max_aqi <= 100 THEN 'Satisfactory'
                    WHEN max_aqi <= 200 THEN 'Moderate'
                    WHEN max_aqi <= 300 THEN 'Poor'
                    WHEN max_aqi <= 400 THEN 'Very Poor'
                    ELSE 'Severe'
                END,
                dom_pollutant
            )
            ON DUPLICATE KEY UPDATE 
                final_aqi = max_aqi,
                category = CASE
                    WHEN max_aqi <= 50 THEN 'Good'
                    WHEN max_aqi <= 100 THEN 'Satisfactory'
                    WHEN max_aqi <= 200 THEN 'Moderate'
                    WHEN max_aqi <= 300 THEN 'Poor'
                    WHEN max_aqi <= 400 THEN 'Very Poor'
                    ELSE 'Severe'
                END,
                dominant_pollutant = dom_pollutant;
        END
        """
        cursor.execute(trigger_sql)
        
        # Seed initial data
        print("Seeding Initial Data...")
        try:
            # Pollutants
            cursor.execute("INSERT IGNORE INTO pollutant (pollutant_id, pollutant_name, unit) VALUES (1, 'PM2.5', 'µg/m³'), (2, 'PM10', 'µg/m³'), (3, 'CO', 'mg/m³'), (4, 'O3', 'µg/m³'), (5, 'NO2', 'µg/m³'), (6, 'SO2', 'µg/m³')")
            
            # Breakpoints
            cursor.execute("INSERT IGNORE INTO aqi_breakpoint (pollutant_id, concentration_low, concentration_high, aqi_low, aqi_high) VALUES "
                           "(1, 0, 30, 0, 50), (1, 30.1, 60, 51, 100), (1, 60.1, 90, 101, 200), (1, 90.1, 120, 201, 300), (1, 120.1, 250, 301, 400), (1, 250.1, 500, 401, 500),"
                           "(2, 0, 50, 0, 50), (2, 50.1, 100, 51, 100), (2, 100.1, 250, 101, 200), (2, 250.1, 350, 201, 300), (2, 350.1, 430, 301, 400), (2, 430.1, 600, 401, 500),"
                           "(3, 0, 1.0, 0, 50), (3, 1.1, 2.0, 51, 100), (3, 2.1, 10.0, 101, 200), (3, 10.1, 17.0, 201, 300), (3, 17.1, 34.0, 301, 400), (3, 34.1, 50.0, 401, 500),"
                           "(4, 0, 50, 0, 50), (4, 50.1, 100, 51, 100), (4, 100.1, 168, 101, 200), (4, 168.1, 208, 201, 300), (4, 208.1, 748, 301, 400), (4, 748.1, 1000, 401, 500),"
                           "(5, 0, 40, 0, 50), (5, 40.1, 80, 51, 100), (5, 80.1, 180, 101, 200), (5, 180.1, 280, 201, 300), (5, 280.1, 400, 301, 400), (5, 400.1, 600, 401, 500),"
                           "(6, 0, 40, 0, 50), (6, 40.1, 80, 51, 100), (6, 80.1, 380, 101, 200), (6, 380.1, 800, 201, 300), (6, 800.1, 1600, 301, 400), (6, 1600.1, 2000, 401, 500)")
            
            # Cities
            cursor.execute("""
            INSERT IGNORE INTO city (city_id, city_name, state) VALUES 
            (1, 'Delhi', 'Delhi'), (2, 'Mumbai', 'Maharashtra'), (3, 'Bangalore', 'Karnataka'), 
            (4, 'Chennai', 'Tamil Nadu'), (5, 'Trivandrum', 'Kerala'), (6, 'Kozhikode', 'Kerala'), 
            (7, 'Coimbatore', 'Tamil Nadu'), (8, 'Kolkata', 'West Bengal'), (9, 'Hyderabad', 'Telangana'), 
            (10, 'Pune', 'Maharashtra')
            """)
            
            # Monitoring Stations (Varied counts: 2, 3, or 4 per city)
            cursor.execute("""
            INSERT IGNORE INTO monitoring_station (station_id, station_name, location, city_id) VALUES 
            -- Delhi (4 stations)
            (1, 'Anand Vihar', 'East Delhi', 1), (2, 'Punjabi Bagh', 'West Delhi', 1), (3, 'RK Puram', 'South Delhi', 1), (28, 'Okhla', 'Industrial South', 1),
            -- Mumbai (4 stations)
            (4, 'Bandra', 'West Mumbai', 2), (5, 'Worli', 'South Mumbai', 2), (6, 'Kurla', 'East Mumbai', 2), (29, 'Borivali', 'North Mumbai', 2),
            -- Bangalore (3 stations)
            (7, 'Indiranagar', 'East Bangalore', 3), (8, 'Jayanagar', 'South Bangalore', 3), (9, 'Whitefield', 'Outer Bangalore', 3),
            -- Chennai (3 stations)
            (10, 'Velachery', 'South Chennai', 4), (11, 'Alandur', 'Central Chennai', 4), (12, 'Manali', 'North Chennai', 4),
            -- Trivandrum (2 stations)
            (13, 'Museum', 'Central Trivandrum', 5), (14, 'Karyavattom', 'Technopark Area', 5),
            -- Kozhikode (2 stations)
            (15, 'Civil Station', 'Civil Station Area', 6), (16, 'Mananchira', 'Town Area', 6),
            -- Coimbatore (2 stations)
            (17, 'SIDCO Kurichi', 'Industrial Area', 7), (18, 'Coimbatore South', 'South Area', 7),
            -- Kolkata (3 stations)
            (19, 'Victoria', 'Central Kolkata', 8), (20, 'Ballygunge', 'South Kolkata', 8), (21, 'Howrah', 'Greater Kolkata', 8),
            -- Hyderabad (4 stations)
            (22, 'Miyapur', 'West Hyderabad', 9), (23, 'Sanathnagar', 'Industrial Area', 9), (24, 'Zoo Park', 'South Hyderabad', 9), (30, 'Bollaram', 'Industrial North', 9),
            -- Pune (3 stations)
            (25, 'Shivaji Nagar', 'Central Pune', 10), (26, 'Hadapsar', 'East Pune', 10), (27, 'Katraj', 'South Pune', 10)
            """)

            # No sample measurements - waiting for user input
            
            # Default Admin User
            from werkzeug.security import generate_password_hash
            admin_password = generate_password_hash('admin123')
            cursor.execute("INSERT IGNORE INTO users (username, password_hash, role) VALUES ('admin', %s, 'admin')", (admin_password,))
            print("Default admin user created: admin / admin123")
        except Exception as e:
            print(f"Initial seed check: {e}")
            
        conn.commit()
        print("Database Initialization Complete!")

    except mysql.connector.Error as err:
        print(f"Database Initialization Failed: {err}")
    finally:
        if 'cursor' in locals() and cursor is not None:
            cursor.close()
        if 'conn' in locals() and conn is not None:
            conn.close()

if __name__ == '__main__':
    init_db()
