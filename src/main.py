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
