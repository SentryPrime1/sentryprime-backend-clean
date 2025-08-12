# SentryPrime AI Backend with Authentication
from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os
from bs4 import BeautifulSoup
import openai
import hashlib # For password hashing
import secrets # For generating secure tokens

# --- Configuration ---
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "https://sentryprime-frontend-final.vercel.app"}} )
openai.api_key = os.environ.get("OPENAI_API_KEY")

# --- In-Memory Database (for now) ---
# This will reset if the server restarts. A real database is the next step.
users = {} # Will store users by email
active_tokens = {} # Will map tokens to user emails

# --- Authentication Endpoints ---

@app.route('/api/auth/register', methods=['POST'])
def register_user():
    data = request.get_json()
    if not data or not all(k in data for k in ['firstName', 'lastName', 'email', 'password']):
        return jsonify({"error": "Missing required fields"}), 400

    email = data['email'].lower()
    if email in users:
        return jsonify({"error": "An account with this email already exists"}), 409

    # Securely hash the password
    hashed_password = hashlib.sha256(data['password'].encode()).hexdigest()

    users[email] = {
        "firstName": data['firstName'],
        "lastName": data['lastName'],
        "password_hash": hashed_password
    }
    
    # Automatically log the user in by creating a token
    token = secrets.token_hex(24)
    active_tokens[token] = email

    return jsonify({
        "message": "User registered successfully",
        "token": token,
        "user": {"firstName": data['firstName'], "email": email}
    }), 201

@app.route('/api/auth/login', methods=['POST'])
def login_user():
    data = request.get_json()
    if not data or not all(k in data for k in ['email', 'password']):
        return jsonify({"error": "Email and password are required"}), 400

    email = data['email'].lower()
    user = users.get(email)
    
    if not user:
        return jsonify({"error": "Invalid credentials"}), 401

    # Check if the provided password matches the stored hash
    hashed_password = hashlib.sha256(data['password'].encode()).hexdigest()
    if hashed_password != user['password_hash']:
        return jsonify({"error": "Invalid credentials"}), 401
        
    # Create a new secure token for the session
    token = secrets.token_hex(24)
    active_tokens[token] = email

    return jsonify({
        "message": "Login successful",
        "token": token,
        "user": {"firstName": user['firstName'], "email": email}
    })

# --- Helper Function for AI Analysis ---
def get_ai_recommendation(violation_text):
    if not openai.api_key:
        return "AI analysis is not configured."

    try:
        system_prompt = "You are an expert web accessibility consultant. Provide a clear, concise, and actionable recommendation for fixing a specific violation. Structure your response in three parts: 1. **What it is:** 2. **Why it matters:** 3. **How to fix it:** (with a code example)."
        user_prompt = f"Please provide an accessibility recommendation for the following violation: '{violation_text}'"
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            temperature=0.5, max_tokens=250
        )
        return response.choices[0].message['content'].strip()
    except Exception as e:
        return f"Could not get AI recommendation: {str(e)}"

# --- Core API Endpoints ---
@app.route('/')
def health():
    ai_status = "Ready" if openai.api_key else "Not Configured"
    return jsonify({
        "status": "healthy", "service": "SentryPrime AI Report Engine",
        "version": "2.1.0 (Auth Enabled)", "ai_status": ai_status
    })

@app.route('/api/scan/ai-enhanced', methods=['POST'])
def ai_enhanced_scan():
    # A real implementation would check for a valid token here
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({"error": "URL is required"}), 400
    
    url = data.get('url')
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        violations = []
        images = soup.find_all('img')
        for img in images:
            if not img.has_attr('alt') or img['alt'] == '':
                violations.append({"type": "Missing Alt Text", "element_tag": str(img)})
        
        ai_enhanced_results = []
        for violation in violations[:3]: # Limit to 3 for faster testing
            recommendation = get_ai_recommendation(f"{violation['type']} on element: {violation['element_tag']}")
            violation['ai_recommendation'] = recommendation
            ai_enhanced_results.append(violation)

        return jsonify({
            "url": url, "violations_count": len(ai_enhanced_results),
            "results": ai_enhanced_results, "status": "completed_ai_analysis"
        })
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
