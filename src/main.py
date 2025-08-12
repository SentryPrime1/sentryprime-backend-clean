# SentryPrime AI-Powered Accessibility Report Engine
from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os
from bs4 import BeautifulSoup
import openai # The star of the show!

# --- Configuration ---
app = Flask(__name__)
CORS(app)

# Configure OpenAI API Key from Railway Variables
openai.api_key = os.environ.get("OPENAI_API_KEY")

# --- Helper Function for AI Analysis ---
def get_ai_recommendation(violation_text):
    if not openai.api_key:
        return {"error": "OpenAI API key is not configured."}

    try:
        system_prompt = """
        You are an expert web accessibility consultant. Your task is to provide a clear, concise, and actionable recommendation for fixing a specific accessibility violation.
        Structure your response in three parts:
        1.  **What it is:** Briefly explain the violation in simple terms.
        2.  **Why it matters:** Describe the impact on users, especially those with disabilities.
        3.  **How to fix it:** Provide a step-by-step guide with a clear "before" and "after" code example.
        """
        
        user_prompt = f"Please provide an accessibility recommendation for the following violation: '{violation_text}'"

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.5,
            max_tokens=250
        )
        
        return response.choices[0].message['content'].strip()

    except Exception as e:
        return f"Could not get AI recommendation: {str(e)}"


# --- API Endpoints ---
@app.route('/')
def health():
    """Provides a health check and confirms AI readiness."""
    ai_status = "Ready" if openai.api_key else "Not Configured"
    return jsonify({
        "status": "healthy",
        "service": "SentryPrime AI Report Engine",
        "version": "2.0.0 (AI Enabled)",
        "ai_status": ai_status
    })

@app.route('/api/scan/ai-enhanced', methods=['POST'])
def ai_enhanced_scan():
    """Performs a scan and enriches findings with AI recommendations."""
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({"error": "URL is required"}), 400
    
    url = data.get('url')
    
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        violations = []
        
        # Scan for images missing alt text
        images = soup.find_all('img')
        for img in images:
            if not img.has_attr('alt') or img['alt'] == '':
                src = img.get('src', 'Unknown source')
                violation_details = {
                    "type": "Missing Alt Text",
                    "element_tag": str(img),
                    "context": f"Image source: ...{src[-40:]}"
                }
                violations.append(violation_details)

        # --- AI Enrichment Step ---
        ai_enhanced_results = []
        for violation in violations:
            recommendation = get_ai_recommendation(f"{violation['type']} on element: {violation['element_tag']}")
            violation['ai_recommendation'] = recommendation
            ai_enhanced_results.append(violation)

        return jsonify({
            "url": url,
            "violations_count": len(ai_enhanced_results),
            "results": ai_enhanced_results,
            "status": "completed_ai_analysis"
        })
        
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False) # Debug mode off for production
