import yfinance as yf
import numpy as np
import requests
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta
from pinecone import Pinecone

app = Flask(__name__)
CORS(app)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
INDEX_HOST = os.getenv("INDEX_HOST")

def get_now():
    return datetime(2026, 5, 4)

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_query = data.get('query').upper()
    today_str = get_now().strftime('%B %d, %Y')
    try:
        pc = Pinecone(api_key=PINECONE_API_KEY)
        index_pc = pc.Index(host=INDEX_HOST)
        res_emb = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-2:embedContent?key={GOOGLE_API_KEY}", 
            json={"model": "models/gemini-embedding-2", "content": {"parts": [{"text": user_query}]}, "output_dimensionality": 768}).json()
        query_v = res_emb['embedding']['values']
        search = index_pc.query(vector=query_v, top_k=15, include_metadata=True)
        context = "\n".join([m.metadata["text"] for m in search.matches])
        
        gen_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemma-3-27b-it:generateContent?key={GOOGLE_API_KEY}"
        
        prompt_chat = f"""TODAY IS {today_str}. 
        IDENTITY: You are a quantitative analytical engine based on the 'Calculated Risk and Profit Machines' (CRPM) methodology.
        CONTEXT: {context}.
        USER QUERY: {user_query}. 
        
        STRICT FORMATTING RULES:
        1. Respond EXCLUSIVELY in English.
        2. NO personal names. NO square brackets.
        3. Use ONLY bold text for section titles (e.g., **Title:**).
        4. If query is about owning 100 shares, ALWAYS present two options:
           - **Machine 3 (Married Put):** For structural protection.
           - **Machine 4 (Covered Call):** For yield generation.
        5. Use LaTeX for math: $$E(X) = (P_{{below}} \times Premium) + (P_{{above}} \times (Premium - (Price - Strike)))$$.
        6. Explain that E(X) represents the mathematical edge of the strategy."""
        
        res_gen = requests.post(gen_url, json={"contents": [{"parts": [{"text": prompt_chat}]}]}).json()
        return jsonify({"response": res_gen['candidates'][0]['content']['parts'][0]['text']})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/index', methods=['POST', 'GET'])
def index():
    # ... (Il resto del codice index rimane invariato per mantenere la stabilità dei calcoli) ...
    # Per brevità non incollo tutto, ma nel tuo file tieni la versione completa precedente
    pass

handler = app
