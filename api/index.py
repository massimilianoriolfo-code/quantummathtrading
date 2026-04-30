import yfinance as yf
import numpy as np
import requests
import os  # <--- AGGIUNTO per leggere le chiavi segrete
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta
from pinecone import Pinecone

app = Flask(__name__)
CORS(app)

# --- CONFIGURAZIONE SICURA ---
# Invece di incollare il testo della chiave, diciamo al programma 
# di prenderlo dal "cassetto segreto" di Vercel (Environment Variables)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
INDEX_HOST = os.getenv("INDEX_HOST")

@app.route('/api/index', methods=['POST', 'GET'])
def index():
    data = request.get_json(silent=True) or {}
    t = data.get('ticker') or request.args.get('ticker')
    if not t: return jsonify({"error": "Ticker mancante"}), 400
    ticker = t.upper()

    try:
        stock = yf.Ticker(ticker)
        # Prezzo attuale (fast_info è più rapido)
        price = stock.fast_info['last_price']
        
        # --- CALCOLO VOLATILITÀ REALE (Il tuo motore) ---
        expirations = stock.options
        target_date = datetime.now() + timedelta(days=30)
        closest_exp = min(expirations, key=lambda x: abs((datetime.strptime(x, '%Y-%m-%d') - target_date).days))
        opt_chain = stock.option_chain(closest_exp)
        
        # Calcolo IV media delle opzioni At-The-Money (ATM)
        iv_reale = (opt_chain.calls.iloc[(opt_chain.calls['strike'] - price).abs().idxmin()]['impliedVolatility'] + 
                    opt_chain.puts.iloc[(opt_chain.puts['strike'] - price).abs().idxmin()]['impliedVolatility']) / 2
        
        # Formula CRPM: Deviazione = Prezzo * IV * radice(tempo)
        move = price * iv_reale * np.sqrt(30 / 365)
        high, low = round(price + move, 2), round(price - move, 2)

        # --- LOGICA AI (Knowledge Base del libro) ---
        # 1. Connessione a Pinecone
        pc = Pinecone(api_key=PINECONE_API_KEY)
        index_pc = pc.Index(host=INDEX_HOST)
        
        question = data.get('question', f"Analizza {ticker} con prezzo {price} e range {low}-{high}")
        
        # 2. Embedding con Gemini-2
        emb_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-2:embedContent?key={GOOGLE_API_KEY}"
        res_emb = requests.post(emb_url, json={
            "model": "models/gemini-embedding-2", 
            "content": {"parts": [{"text": question}]}, 
            "output_dimensionality": 768
        }).json()
        
        # 3. Retrieval dei frammenti del libro (Top 3 matches)
        query_v = res_emb['embedding']['values']
        search = index_pc.query(vector=query_v, top_k=3, include_metadata=True)
        context = "\n".join([m.metadata["text"] for m in search.matches])
        
        # 4. Ragionamento con Gemma 3
        gen_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemma-3-27b-it:generateContent?key={GOOGLE_API_KEY}"
        prompt = f"Contesto dal libro di Massimiliano Riolfo: {context}\n\nDati Mercato: {ticker} a {price}, Range 30gg: {low}-{high}\n\nAnalisi CRPM (Calculated Risk and Profit Machines):"
        
        res_gen = requests.post(gen_url, json={"contents": [{"parts": [{"text": prompt}]}]}).json()
        ai_response = res_gen['candidates'][0]['content']['parts'][0]['text']

        return jsonify({
            "ticker": ticker,
            "price": round(price, 2),
            "volatility": round(iv_reale * 100, 2),
            "high": high,
            "low": low,
            "ai_analysis": ai_response,
            "date": "2026-04-30"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

handler = app
