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

# --- CONFIGURAZIONE SICURA ---
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
        price = stock.fast_info['last_price']
        
        # --- MOTORE QUANTITATIVO ---
        expirations = stock.options
        target_date = datetime.now() + timedelta(days=30)
        closest_exp = min(expirations, key=lambda x: abs((datetime.strptime(x, '%Y-%m-%d') - target_date).days))
        opt_chain = stock.option_chain(closest_exp)
        
        iv_reale = (opt_chain.calls.iloc[(opt_chain.calls['strike'] - price).abs().idxmin()]['impliedVolatility'] + 
                    opt_chain.puts.iloc[(opt_chain.puts['strike'] - price).abs().idxmin()]['impliedVolatility']) / 2
        
        move = price * iv_reale * np.sqrt(30 / 365)
        high, low = round(price + move, 2), round(price - move, 2)

        # --- LOGICA AI PROFESSIONALE (Knowledge Base) ---
        pc = Pinecone(api_key=PINECONE_API_KEY)
        index_pc = pc.Index(host=INDEX_HOST)
        
        # Query mirata per estrarre le definizioni delle Macchine dal libro
        search_query = f"Definizione operativa delle cinque macchine CRPM applicate a {ticker} con range {low}-{high}"
        
        emb_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-2:embedContent?key={GOOGLE_API_KEY}"
        res_emb = requests.post(emb_url, json={
            "model": "models/gemini-embedding-2", 
            "content": {"parts": [{"text": search_query}]}, 
            "output_dimensionality": 768
        }).json()
        
        # Aumentiamo top_k a 10 per assicurarci di catturare tutte le definizioni delle macchine
        query_v = res_emb['embedding']['values']
        search = index_pc.query(vector=query_v, top_k=10, include_metadata=True)
        context = "\n".join([m.metadata["text"] for m in search.matches])
        
        # --- PROMPT RIGOROSO: 5 MACCHINE OPERATIVE ---
        gen_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemma-3-27b-it:generateContent?key={GOOGLE_API_KEY}"
        
        prompt = f"""
        Sei l'analista IA ufficiale di Massimiliano Riolfo. Analizza il sottostante {ticker} (Prezzo: {price}) 
        utilizzando i parametri quantitativi calcolati: Range 1-Sigma a 30gg tra {low} e {high}.

        COMPITI TASSATIVI:
        1. Identifica nel CONTESTO fornito le definizioni esatte delle CINQUE MACCHINE CRPM.
        2. Per ogni Macchina (dalla n. 1 alla n. 5), spiega come operare con le OPZIONI su {ticker} basandoti sulla logica del libro.
        3. Sii sintetico, tecnico e rigoroso. Evita commenti discorsivi o introduzioni.
        
        CONTESTO DAL LIBRO:
        {context}

        STRUTTURA OUTPUT:
        - Analisi Volatilità: Commento tecnico su IV e perimetro operativo.
        - Le 5 Macchine CRPM su {ticker}: (Elenco puntato con applicazione pratica delle opzioni).
        - Nota Disciplinare: Massima brevità basata sulla logica del rischio calcolato.
        """
        
        res_gen = requests.post(gen_url, json={"contents": [{"parts": [{"text": prompt}]}]}).json()
        ai_response = res_gen['candidates'][0]['content']['parts'][0]['text']

        return jsonify({
            "ticker": ticker,
            "price": round(price, 2),
            "volatility": round(iv_reale * 100, 2),
            "high": high,
            "low": low,
            "ai_analysis": ai_analysis, # Corretto nome variabile per coerenza frontend
            "date": "2026-05-01"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

handler = app
