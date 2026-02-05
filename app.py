import os
import math
import json
import sqlite3
import numpy as np
import pandas as pd
import httpx
import tensorflow as tf
from joblib import load
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
from contextlib import asynccontextmanager
from typing import Optional, List
import threading
import asyncio

LOOKBACK = 48
TARGETS = ["PM10_AGRABAD", "PM2.5_AGRABAD", "NOX_AGRABAD"]

MODEL_DIR = "saved_models2"
MODEL_PATH  = f"{MODEL_DIR}/aq_lstm_log_huber_lags.keras"
XSCALE_PATH = f"{MODEL_DIR}/aq_x_scaler_log_huber_lags.joblib"
YSCALE_PATH = f"{MODEL_DIR}/aq_y_scaler_log_huber_lags.joblib"
FEATS_PATH  = f"{MODEL_DIR}/aq_feature_cols_log_huber_lags.txt"

# AQI Model
AQI_MODEL_DIR = "artifacts_aqi_model_gpu_2_PM_NO"
AQI_MODEL_PATH = f"{AQI_MODEL_DIR}/aqi_xgb_model_final.pkl"
AQI_FEATURE_PATH = f"{AQI_MODEL_DIR}/feature_columns.pkl"

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

STATE_DIR = "state_store"
os.makedirs(STATE_DIR, exist_ok=True)

# SQLite Database for prediction history
DB_PATH = "prediction_history.db"

def init_database():
    """Initialize SQLite database for storing prediction history"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS prediction_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            station_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            aqi REAL,
            pm25 REAL,
            pm10 REAL,
            nox REAL,
            temp REAL,
            humidity REAL,
            wind_speed REAL,
            lat REAL,
            lng REAL,
            UNIQUE(station_id, timestamp)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_station_time ON prediction_history(station_id, timestamp)')
    conn.commit()
    conn.close()
    print("Database initialized successfully!")

def get_db_connection():
    """Get a database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def store_prediction(station_id: str, data: dict):
    """Store a prediction in the database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO prediction_history 
            (station_id, timestamp, aqi, pm25, pm10, nox, temp, humidity, wind_speed, lat, lng)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            station_id,
            data.get('timestamp', datetime.now(timezone.utc).isoformat()),
            data.get('aqi'),
            data.get('pm25'),
            data.get('pm10'),
            data.get('nox'),
            data.get('temp'),
            data.get('humidity'),
            data.get('wind_speed'),
            data.get('lat'),
            data.get('lng')
        ))
        conn.commit()
    except Exception as e:
        print(f"Error storing prediction: {e}")
    finally:
        conn.close()

def get_prediction_history(station_id: str, hours: int = 24) -> list:
    """Get prediction history for a station for the last N hours"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cutoff_time = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    
    cursor.execute('''
        SELECT * FROM prediction_history 
        WHERE station_id = ? AND timestamp > ?
        ORDER BY timestamp ASC
    ''', (station_id, cutoff_time))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

# Lazy load model and scalers
_model = None
_xsc = None
_ysc = None
_feature_cols = None
_aqi_model = None
_aqi_feature_cols = None

def get_model():
    global _model, _xsc, _ysc, _feature_cols, _aqi_model, _aqi_feature_cols
    if _model is None:
        print("Loading LSTM model...")
        try:
            # Try loading with custom_objects and safe mode
            _model = tf.keras.models.load_model(MODEL_PATH, safe_mode=False)
        except Exception as e:
            print(f"Standard load failed: {e}")
            print("Attempting alternative load method...")
            # If standard loading fails, try with compile=False
            _model = tf.keras.models.load_model(MODEL_PATH, compile=False)
        
        _xsc = load(XSCALE_PATH)
        _ysc = load(YSCALE_PATH)
        with open(FEATS_PATH, "r") as f:
            _feature_cols = [ln.strip() for ln in f if ln.strip()]
        print("LSTM model loaded successfully!")
        
        # Load AQI model
        print("Loading AQI model...")
        _aqi_model = load(AQI_MODEL_PATH)
        _aqi_feature_cols = load(AQI_FEATURE_PATH)
        print("AQI model loaded successfully!")
    return _model, _xsc, _ysc, _feature_cols, _aqi_model, _aqi_feature_cols

