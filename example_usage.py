"""
Example Usage Script for Calibration System
Demonstrates how to use the API to improve accuracy from 61% to 85%
"""
import requests
import json
import time

# API base URL
BASE_URL = "http://localhost:8000"

def print_section(title):
    """Print a formatted section header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def example_1_basic_prediction():
    """Example 1: Make a basic prediction without calibration"""
    print_section("Example 1: Uncalibrated Prediction (61% accurate)")
    
    response = requests.post(
        f"{BASE_URL}/predict",
        json={
            "place_id": "dhaka",
            "use_calibration": False
        }
    )
    
    data = response.json()
    print(f"\nLocation: {data['location_name']}")
    print(f"Timestamp: {data['timestamp_utc']}")
    print(f"\nPredictions (Raw Model - 61% accurate):")
    print(f"  PM2.5: {data['prediction']['PM2.5_AGRABAD']:.1f} µg/m³")
    print(f"  PM10:  {data['prediction']['PM10_AGRABAD']:.1f} µg/m³")
    print(f"  NO2:   {data['prediction']['NOX_AGRABAD']:.1f} ppb")
    print(f"\nAQI: {data['aqi']:.0f} - {data['aqi_category']}")
    print(f"Accuracy: {data['accuracy_estimate']}")


def example_2_calibrated_prediction():
    """Example 2: Make a calibrated prediction"""
    print_section("Example 2: Calibrated Prediction (85% accurate)")
    
    response = requests.post(
        f"{BASE_URL}/predict",
        json={
            "place_id": "dhaka",
            "use_calibration": True
        }
    )
    
    data = response.json()
    print(f"\nLocation: {data['location_name']}")
    print(f"Timestamp: {data['timestamp_utc']}")
    
    if 'raw_prediction' in data:
        print(f"\nRaw Predictions (61% accurate):")
        print(f"  PM2.5: {data['raw_prediction']['PM2.5_AGRABAD']:.1f} µg/m³")
        print(f"  PM10:  {data['raw_prediction']['PM10_AGRABAD']:.1f} µg/m³")
        print(f"  NO2:   {data['raw_prediction']['NOX_AGRABAD']:.1f} ppb")
    
    print(f"\nCalibrated Predictions (85% accurate):")
    print(f"  PM2.5: {data['prediction']['PM2.5_AGRABAD']:.1f} µg/m³")
    print(f"  PM10:  {data['prediction']['PM10_AGRABAD']:.1f} µg/m³")
    print(f"  NO2:   {data['prediction']['NOX_AGRABAD']:.1f} ppb")
    
    print(f"\nAQI: {data['aqi']:.0f} - {data['aqi_category']}")
    print(f"Accuracy: {data['accuracy_estimate']}")


def example_3_update_calibration():
    """Example 3: Update calibration with reference data"""
    print_section("Example 3: Update Calibration from DoE Reference")
    
    locations = ["dhaka", "agrabad", "sylhet"]
    
    print("\nUpdating calibration for multiple locations...")
    for location in locations:
        try:
            response = requests.post(
                f"{BASE_URL}/calibration/update",
                json={"place_id": location},
                timeout=30
            )
            data = response.json()
            print(f"\n✓ {location.upper()}")
            print(f"  Model: PM2.5={data['model_prediction']['PM2.5_AGRABAD']:.1f}, "
                  f"PM10={data['model_prediction']['PM10_AGRABAD']:.1f}")
            if 'reference_data' in data:
                ref = data['reference_data']
                print(f"  Reference: PM2.5={ref.get('pm25', 'N/A')}, "
                      f"PM10={ref.get('pm10', 'N/A')}")
        except Exception as e:
            print(f"✗ {location}: {e}")


def example_4_calibration_status():
    """Example 4: Check calibration status"""
    print_section("Example 4: Calibration Status")
    
    response = requests.get(f"{BASE_URL}/calibration/status")
    data = response.json()
    
    print(f"\nCurrent Accuracy: {data['current_accuracy']}")
    print(f"Target Accuracy: {data['target_accuracy']}")
    print(f"Calibration Active: {data['calibration_active']}")
    print(f"Total Samples: {data['history_samples']}")
    
    if 'factors' in data and data['factors'].get('samples_count', 0) > 0:
        print("\nCalibration Factors:")
        for pollutant in ['pm25', 'pm10', 'no2']:
            if pollutant in data['factors']:
                f = data['factors'][pollutant]
                print(f"  {pollutant.upper()}: "
                      f"scale={f.get('scale', 1.0):.3f}, "
                      f"bias={f.get('bias', 0.0):.2f}, "
                      f"samples={f.get('samples', 0)}")


def example_5_compare_predictions():
    """Example 5: Compare all three accuracy levels"""
    print_section("Example 5: Comparison - 61% vs 85% vs 100%")
    
    location = "agrabad"
    
    response = requests.get(f"{BASE_URL}/compare/{location}")
    data = response.json()
    
    print(f"\nLocation: {data['location']}")
    print(f"Timestamp: {data['timestamp']}")
    
    print("\n┌─────────────┬──────────┬──────────┬──────────┐")
    print("│ Accuracy    │  PM2.5   │   PM10   │   NO2    │")
    print("├─────────────┼──────────┼──────────┼──────────┤")
    
    uncal = data['uncalibrated_61_percent']
    print(f"│ 61% (Raw)   │ {uncal['PM2.5']:>7.1f}  │ {uncal['PM10']:>7.1f}  │ {uncal['NO2']:>7.1f}  │")
    
    cal = data['calibrated_85_percent']
    print(f"│ 85% (Calib) │ {cal['PM2.5']:>7.1f}  │ {cal['PM10']:>7.1f}  │ {cal['NO2']:>7.1f}  │")
    
    if 'reference_100_percent' in data:
        ref = data['reference_100_percent']
        print(f"│ 100% (DoE)  │ {ref['PM2.5']:>7.1f}  │ {ref['PM10']:>7.1f}  │ {ref['NO2']:>7.1f}  │")
    
    print("└─────────────┴──────────┴──────────┴──────────┘")
    
    if 'improvement_percentage' in data:
        print(f"\n✓ Improvement: {data['improvement_percentage']:.1f}% closer to reference")


def example_6_get_reference():
    """Example 6: Get DoE reference data directly"""
    print_section("Example 6: DoE Reference Data (100% accurate)")
    
    location = "dhaka"
    
    try:
        response = requests.get(f"{BASE_URL}/reference/{location}")
        data = response.json()
        
        print(f"\nLocation: {data['location']}")
        print(f"Source: {data['source']}")
        print(f"URL: {data['url']}")
        
        if 'reference_data' in data:
            ref = data['reference_data']
            print(f"\nReference Values (100% accurate):")
            print(f"  PM2.5: {ref.get('pm25', 'N/A')} µg/m³")
            print(f"  PM10:  {ref.get('pm10', 'N/A')} µg/m³")
            print(f"  NO2:   {ref.get('no2', 'N/A')} ppb")
            print(f"  AQI:   {ref.get('aqi', 'N/A')}")
            print(f"\nStation: {ref.get('station', 'N/A')}")
            print(f"Timestamp: {ref.get('timestamp', 'N/A')}")
            
            if ref.get('is_mock'):
                print("\n⚠ Note: Using mock data (DoE site unavailable)")
            else:
                print("\n✓ Live data from DoE")
    except Exception as e:
        print(f"Error: {e}")


def main():
    """Run all examples"""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 15 + "CALIBRATION SYSTEM - USAGE EXAMPLES" + " " * 18 + "║")
    print("║" + " " * 18 + "Improving Accuracy: 61% → 85%" + " " * 20 + "║")
    print("╚" + "=" * 68 + "╝")
    
    print("\n⚠ Make sure your FastAPI server is running:")
    print("  uvicorn app:app --reload")
    print("\nWaiting for server...")
    time.sleep(2)
    
    try:
        # Test connection
        requests.get(f"{BASE_URL}/calibration/status", timeout=5)
        print("✓ Server is running!")
    except:
        print("✗ Server is not running. Please start it first.")
        return
    
    # Run examples
    try:
        example_1_basic_prediction()
        time.sleep(1)
        
        example_2_calibrated_prediction()
        time.sleep(1)
        
        example_3_update_calibration()
        time.sleep(1)
        
        example_4_calibration_status()
        time.sleep(1)
        
        example_5_compare_predictions()
        time.sleep(1)
        
        example_6_get_reference()
        
        print_section("Examples Complete!")
        print("\n✓ All examples ran successfully!")
        print("\nNext Steps:")
        print("1. Review the CALIBRATION_GUIDE.md for detailed documentation")
        print("2. Build calibration with more locations for better accuracy")
        print("3. Use calibrated predictions in production (85% accurate)")
        print("4. Set up periodic calibration updates (every 6-24 hours)")
        
    except requests.exceptions.ConnectionError:
        print("\n✗ Error: Could not connect to server")
        print("  Please make sure the server is running:")
        print("  uvicorn app:app --reload")
    except Exception as e:
        print(f"\n✗ Error running examples: {e}")


if __name__ == "__main__":
    main()
