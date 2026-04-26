import mysql.connector
import os
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv()

def fix_db():
    try:
        conn = mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASS', ''),
            database=os.getenv('DB_NAME', 'aqi_db')
        )
        cursor = conn.cursor()
        
        print("Creating 'users' table...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(20) DEFAULT 'operator',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        print("Adding default admin user...")
        admin_pass = generate_password_hash('admin123')
        cursor.execute("INSERT IGNORE INTO users (username, password_hash, role) VALUES ('admin', %s, 'admin')", (admin_pass,))
        
        conn.commit()
        print("Done! Database is now ready for login.")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()

if __name__ == '__main__':
    fix_db()
