import os
import datetime
from functools import wraps
import jwt
from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import openai

# --- CONFIGURATION ---
app = Flask(__name__)
# Use a more specific CORS configuration for production
CORS(app, resources={r"/api/*": {"origins": "*"}}, allow_headers=["Content-Type", "Authorization"])
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-default-secret-key')
openai.api_key = os.environ.get("OPENAI_API_KEY")

# --- IN-MEMORY DATABASE ---
# This acts as a temporary database. It will reset if the server restarts.
db = {
    "users": {},
    "websites": {},
    "scans": {}
}
# Use counters to simulate auto-incrementing IDs
user_id_counter = 1
website_id_counter = 1
scan_id_counter = 1

# --- AUTHENTICATION DECORATOR ---
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            try:
                token = request.headers['Authorization'].split(" ")[1]
            except IndexError:
                return jsonify({'message': 'Token is missing or malformed!'}), 401
        
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401

        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = db['users'].get(data['user_id'])
            if not current_user:
                 return jsonify({'message': 'User not found!'}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired!'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Token is invalid!'}), 401

        return f(current_user, *args, **kwargs)
    return decorated

# --- AUTHENTICATION ROUTES ---
@app.route('/api/auth/register', methods=['POST'])
def register():
    global user_id_counter
    data = request.get_json()
    if not data or not all(k in data for k in ['firstName', 'lastName', 'email', 'password']):
        return jsonify({'error': 'Missing required fields'}), 400
    
    email = data['email'].lower()
    if any(u['email'] == email for u in db['users'].values()):
        return jsonify({'error': 'An account with this email already exists'}), 409

    user = {
        'id': user_id_counter,
        'firstName': data['firstName'],
        'lastName': data['lastName'],
        'email': email,
        'password': data['password'], # In a real app, hash this!
        'created_at': datetime.datetime.utcnow()
    }
    db['users'][user_id_counter] = user
    user_id_counter += 1
    
    token = jwt.encode({
        'user_id': user['id'],
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }, app.config['SECRET_KEY'], algorithm="HS256")

    return jsonify({'token': token, 'user': {'id': user['id'], 'firstName': user['firstName'], 'email': user['email']}}), 201

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or not all(k in data for k in ['email', 'password']):
        return jsonify({'error': 'Email and password are required'}), 400

    email = data['email'].lower()
    user = next((u for u in db['users'].values() if u['email'] == email), None)

    if not user or user['password'] != data['password']:
        return jsonify({'error': 'Invalid credentials'}), 401

    token = jwt.encode({
        'user_id': user['id'],
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }, app.config['SECRET_KEY'], algorithm="HS256")

    return jsonify({'token': token, 'user': {'id': user['id'], 'firstName': user['firstName'], 'email': user['email']}})

# --- DASHBOARD API ROUTES ---
@app.route('/api/dashboard/stats', methods=['GET'])
@token_required
def get_dashboard_stats(current_user):
    user_websites = [w for w in db['websites'].values() if w['user_id'] == current_user['id']]
    user_scans = [s for s in db['scans'].values() if s['website_id'] in [w['id'] for w in user_websites]]
    
    total_violations = sum(s.get('total_violations', 0) for s in user_scans)
    avg_compliance = (100 - total_violations) if user_scans else 100 # Simplified logic

    return jsonify({
        "overview": {
            "total_websites": len(user_websites),
            "avg_compliance_score": int(avg_compliance),
            "total_violations": total_violations,
            "total_scans": len(user_scans)
        },
        "recent_activity": sorted(user_scans, key=lambda x: x['scan_date'], reverse=True)[:5],
        "quick_stats": {
            "websites_monitored": len(user_websites),
            "scans_this_month": len(user_scans), # Simplified
            "last_scan_date": user_scans[-1]['scan_date'] if user_scans else None
        }
    })

