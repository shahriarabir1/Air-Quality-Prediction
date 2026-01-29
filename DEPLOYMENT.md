# Air Quality Forecast API - Deployment Guide

This is a FastAPI-based air quality prediction system using LSTM and XGBoost models with weather data from Open-Meteo API.

## 📋 Project Overview

- **Framework**: FastAPI (Python)
- **ML Models**: TensorFlow LSTM + XGBoost
- **Features**: Real-time AQI prediction, interactive maps, location search
- **APIs**: Open-Meteo for weather data

## 🚀 Deployment Options

### 1. Docker (Recommended)

#### Prerequisites
- Docker installed
- Docker Compose (optional but recommended)

#### Build and Run with Docker Compose
```bash
# Build and start the container
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the container
docker-compose down
```

The app will be available at `http://localhost:8000`

#### Build and Run with Docker only
```bash
# Build image
docker build -t aq-forecast .

# Run container
docker run -d -p 8000:8000 --name aq-forecast-app aq-forecast

# View logs
docker logs -f aq-forecast-app

# Stop container
docker stop aq-forecast-app
docker rm aq-forecast-app
```

### 2. Render.com (Cloud - Free Tier Available)

#### Steps:
1. Create account at [render.com](https://render.com)
2. Connect your GitHub repository
3. Create a new Web Service
4. Select "Docker" as environment
5. Render will automatically detect `render.yaml`
6. Click "Create Web Service"

**Configuration** (if manual setup):
- **Build Command**: Use Dockerfile
- **Start Command**: `uvicorn app:app --host 0.0.0.0 --port $PORT`
- **Health Check Path**: `/simple`
- **Add Disk**: Mount `/app/state_store` (1GB)

**Note**: Free tier has 750 hours/month and may spin down after inactivity.

### 3. Railway.app (Cloud - $5/month credit)

#### Steps:
1. Create account at [railway.app](https://railway.app)
2. Click "New Project" → "Deploy from GitHub repo"
3. Select your repository
4. Railway will auto-detect `railway.json` and `Dockerfile`
5. Click "Deploy"

**Environment Variables** (if needed):
- `PORT`: Auto-configured by Railway
- `PYTHONUNBUFFERED`: 1

### 4. Heroku (Cloud)

#### Prerequisites
- Heroku CLI installed
- Heroku account

#### Steps:
```bash
# Login to Heroku
heroku login

# Create Heroku app
heroku create your-aq-forecast-app

# Set stack to container
heroku stack:set container -a your-aq-forecast-app

# Deploy
git push heroku main

# Open app
heroku open -a your-aq-forecast-app
```

### 5. Azure Container Instances

#### Steps:
```bash
# Login to Azure
az login

# Create resource group
az group create --name aq-forecast-rg --location eastus

# Create container registry
az acr create --resource-group aq-forecast-rg --name aqforecastacr --sku Basic

# Build and push image
az acr build --registry aqforecastacr --image aq-forecast:latest .

# Deploy container
az container create \
  --resource-group aq-forecast-rg \
  --name aq-forecast-app \
  --image aqforecastacr.azurecr.io/aq-forecast:latest \
  --cpu 2 \
  --memory 4 \
  --registry-username <username> \
  --registry-password <password> \
  --dns-name-label aq-forecast \
  --ports 8000

# Get URL
az container show --resource-group aq-forecast-rg --name aq-forecast-app --query ipAddress.fqdn
```

### 6. AWS (EC2 + Docker)

#### Steps:
1. Launch EC2 instance (t3.medium recommended - 4GB RAM for TensorFlow)
2. SSH into instance
3. Install Docker:
```bash
sudo yum update -y
sudo yum install docker -y
sudo service docker start
sudo usermod -a -G docker ec2-user
```
4. Clone repository and deploy:
```bash
git clone <your-repo-url>
cd DRE
sudo docker-compose up -d
```
5. Configure Security Group to allow port 8000

### 7. Google Cloud Run

#### Steps:
```bash
# Set project
gcloud config set project YOUR_PROJECT_ID

# Build and deploy
gcloud run deploy aq-forecast \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 4Gi \
  --cpu 2 \
  --timeout 300
```

### 8. Local Development (No Docker)

#### Prerequisites
- Python 3.11+
- pip

#### Steps:
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run server
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Visit `http://localhost:8000` in your browser.

## 📱 Available Endpoints

- `/` - Chittagong map view (main interface)
- `/map` - Alternative map view
- `/simple` - Simple input interface
- `/predict` - API endpoint (POST)

## 🔍 API Usage

### Predict by Location Name
```bash
curl -X POST "http://localhost:8000/predict" \
  -H "Content-Type: application/json" \
  -d '{"place_id": "Dhaka"}'
```

### Predict by Coordinates
```bash
curl -X POST "http://localhost:8000/predict" \
  -H "Content-Type: application/json" \
  -d '{"lat": 22.3569, "lng": 91.7832}'
```

### Response Format
```json
{
  "place_id": "Dhaka",
  "location_name": "Dhaka",
  "country": "Bangladesh",
  "lat": 23.7104,
  "lng": 90.4074,
  "timestamp_utc": "2026-01-29T12:00:00+00:00",
  "met": {
    "Rain_AGRABAD": 0,
    "Temp_AGRABAD": 25.3,
    "RH_AGRABAD": 68.0,
    "WS_AGRABAD": 3.5
  },
  "prediction": {
    "PM10_AGRABAD": 145.2,
    "PM2.5_AGRABAD": 68.5,
    "NOX_AGRABAD": 42.3
  },
  "aqi": 274.0,
  "aqi_category": "Poor",
  "note": "Uses Open-Meteo (free). Model keeps a rolling 48-step buffer per place."
}
```

## 🔧 Configuration

### Environment Variables
- `PORT` - Server port (default: 8000)
- `PYTHONUNBUFFERED` - Enable real-time logging (set to 1)

### Resource Requirements
- **Minimum**: 2GB RAM, 1 CPU
- **Recommended**: 4GB RAM, 2 CPUs (for TensorFlow)
- **Storage**: ~500MB for models + state storage

## 📊 Model Files Structure
```
saved_models2/
├── aq_lstm_log_huber_lags.keras    # LSTM model
├── aq_x_scaler_log_huber_lags.joblib   # Input scaler
├── aq_y_scaler_log_huber_lags.joblib   # Output scaler
└── aq_feature_cols_log_huber_lags.txt  # Feature columns

artifacts_aqi_model_gpu_2_PM_NO/
├── aqi_xgb_model_final.pkl         # XGBoost AQI model
└── feature_columns.pkl             # AQI feature columns
```

## 🛠️ Troubleshooting

### Issue: "Model loading failed"
- Ensure all model files are present in `saved_models2/` and `artifacts_aqi_model_gpu_2_PM_NO/`
- Check file permissions
- Verify TensorFlow version compatibility (2.16.1)

### Issue: "Out of memory"
- Increase container/instance memory to at least 4GB
- Reduce number of workers in start command

### Issue: "Location not found"
- Check spelling of place name
- Try using coordinates instead
- Use suggestions from error response

### Issue: "Open-Meteo API timeout"
- Check internet connectivity
- Open-Meteo may be experiencing issues (rare)
- Try again after a few minutes

## 📈 Monitoring & Logs

### Docker Logs
```bash
docker-compose logs -f
```

### Health Check
```bash
curl http://localhost:8000/simple
```

## 🔐 Security Notes

- API is currently open (no authentication)
- For production, consider adding:
  - API key authentication
  - Rate limiting
  - HTTPS/SSL certificates
  - CORS restrictions

## 📝 License & Credits

- Uses Open-Meteo API (free, no API key required)
- Models trained on Bangladesh air quality data
- Built with FastAPI, TensorFlow, and XGBoost

## 🤝 Support

For issues or questions, please check:
1. Deployment logs
2. Health check endpoint
3. API documentation at `/docs`

---

**Ready to deploy!** Choose your preferred platform and follow the steps above. Docker is recommended for consistency across environments.
