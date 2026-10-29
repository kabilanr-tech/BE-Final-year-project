#!/usr/bin/env python3
"""
EV Battery Management System - Quick Start Script
Run this file to start the application
"""

import os
import sys

def check_dependencies():
    """Check if required packages are installed"""
    required = ['flask', 'flask_sqlalchemy', 'werkzeug', 'joblib', 'pandas']
    missing = []
    
    for package in required:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    
    if missing:
        print("❌ Missing dependencies detected!")
        print(f"   Missing: {', '.join(missing)}")
        print("\n📦 Installing dependencies...")
        os.system(f"{sys.executable} -m pip install -r requirements.txt")
        print("✅ Dependencies installed!")
    else:
        print("✅ All dependencies are installed!")

def check_models():
    """Check if ML models exist"""
    models_dir = 'models'
    required_models = [
        'battery_health_model.pkl',
        'rul_model.pkl', 
        'battery_state_model.pkl'
    ]
    
    if not os.path.exists(models_dir):
        os.makedirs(models_dir)
        print(f"\n📁 Created '{models_dir}' directory")
    
    missing_models = []
    for model in required_models:
        if not os.path.exists(os.path.join(models_dir, model)):
            missing_models.append(model)
    
    if missing_models:
        print(f"\n⚠️  Warning: Some ML models are missing:")
        for model in missing_models:
            print(f"   - {model}")
        print("\n💡 The app will work with fallback predictions.")
        print("   Add your trained models to the 'models/' folder for accurate predictions.")
    else:
        print("\n✅ All ML models found!")

def main():
    """Main startup function"""
    print("=" * 60)
    print("🔋 EV Battery Management System")
    print("=" * 60)
    print()
    
    # Check dependencies
    check_dependencies()
    
    # Check models
    check_models()
    
    print("\n" + "=" * 60)
    print("🚀 Starting the application...")
    print("=" * 60)
    print()
    print("📍 Open your browser and visit: http://localhost:5000")
    print("⚡ Press Ctrl+C to stop the server")
    print()
    
    # Import and run the app
    from app import app
    app.run(debug=True, host='0.0.0.0', port=5000)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped. Goodbye!")
        sys.exit(0)