@app.route('/api/dashboard/websites', methods=['GET', 'POST'])
@token_required
def manage_websites(current_user):
    global website_id_counter
    if request.method == 'POST':
        data = request.get_json()
        if not data or not data.get('url'):
            return jsonify({'error': 'URL is required'}), 400
        
        website = {
            'id': website_id_counter,
            'user_id': current_user['id'],
            'url': data['url'],
            'name': data.get('name', data['url']),
            'created_at': datetime.datetime.utcnow(),
            'last_scan_date': None,
            'compliance_score': 100,
            'total_violations': 0,
            'risk_level': 'Low'
        }
        db['websites'][website_id_counter] = website
        website_id_counter += 1
        return jsonify(website), 201

    # GET request
    user_websites = [w for w in db['websites'].values() if w['user_id'] == current_user['id']]
    return jsonify({'websites': user_websites})

@app.route('/api/dashboard/scans', methods=['GET'])
@token_required
def get_user_scans(current_user):
    user_websites = [w['id'] for w in db['websites'].values() if w['user_id'] == current_user['id']]
    user_scans = [s for s in db['scans'].values() if s['website_id'] in user_websites]
    return jsonify({'scans': sorted(user_scans, key=lambda x: x['scan_date'], reverse=True)})

# --- SCANNING ROUTE ---
@app.route('/api/dashboard/scan', methods=['POST'])
@token_required
def trigger_scan(current_user):
    global scan_id_counter
    data = request.get_json()
    if not data or not data.get('url') or not data.get('website_id'):
        return jsonify({'error': 'URL and Website ID are required'}), 400

    website_id = data['website_id']
    website = db['websites'].get(website_id)
    if not website or website['user_id'] != current_user['id']:
        return jsonify({'error': 'Website not found or access denied'}), 404

    # --- Perform the actual scan ---
    try:
        response = requests.get(data['url'], timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        images = soup.find_all('img')
        violations = [str(img) for img in images if not img.has_attr('alt') or img['alt'] == '']
        num_violations = len(violations)
    except Exception as e:
        return jsonify({'error': f"Failed to scan URL: {str(e)}"}), 500
    # --- End of scan ---

    scan_result = {
        'id': scan_id_counter,
        'website_id': website_id,
        'website_name': website['name'],
        'url': data['url'],
        'scan_date': datetime.datetime.utcnow(),
        'status': 'completed',
        'total_violations': num_violations,
        'serious_violations': num_violations, # Simplified
        'moderate_violations': 0,
        'compliance_score': max(0, 100 - num_violations), # Simplified
        'risk_level': 'High' if num_violations > 10 else 'Moderate' if num_violations > 0 else 'Low'
    }
    db['scans'][scan_id_counter] = scan_result
    scan_id_counter += 1

    # Update website record
    website['last_scan_date'] = scan_result['scan_date']
    website['compliance_score'] = scan_result['compliance_score']
    website['total_violations'] = scan_result['total_violations']
    website['risk_level'] = scan_result['risk_level']

    return jsonify(scan_result), 201

# --- HEALTH CHECK ---
@app.route('/')
def health_check():
    return jsonify({'status': 'healthy', 'service': 'SentryPrime Final Backend'}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    # Use gunicorn for production if available, otherwise use Flask's dev server
    if os.environ.get('RAILWAY_ENVIRONMENT') == 'production':
        from gunicorn.app.base import BaseApplication

        class StandaloneApplication(BaseApplication):
            def __init__(self, app, options=None):
                self.options = options or {}
                self.application = app
                super().__init__()

            def load_config(self):
                config = {key: value for key, value in self.options.items()
                          if key in self.cfg.settings and value is not None}
                for key, value in config.items():
                    self.cfg.set(key.lower(), value)

            def load(self):
                return self.application

        options = {
            'bind': f'0.0.0.0:{port}',
            'workers': 4,
            'worker_class': 'gevent',
        }
        StandaloneApplication(app, options).run()
    else:
        app.run(host='0.0.0.0', port=port, debug=True)
