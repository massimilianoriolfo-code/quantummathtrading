import yfinance as yf
import numpy as np
import requests
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
INDEX_HOST = os.getenv("INDEX_HOST")

def get_now():
    return datetime(2026, 5, 4)

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json(silent=True) or {}
    user_query = data.get('query', '')
    if not user_query: return jsonify({"response": "Query missing."})
    
    try:
        # 1. RICERCA RAPIDA PINECONE (REST DIRETTO)
        host = INDEX_HOST.strip().replace("https://", "").replace("http://", "")
        pine_url = f"https://{host}/records/namespaces/book-content/search"
        
        headers = {"Api-Key": PINECONE_API_KEY, "Content-Type": "application/json", "X-Pinecone-Api-Version": "2024-10"}
        payload = {"query": {"inputs": {"text": user_query}, "top_k": 3}}
        
        context = ""
        res_pine = requests.post(pine_url, headers=headers, json=payload, timeout=5)
        if res_pine.status_code == 200:
            hits = res_pine.json().get('result', {}).get('hits', [])
            context = "\n".join([h.get('fields', {}).get('text', '') for h in hits])

        # 2. CHIAMATA DIRETTA GOOGLE GEMINI (Sintassi minima)
        gen_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GOOGLE_API_KEY}"
        
        prompt = f"Today is May 4, 2026. As a CRPM assistant, answer this based on the book context provided: {context}. User query: {user_query}. Rule: English only, bold titles."
        
        ai_req = {"contents": [{"parts": [{"text": prompt}]}]}
        res_ai = requests.post(gen_url, json=ai_req, timeout=8).json()
        
        # Estrazione diretta senza fronzoli
        response_text = res_ai['candidates'][0]['content']['parts'][0]['text']
        return jsonify({"response": response_text})

    except Exception as e:
        # Se fallisce, sputa l'errore crudo nel box per capire cosa succede
        return jsonify({"response": f"System Error: {str(e)}"}), 200

@app.route('/api/index', methods=['POST', 'GET'])
def index():
    # Mantengo il simulatore intatto ma snello
    t = (request.get_json(silent=True) or {}).get('ticker') or request.args.get('ticker')
    if not t: return jsonify({"error": "Ticker missing"}), 400
    try:
        stock = yf.Ticker(t.upper())
        price = round(stock.fast_info['last_price'], 2)
        return jsonify({"ticker": t.upper(), "price": price, "date": "May 04, 2026", "machines": []})
    except:
        return jsonify({"error": "Ticker error"}), 500

handler = app
