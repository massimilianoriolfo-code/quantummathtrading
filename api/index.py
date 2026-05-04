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
    return datetime(2026, 5, 4) # Data fissa richiesta

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_query = data.get('query')
    today_str = get_now().strftime('%B %d, %Y')
    
    try:
        pc = Pinecone(api_key=PINECONE_API_KEY)
        index_pc = pc.Index(host=INDEX_HOST)
        res_emb = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-2:embedContent?key={GOOGLE_API_KEY}", 
            json={"model": "models/gemini-embedding-2", "content": {"parts": [{"text": user_query}]}, "output_dimensionality": 768}).json()
        query_v = res_emb['embedding']['values']
        search = index_pc.query(vector=query_v, top_k=10, include_metadata=True)
        context = "\n".join([m.metadata["text"] for m in search.matches])
        
        gen_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemma-3-27b-it:generateContent?key={GOOGLE_API_KEY}"
        prompt_chat = f"""TODAY IS {today_str}. 
        You are the AI Assistant for the book 'The Essence of Quantitative Math Trading with Options'.
        Use the following book context: {context}
        USER QUESTION: {user_query}
        
        INSTRUCTIONS:
        - Use ONLY Markdown for bolding, NEVER use vertical bars or raw table syntax.
        - Explain Machine 3 (Married Put) as Long Stock + Put Option ITM.
        - Be direct and professional."""
        
        res_gen = requests.post(gen_url, json={"contents": [{"parts": [{"text": prompt_chat}]}]}).json()
        return jsonify({"response": res_gen['candidates'][0]['content']['parts'][0]['text']})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/index', methods=['POST', 'GET'])
def index():
    data = request.get_json(silent=True) or {}
    t = data.get('ticker') or request.args.get('ticker')
    if not t: return jsonify({"error": "Ticker missing"}), 400
    ticker_sym = t.upper()
    today_dt = get_now()

    try:
        stock = yf.Ticker(ticker_sym)
        company_name = stock.info.get('longName', ticker_sym)
        price = stock.fast_info['last_price']
        
        # Volatilità
        iv_val = 0.27 # Fallback come da immagine utente
        exp_30_str = (today_dt + timedelta(days=30)).strftime('%d %b %Y')
        m3_expiry_str = (today_dt + timedelta(days=180)).strftime('%B %Y')
        
        # Calcoli Range
        move = price * iv_val * np.sqrt(30 / 365)
        high, low = round(price + move, 2), round(price - move, 2)
        
        # Machine 3
        m3_strike = round(price * 1.02, 2)
        max_risk_pct = round(((price * 0.08 - (m3_strike - price)) / price) * 100, 2)

        # Restituiamo dati strutturati per il frontend, non testo grezzo
        return jsonify({
            "ticker": ticker_sym,
            "company": company_name,
            "price": round(price, 2),
            "volatility": round(iv_val*100, 2),
            "high": high,
            "low": low,
            "date": today_dt.strftime('%B %d, %Y'),
            "machines": [
                {"name": "Machine 1 (Long Call)", "target": high, "expiry": exp_30_str, "profit": "Unlimited", "risk": "Finite (Premium)"},
                {"name": "Machine 2 (Short Put)", "target": low, "expiry": exp_30_str, "profit": "Finite (Premium)", "risk": "Finite (Calculated)"},
                {"name": "Machine 3 (Married Put)", "target": m3_strike, "expiry": m3_expiry_str, "profit": "UNLIMITED", "risk": f"{max_risk_pct}%"}
            ]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

handler = app
