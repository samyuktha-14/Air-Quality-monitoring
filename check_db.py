import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

def check():
    url = os.getenv('MYSQL_URL')
    print(f"Connecting to: {url.split('@')[1] if url else 'Localhost'}")
    
    try:
        # Use your existing connection logic
        from app import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check City Table
        cursor.execute("SELECT COUNT(*) FROM city")
        city_count = cursor.fetchone()[0]
        print(f"Cities found: {city_count}")
        
        # Check Users Table
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        print(f"Users found: {user_count}")
        
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check()
