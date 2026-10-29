from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import joblib
import pandas as pd
import os
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///battery_management.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Load ML Models
try:
    battery_health_model = joblib.load('models/battery_health_model.pkl')
    rul_model = joblib.load('models/rul_model.pkl')
    battery_state_model = joblib.load('models/battery_state_model.pkl')
    print("✓ Models loaded successfully")
except Exception as e:
    print(f"⚠ Warning: Could not load models - {e}")
    battery_health_model = None
    rul_model = None
    battery_state_model = None

# Database Models
class User(db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

    predictions = db.relationship('Prediction', backref='user', lazy=True)



class Prediction(db.Model):
    __tablename__ = "prediction"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    cycle_count = db.Column(db.Float)
    avg_speed = db.Column(db.Float)
    avg_voltage = db.Column(db.Float)
    avg_temp = db.Column(db.Float)
    voltage_drop_rate = db.Column(db.Float)

    battery_health = db.Column(db.Float)
    rul_cycles = db.Column(db.Integer)
    battery_state = db.Column(db.String(20))

    created_at = db.Column(db.DateTime, default=datetime.now)

# Create database tables
with app.app_context():
    db.create_all()

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return redirect(url_for('register'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return redirect(url_for('register'))
        
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, email=email, password=hashed_password)
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    user = User.query.get(session['user_id'])
    recent_predictions = Prediction.query.filter_by(user_id=user.id).order_by(Prediction.created_at.desc()).limit(5).all()
    total_predictions = Prediction.query.filter_by(user_id=user.id).count()
    
    # Calculate average health from recent predictions
    avg_health = 0
    if recent_predictions:
        avg_health = sum([p.battery_health for p in recent_predictions]) / len(recent_predictions)
    
    return render_template('dashboard.html', 
                         user=user, 
                         recent_predictions=recent_predictions,
                         total_predictions=total_predictions,
                         avg_health=round(avg_health, 1))

@app.route('/predict', methods=['GET', 'POST'])
@login_required
def predict():
    if request.method == 'POST':
        try:
            # Get form data
            cycle_count = float(request.form.get('cycle_count'))
            avg_speed = float(request.form.get('avg_speed'))
            avg_voltage = float(request.form.get('avg_voltage'))
            avg_temp = float(request.form.get('avg_temp'))
            voltage_drop_rate = float(request.form.get('voltage_drop_rate'))
            
            # Create sample dataframe
            sample = pd.DataFrame([{
                "cycle_count": cycle_count,
                "avg_speed": avg_speed,
                "avg_voltage": avg_voltage,
                "avg_temp": avg_temp,
                "voltage_drop_rate": voltage_drop_rate
            }])
            
            # Make predictions
            if battery_health_model and rul_model and battery_state_model:
                health_pred = battery_health_model.predict(sample)[0]
                rul_pred = rul_model.predict(sample)[0]
                state_pred = battery_state_model.predict(sample)[0]
                
                # Map numeric state to string (adjust based on your label encoder)
                state_mapping = {0: 'Normal', 1: 'Degrading', 2: 'Critical'}
                battery_state = state_mapping.get(int(state_pred), 'Unknown')
            else:
                # Fallback prediction if models not loaded
                health_pred = 75.0
                rul_pred = 2500
                battery_state = 'Normal'
            
            # Save prediction to database
            new_prediction = Prediction(
                user_id=session['user_id'],
                cycle_count=cycle_count,
                avg_speed=avg_speed,
                avg_voltage=avg_voltage,
                avg_temp=avg_temp,
                voltage_drop_rate=voltage_drop_rate,
                battery_health=round(health_pred, 2),
                rul_cycles=int(rul_pred),
                battery_state=battery_state
            )
            
            db.session.add(new_prediction)
            db.session.commit()
            
            # Redirect to result page
            return redirect(url_for('result', prediction_id=new_prediction.id))
            
        except Exception as e:
            flash(f'Error making prediction: {str(e)}', 'error')
            return redirect(url_for('predict'))
    
    return render_template('predict.html')

@app.route('/result/<int:prediction_id>')
@login_required
def result(prediction_id):
    prediction = Prediction.query.get_or_404(prediction_id)
    
    # Verify user owns this prediction
    if prediction.user_id != session['user_id']:
        flash('Unauthorized access', 'error')
        return redirect(url_for('dashboard'))
    
    return render_template('result.html', prediction=prediction)

@app.route('/history')
@login_required
def history():
    predictions = Prediction.query.filter_by(user_id=session['user_id']).order_by(Prediction.created_at.desc()).all()
    return render_template('history.html', predictions=predictions)

@app.route('/analytics')
@login_required
def analytics():
    predictions = Prediction.query.filter_by(user_id=session['user_id']).order_by(Prediction.created_at.asc()).all()
    return render_template('analytics.html', predictions=predictions)

@app.route('/api/analytics-data')
@login_required
def analytics_data():
    predictions = Prediction.query.filter_by(user_id=session['user_id']).order_by(Prediction.created_at.asc()).all()
    
    data = {
        'dates': [p.created_at.strftime('%Y-%m-%d %H:%M') for p in predictions],
        'health': [p.battery_health for p in predictions],
        'rul': [p.rul_cycles for p in predictions],
        'voltage': [p.avg_voltage for p in predictions],
        'temperature': [p.avg_temp for p in predictions],
        'states': [p.battery_state for p in predictions]
    }
    
    return jsonify(data)

if __name__ == '__main__':
    # Create models directory if it doesn't exist
    os.makedirs('models', exist_ok=True)
    app.run(debug=True, host='0.0.0.0', port=5000)
