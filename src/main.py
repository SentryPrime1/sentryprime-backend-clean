# SentryPrime Minimal AI Backend - Now with BeautifulSoup
from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os
from bs4 import BeautifulSoup # Now we can use this!

app = Flask(__name__)
CORS(app)

@app.route('/')
def health():
    """Provides a simple health check and status of the service."""
    return jsonify({
        "status": "healthy",
        "service": "SentryPrime AI Backend - Clean Version",
        "version": "1.1.0 (BeautifulSoup Enabled)",
        "message": "Ready to integrate AI features."
    })

@app.route('/api/scan/basic', methods=['POST'])
def basic_scan_website():
    """Performs an improved basic scan using BeautifulSoup."""
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({"error": "URL is required"}), 400
    
    url = data.get('url')
    
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        
        # Use BeautifulSoup to parse the HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        
        violations = []
        
        # More accurate check for missing alt text
        images = soup.find_all('img')
        for img in images:
            # Check if alt attribute is missing or empty
            if not img.has_attr('alt') or img['alt'] == '':
                # Try to get a source snippet for context
                src = img.get('src', 'Unknown source')
                violations.append(f"Image missing alt text. (Source: ...{src[-30:]})")

        return jsonify({
            "url": url,
            "violations_count": len(violations),
            "violations_found": violations, # Send back the actual violations
            "status": "completed_html_parse"
        })
        
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Failed to fetch URL: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
