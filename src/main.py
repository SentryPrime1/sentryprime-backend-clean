# SentryPrime Minimal AI Backend - Clean Start
from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os
# We will add beautifulsoup and openai back later

app = Flask(__name__)
CORS(app)

@app.route('/')
def health():
    """Provides a simple health check and status of the service."""
    return jsonify({
        "status": "healthy",
        "service": "SentryPrime AI Backend - Clean Version",
        "version": "1.0.0",
        "message": "Ready to integrate AI features."
    })

@app.route('/api/scan/basic', methods=['POST'])
def basic_scan_website():
    """Performs a very basic scan for missing image alt text."""
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({"error": "URL is required"}), 400
    
    url = data.get('url')
    
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()  # Raise an exception for bad status codes
        
        # A proper parser like beautifulsoup4 is needed for real analysis
        # This is a placeholder to confirm functionality
        if '<img' in response.text and 'alt=' not in response.text:
            violations_count = 1
            status = "completed_basic"
        else:
            violations_count = 0
            status = "completed_basic"

        return jsonify({
            "url": url,
            "violations_count": violations_count,
            "status": status
        })
        
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Failed to fetch URL: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

if __name__ == '__main__':
    # Use the PORT environment variable provided by Railway
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
