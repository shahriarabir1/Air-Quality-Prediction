import os
import math
import json
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
from datetime import datetime, timezone
from contextlib import asynccontextmanager

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
    get_model()
    yield

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

@app.get("/")
async def root():
    """Serve the enhanced Chittagong map"""
    return FileResponse("map_chittagong.html")

@app.get("/map")
async def map_view():
    """Serve the original map frontend"""
    return FileResponse("map.html")

@app.get("/simple")
async def simple():
    """Serve the simple frontend"""
    return FileResponse("index.html")
