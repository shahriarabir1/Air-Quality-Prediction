"""
Quick test script to verify the application setup
"""
import os
import sys

def check_files():
    """Check if all required files exist"""
    required_files = [
        "app.py",
        "requirements.txt",
        "saved_models2/aq_lstm_log_huber_lags.keras",
        "saved_models2/aq_x_scaler_log_huber_lags.joblib",
        "saved_models2/aq_y_scaler_log_huber_lags.joblib",
        "saved_models2/aq_feature_cols_log_huber_lags.txt",
        "artifacts_aqi_model_gpu_2_PM_NO/aqi_xgb_model_final.pkl",
        "artifacts_aqi_model_gpu_2_PM_NO/feature_columns.pkl",
    ]
    
    missing = []
    for file in required_files:
        if not os.path.exists(file):
            missing.append(file)
    
    if missing:
        print("❌ Missing required files:")
        for f in missing:
            print(f"   - {f}")
        return False
    else:
        print("✅ All required files present")
        return True

def check_dependencies():
    """Check if required packages are installed"""
    required_packages = [
        "fastapi",
        "uvicorn",
        "tensorflow",
        "pandas",
        "numpy",
        "scikit-learn",
        "joblib",
        "xgboost",
        "httpx",
        "pydantic"
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    
    if missing:
        print("❌ Missing required packages:")
        for p in missing:
            print(f"   - {p}")
        print("\nRun: pip install -r requirements.txt")
        return False
    else:
        print("✅ All required packages installed")
        return True

def check_deployment_files():
    """Check if deployment files exist"""
    deployment_files = [
        "Dockerfile",
        "docker-compose.yml",
        ".dockerignore",
        "render.yaml",
        "railway.json",
        "Procfile",
        "DEPLOYMENT.md",
        "README.md"
    ]
    
    present = []
    for file in deployment_files:
        if os.path.exists(file):
            present.append(file)
    
    print(f"✅ Deployment files ready: {len(present)}/{len(deployment_files)}")
    for f in present:
        print(f"   ✓ {f}")
    
    return True

if __name__ == "__main__":
    print("=" * 50)
    print("AQ Forecast API - Pre-Deployment Check")
    print("=" * 50)
    print()
    
    files_ok = check_files()
    print()
    
    deps_ok = check_dependencies()
    print()
    
    deploy_ok = check_deployment_files()
    print()
    
    if files_ok and deps_ok and deploy_ok:
        print("=" * 50)
        print("✅ Ready for deployment!")
        print("=" * 50)
        print("\nNext steps:")
        print("1. Docker: docker-compose up -d")
        print("2. Local: uvicorn app:app --reload")
        print("3. Cloud: See DEPLOYMENT.md for platform-specific instructions")
        sys.exit(0)
    else:
        print("=" * 50)
        print("❌ Please fix the issues above before deploying")
        print("=" * 50)
        sys.exit(1)
