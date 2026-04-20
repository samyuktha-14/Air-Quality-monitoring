CREATE DATABASE IF NOT EXISTS aqi_db;
USE aqi_db;

CREATE TABLE IF NOT EXISTS city (
    city_id INT AUTO_INCREMENT PRIMARY KEY,
    city_name VARCHAR(100) NOT NULL,
    state VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS monitoring_station (
    station_id INT AUTO_INCREMENT PRIMARY KEY,
    station_name VARCHAR(255) NOT NULL,
    location VARCHAR(255),
    city_id INT,
    FOREIGN KEY (city_id) REFERENCES city(city_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS pollutant (
    pollutant_id INT AUTO_INCREMENT PRIMARY KEY,
    pollutant_name VARCHAR(50) NOT NULL,
    unit VARCHAR(20) NOT NULL
);

CREATE TABLE IF NOT EXISTS aqi_breakpoint (
    pollutant_id INT,
    concentration_low DECIMAL(10, 4) NOT NULL,
    concentration_high DECIMAL(10, 4) NOT NULL,
    aqi_low INT NOT NULL,
    aqi_high INT NOT NULL,
    FOREIGN KEY (pollutant_id) REFERENCES pollutant(pollutant_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS measurement (
    measurement_id INT AUTO_INCREMENT PRIMARY KEY,
    station_id INT,
    pollutant_id INT,
    measured_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    measured_value DECIMAL(10, 4) NOT NULL,
    FOREIGN KEY (station_id) REFERENCES monitoring_station(station_id) ON DELETE CASCADE,
    FOREIGN KEY (pollutant_id) REFERENCES pollutant(pollutant_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS aqi_result (
    station_id INT,
    measured_date DATE,
    final_aqi INT,
    category VARCHAR(50),
    dominant_pollutant VARCHAR(100),
    PRIMARY KEY (station_id, measured_date),
    FOREIGN KEY (station_id) REFERENCES monitoring_station(station_id) ON DELETE CASCADE
);