def get_aqi_category(aqi: float) -> str:
    """Get AQI category based on AQI value"""
    if aqi <= 50:
        return "Good"
    elif aqi <= 100:
        return "Satisfactory"
    elif aqi <= 200:
        return "Moderately Polluted"
    elif aqi <= 300:
        return "Poor"
    elif aqi <= 400:
        return "Very Poor"
    else:
        return "Severe"

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load model on startup and cleanup on shutdown"""
    # Initialize database
    init_database()
    
    # Load models
    get_model()
    
    # Start background data collection task
    task = asyncio.create_task(hourly_data_collector())
    
    yield
    
    # Cleanup: cancel background task
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

app = FastAPI(title="AQ Forecast API (Open-Meteo)", lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create references that will be set on first use
model = None
xsc = None
ysc = None
FEATURE_COLS = None

class PredictRequest(BaseModel):
    place_id: str = None
    lat: float = None
    lng: float = None

def now_utc_hour():
    return datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)

def time_features(ts: datetime):
    hour = ts.hour
    month = ts.month
    dayofweek = ts.weekday()
    is_weekend = 1 if dayofweek >= 5 else 0

    return {
        "hour_sin": math.sin(2 * math.pi * hour / 24),
        "hour_cos": math.cos(2 * math.pi * hour / 24),
        "month_sin": math.sin(2 * math.pi * month / 12),
        "month_cos": math.cos(2 * math.pi * month / 12),
        "is_weekend": is_weekend
    }

async def fetch_current_weather(lat: float, lng: float):
    params = {
        "latitude": lat,
        "longitude": lng,
        "current": ["temperature_2m", "relative_humidity_2m", "wind_speed_10m", "rain"],
        "timezone": "UTC"
    }
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(OPEN_METEO_URL, params=params)
        if r.status_code != 200:
            raise HTTPException(r.status_code, f"Open-Meteo error: {r.text}")
        return r.json()

async def geocode_place(place_name: str):
    """Geocode place name to lat/lng using Open-Meteo Geocoding API"""
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {
        "name": place_name,
        "count": 10,  # Get more results for suggestions
        "language": "en"
    }
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(url, params=params)
        if r.status_code != 200:
            raise HTTPException(r.status_code, f"Geocoding error: {r.text}")
        data = r.json()
        
        if not data.get("results") or len(data["results"]) == 0:
            # Return error with suggestions
            raise HTTPException(
                404, 
                {
                    "error": f"Location '{place_name}' not found",
                    "suggestions": []
                }
            )
        
        result = data["results"][0]
        return {
            "lat": result["latitude"],
            "lng": result["longitude"],
            "name": result.get("name", place_name),
            "country": result.get("country", ""),
            "suggestions": [
                {
                    "name": r.get("name", ""),
                    "country": r.get("country", ""),
                    "admin1": r.get("admin1", "")
                }
                for r in data["results"][:5]
            ]
        }

def extract_met_inputs(weather_json: dict) -> dict:
    current = weather_json.get("current", {}) or {}

    temp = current.get("temperature_2m", None)
    rh   = current.get("relative_humidity_2m", None)
    ws   = current.get("wind_speed_10m", None)
    rain_mm = current.get("rain", 0.0) or 0.0

    if temp is None or rh is None or ws is None:
        raise HTTPException(500, f"Missing Open-Meteo fields: {weather_json}")

    rain01 = 1 if float(rain_mm) > 0 else 0

    return {
        "Rain_AGRABAD": float(rain01),
        "Temp_AGRABAD": float(temp),
        "RH_AGRABAD": float(rh),
        "WS_AGRABAD": float(ws)
    }

def state_path(place_id: str) -> str:
    safe_id = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in place_id)
    return os.path.join(STATE_DIR, f"{safe_id}.json")

def load_state(place_id: str):
    p = state_path(place_id)
    if not os.path.exists(p):
        return None
    with open(p, "r") as f:
        return json.load(f)

def save_state(place_id: str, state: dict):
    with open(state_path(place_id), "w") as f:
        json.dump(state, f)

def init_state(place_id: str, first_row: dict):
    buf = [first_row.copy() for _ in range(LOOKBACK)]
    st = {
        "buffer": buf,
        "last_pollutants": {"PM10_AGRABAD": 0.0, "PM2.5_AGRABAD": 0.0, "NOX_AGRABAD": 0.0}
    }
    save_state(place_id, st)
    return st

def build_feature_row(ts: datetime, met: dict) -> dict:
    row = {}
    row.update(met)
    row.update(time_features(ts))
    return row

def build_model_input(place_id: str, ts: datetime, met: dict):
    _, xsc, _, feature_cols, _, _ = get_model()
    st = load_state(place_id)
    base_row = build_feature_row(ts, met)

    if st is None:
        st = init_state(place_id, base_row)

    buf = st.get("buffer", [])
    if len(buf) != LOOKBACK:
        buf = (buf[-LOOKBACK:] if len(buf) > LOOKBACK else [base_row] * (LOOKBACK - len(buf)) + buf)

    buf = buf[1:] + [base_row]
    df_buf = pd.DataFrame(buf)

    # Ensure pollutant columns exist
    for t in TARGETS:
        if t not in df_buf.columns:
            df_buf[t] = 0.0

    # Put last predicted pollutants into last row (for lag creation)
    lastp = st.get("last_pollutants", {"PM10_AGRABAD":0.0,"PM2.5_AGRABAD":0.0,"NOX_AGRABAD":0.0})
    for t in TARGETS:
        df_buf.loc[df_buf.index[-1], t] = float(lastp.get(t, 0.0))

    # Create lag columns based on FEATURE_COLS
    lag_cols = [c for c in feature_cols if "_lag" in c]
    for c in lag_cols:
        base, lag = c.split("_lag")
        df_buf[c] = df_buf[base].shift(int(lag))

    df_buf = df_buf.fillna(0.0)

    X = df_buf.reindex(columns=feature_cols).astype("float32").values  # (48, n_features)

    st["buffer"] = df_buf.to_dict(orient="records")[-LOOKBACK:]
    save_state(place_id, st)

    X_scaled = xsc.transform(X)
    return X_scaled.reshape(1, LOOKBACK, -1)

def predict_from_model(X_in: np.ndarray):
    model, _, ysc, _, _, _ = get_model()
    y_pred_log_scaled = model.predict(X_in, verbose=0)
    y_pred_log = ysc.inverse_transform(y_pred_log_scaled)
    y_pred = np.expm1(y_pred_log)[0]
    return {
        "PM10_AGRABAD": float(y_pred[0]),
        "PM2.5_AGRABAD": float(y_pred[1]),
        "NOX_AGRABAD": float(y_pred[2]),
    }

def predict_aqi(ts: datetime, pollutants: dict) -> float:
    """Predict AQI from pollutants using the XGBoost model"""
    _, _, _, _, aqi_model, aqi_feature_cols = get_model()
    
    # Get the state to access the buffer for historical data
    # For now, we'll use a simple linear combination since we don't have all features
    # AQI is typically a weighted combination of pollutants
    
    pm10 = pollutants.get("PM10_AGRABAD", 0.0)
    pm25 = pollutants.get("PM2.5_AGRABAD", 0.0)
    nox = pollutants.get("NOX_AGRABAD", 0.0)
    
    # Simple AQI calculation based on pollutant concentrations
    # Using standard AQI breakpoints for rough estimation
    # In a real scenario, you'd use proper sub-indices for each pollutant
    
    # Normalize pollutants to 0-500 scale (rough AQI mapping)
    pm10_aqi = min(500, (pm10 / 250.0) * 500)  # PM10: 0-250 µg/m³ maps to 0-500 AQI
    pm25_aqi = min(500, (pm25 / 60.0) * 500)   # PM2.5: 0-60 µg/m³ maps to 0-500 AQI
    nox_aqi = min(500, (nox / 200.0) * 500)    # NOx: 0-200 ppb maps to 0-500 AQI
    
    # Take the maximum (most polluted pollutant determines AQI)
    aqi = max(pm10_aqi, pm25_aqi, nox_aqi)
    
    return float(aqi)

@app.post("/predict")
async def predict(req: PredictRequest):
    try:
        # Check if lat/lng provided directly, otherwise geocode place_id
        if req.lat is not None and req.lng is not None:
            lat = req.lat
            lng = req.lng
            location_name = f"Location ({lat:.4f}, {lng:.4f})"
            country = ""
            place_id = f"{lat}_{lng}"
        elif req.place_id:
            # Geocode the place name
            geo_data = await geocode_place(req.place_id)
            lat = geo_data["lat"]
            lng = geo_data["lng"]
            location_name = geo_data["name"]
            country = geo_data["country"]
            place_id = req.place_id
        else:
            raise HTTPException(400, "Either place_id or lat/lng must be provided")
        
        ts = now_utc_hour()
        weather_json = await fetch_current_weather(lat, lng)
        met = extract_met_inputs(weather_json)

        X_in = build_model_input(place_id, ts, met)
        pred = predict_from_model(X_in)
        
        # Predict AQI from pollutants
        aqi = predict_aqi(ts, pred)

        st = load_state(place_id) or {}
        st["last_pollutants"] = pred
        save_state(place_id, st)

        return {
            "place_id": place_id,
            "location_name": location_name,
            "country": country,
            "lat": lat,
            "lng": lng,
            "timestamp_utc": ts.isoformat(),
            "met": met,
            "prediction": pred,
            "aqi": aqi,
            "aqi_category": get_aqi_category(aqi),
            "note": "Uses Open-Meteo (free). Model keeps a rolling 48-step buffer per place."
        }
    except HTTPException as e:
        if e.status_code == 404:
            # Try to get suggestions
            try:
                url = "https://geocoding-api.open-meteo.com/v1/search"
                params = {
                    "name": req.place_id,
                    "count": 5,
                    "language": "en"
                }
                async with httpx.AsyncClient(timeout=20) as client:
                    r = await client.get(url, params=params)
                    if r.status_code == 200:
                        data = r.json()
                        suggestions = [
                            {
                                "name": result.get("name", ""),
                                "country": result.get("country", ""),
                                "admin1": result.get("admin1", "")
                            }
                            for result in data.get("results", [])[:5]
                        ]
                        raise HTTPException(
                            404,
                            {
                                "error": f"Location '{req.place_id}' not found",
                                "suggestions": suggestions
                            }
                        )
            except:
                pass
            raise HTTPException(404, f"Location '{req.place_id}' not found. Please check the spelling and try again.")
        raise

# Stations to collect data for hourly
MONITORED_STATIONS = {
    "CUET": {"lat": 22.4624, "lng": 91.9710, "name": "CUET"},
    "CDA_AGRABAD": {"lat": 22.3236, "lng": 91.8144, "name": "Agrabad"},
    "BARC": {"lat": 23.7806, "lng": 90.2792, "name": "Dhaka BARC"},
    "DOE": {"lat": 23.7287, "lng": 90.3854, "name": "Dhaka DoE"},
}

async def collect_station_data():
    """Collect prediction data for all monitored stations"""
    print(f"[{datetime.now()}] Collecting hourly station data...")
    for station_id, station_info in MONITORED_STATIONS.items():
        try:
            lat = station_info["lat"]
            lng = station_info["lng"]
            ts = now_utc_hour()
            
            weather_json = await fetch_current_weather(lat, lng)
            met = extract_met_inputs(weather_json)
            X_in = build_model_input(station_id, ts, met)
            pred = predict_from_model(X_in)
            aqi = predict_aqi(ts, pred)
            
            # Store in database
            store_prediction(station_id, {
                "timestamp": ts.isoformat(),
                "aqi": aqi,
                "pm25": pred.get("PM2.5_AGRABAD"),
                "pm10": pred.get("PM10_AGRABAD"),
                "nox": pred.get("NOX_AGRABAD"),
                "temp": met.get("Temp_AGRABAD"),
                "humidity": met.get("RH_AGRABAD"),
                "wind_speed": met.get("WS_AGRABAD"),
                "lat": lat,
                "lng": lng
            })
            print(f"  Stored data for {station_id}: AQI={aqi:.1f}")
        except Exception as e:
            print(f"  Error collecting data for {station_id}: {e}")

async def hourly_data_collector():
    """Background task to collect data every hour"""
    while True:
        await collect_station_data()
        # Wait for 1 hour
        await asyncio.sleep(3600)

@app.get("/api/history/{station_id}")
async def get_history(station_id: str, hours: int = 24):
    """Get prediction history for a station"""
    history = get_prediction_history(station_id, hours)
    return {
        "station_id": station_id,
        "hours": hours,
        "count": len(history),
        "data": history
    }

@app.get("/api/stations")
async def get_stations():
    """Get list of monitored stations"""
    return MONITORED_STATIONS

@app.post("/api/store")
async def store_current_prediction(station_id: str, lat: float, lng: float):
    """Manually trigger data collection for a station"""
    try:
        ts = now_utc_hour()
        weather_json = await fetch_current_weather(lat, lng)
        met = extract_met_inputs(weather_json)
        X_in = build_model_input(station_id, ts, met)
        pred = predict_from_model(X_in)
        aqi = predict_aqi(ts, pred)
        
        store_prediction(station_id, {
            "timestamp": ts.isoformat(),
            "aqi": aqi,
            "pm25": pred.get("PM2.5_AGRABAD"),
            "pm10": pred.get("PM10_AGRABAD"),
            "nox": pred.get("NOX_AGRABAD"),
            "temp": met.get("Temp_AGRABAD"),
            "humidity": met.get("RH_AGRABAD"),
            "wind_speed": met.get("WS_AGRABAD"),
            "lat": lat,
            "lng": lng
        })
        return {"status": "success", "station_id": station_id, "aqi": aqi}
    except Exception as e:
        raise HTTPException(500, str(e))

# DOE API Proxy to avoid mixed content issues (HTTPS -> HTTP)
DOE_API_URL = "http://180.211.164.219:8080/aqiApi_v1/aqiApiController/markerAQIData/ABCDEFGHIJKLMNOPQdefghijklmnopqrstuvwxyz0123456789"

@app.get("/api/doe-stations")
async def proxy_doe_stations():
    """Proxy endpoint for DOE AQI API to avoid mixed content issues"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(DOE_API_URL)
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        raise HTTPException(504, "DOE API request timed out")
    except httpx.HTTPError as e:
        raise HTTPException(502, f"DOE API error: {str(e)}")
    except Exception as e:
        raise HTTPException(500, f"Proxy error: {str(e)}")

@app.get("/")
async def root():
    """Serve the enhanced Chittagong map"""
    return FileResponse("map.html")

@app.get("/map")
async def map_view():
    """Serve the original map frontend"""
    return FileResponse("map_chittagong.html")

@app.get("/simple")
async def simple():
    """Serve the simple frontend"""
    return FileResponse("index.html")
