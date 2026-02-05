"""
Test script to show comparison of Windy, DoE, and our model data
"""
import requests
import json

def test_comparison(location="dhaka"):
    """Test the data comparison for a location"""
    
    print("=" * 80)
    print(f"AIR QUALITY DATA COMPARISON FOR: {location.upper()}")
    print("=" * 80)
    print()
    
    # Make prediction request with calibration
    url = "http://localhost:8000/predict"
    payload = {
        "place_id": location,
        "use_calibration": True
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        
        # Print location info
        print(f"📍 Location: {data['location_name']}, {data['country']}")
        print(f"🕐 Time: {data['timestamp_utc']}")
        print()
        
        # Print comparison table
        comparison = data.get("data_comparison", {})
        
        print("┌" + "─" * 78 + "┐")
        print("│" + " " * 25 + "DATA SOURCE COMPARISON" + " " * 31 + "│")
        print("├" + "─" * 78 + "┤")
        print(f"│ {'Pollutant':<12} │ {'Windy.com':<20} │ {'DoE Bangladesh':<20} │ {'Our Model':<15} │")
        print("├" + "─" * 78 + "┤")
        
        # PM2.5
        windy_pm25 = comparison.get("windy_data", {}).get("PM2.5", 0)
        doe_pm25 = comparison.get("doe_data", {}).get("PM2.5", 0)
        our_pm25 = comparison.get("our_model", {}).get("PM2.5", 0)
        print(f"│ {'PM2.5':<12} │ {windy_pm25:>18.1f}   │ {doe_pm25:>18.1f}   │ {our_pm25:>13.1f}   │")
        
        # PM10
        windy_pm10 = comparison.get("windy_data", {}).get("PM10", 0)
        doe_pm10 = comparison.get("doe_data", {}).get("PM10", 0)
        our_pm10 = comparison.get("our_model", {}).get("PM10", 0)
        print(f"│ {'PM10':<12} │ {windy_pm10:>18.1f}   │ {doe_pm10:>18.1f}   │ {our_pm10:>13.1f}   │")
        
        # NO2
        windy_no2 = comparison.get("windy_data", {}).get("NO2", 0)
        doe_no2 = comparison.get("doe_data", {}).get("NO2", 0)
        our_no2 = comparison.get("our_model", {}).get("NO2", 0)
        print(f"│ {'NO2':<12} │ {windy_no2:>18.1f}   │ {doe_no2:>18.1f}   │ {our_no2:>13.1f}   │")
        
        # AQI
        windy_aqi = comparison.get("windy_data", {}).get("AQI", 0)
        doe_aqi = comparison.get("doe_data", {}).get("AQI", 0)
        our_aqi = comparison.get("our_model", {}).get("AQI", 0)
        print(f"│ {'AQI':<12} │ {windy_aqi:>18.0f}   │ {doe_aqi:>18.0f}   │ {our_aqi:>13.0f}   │")
        
        print("├" + "─" * 78 + "┤")
        
        # Accuracy info
        windy_acc = comparison.get("windy_data", {}).get("accuracy", "N/A")
        doe_acc = comparison.get("doe_data", {}).get("accuracy", "N/A")
        our_acc = comparison.get("our_model", {}).get("accuracy", "N/A")
        
        print(f"│ {'Accuracy':<12} │ {windy_acc:<20} │ {doe_acc:<20} │ {our_acc:<15} │")
        
        # Availability
        windy_avail = "✓" if comparison.get("windy_data", {}).get("available") else "✗"
        doe_avail = "✓" if comparison.get("doe_data", {}).get("available") else "✗"
        our_avail = "✓"
        
        print(f"│ {'Available':<12} │ {windy_avail:<20} │ {doe_avail:<20} │ {our_avail:<15} │")
        
        print("└" + "─" * 78 + "┘")
        print()
        
        # Print summary
        print("📊 SUMMARY:")
        print(f"   • Windy.com: {comparison.get('windy_data', {}).get('source', 'N/A')}")
        print(f"   • DoE: {comparison.get('doe_data', {}).get('source', 'N/A')}")
        print(f"   • Our Model: {comparison.get('our_model', {}).get('source', 'N/A')}")
        print()
        
        # AQI Category
        print(f"🌫️  AQI Category: {data.get('aqi_category', 'N/A')}")
        print()
        
        # Notes
        if not comparison.get("windy_data", {}).get("available"):
            print("⚠️  Note: Windy data using estimated values (API unavailable)")
        if not comparison.get("doe_data", {}).get("available"):
            print("⚠️  Note: DoE data using mock values (no official station nearby)")
        
        print()
        print("=" * 80)
        
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to server. Is it running?")
        print("   Start with: uvicorn app:app --reload")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    import sys
    
    location = sys.argv[1] if len(sys.argv) > 1 else "dhaka"
    test_comparison(location)
    
    print()
    print("💡 Try other locations:")
    print("   python test_comparison.py chittagong")
    print("   python test_comparison.py sylhet")
    print("   python test_comparison.py khulna")
