
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
    if not user_query: return jsonify({"response": "Missing query."})
    
    try:
        # 1. ESTRAZIONE FORZATA DALLA TUA CONOSCENZA (PINECONE)
        host = INDEX_HOST.strip().replace("https://", "").replace("http://", "").rstrip("/")
        # Proviamo i due namespace più probabili che abbiamo usato nei test
        namespaces = ["book-content", "default", ""]
        context = ""
        
        headers = {
            "Api-Key": PINECONE_API_KEY,
            "Content-Type": "application/json",
            "X-Pinecone-Api-Version": "2024-10"
        }

        for ns in namespaces:
            pine_url = f"https://{host}/records/namespaces/{ns}/search" if ns else f"https://{host}/records/search"
            try:
                res = requests.post(pine_url, headers=headers, json={"query": {"inputs": {"text": user_query}, "top_k": 10}}, timeout=5)
                if res.status_code == 200:
                    hits = res.json().get('result', {}).get('hits', [])
                    for h in hits:
                        f = h.get('fields', {})
                        # Prendiamo tutto ciò che è testo lungo (il tuo libro)
                        for k in f:
                            if isinstance(f[k], str) and len(f[k]) > 50:
                                context += f"\n{f[k]}"
                if context: break # Se abbiamo trovato il libro, fermiamoci
            except: continue

        # 2. COMANDO AUTORITARIO A GEMINI
        gen_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GOOGLE_API_KEY}"
        
        # Se il contesto è vuoto, lo segnaliamo esplicitamente
        if not context:
            return jsonify({"response": "ATTENZIONE: Non riesco a leggere il libro nel database. Verifica il nome del Namespace su Pinecone."})

        prompt = f"""DOCUMENTO DI RIFERIMENTO (IL TUO LIBRO):
        {context}
        
        DOMANDA UTENTE: {user_query}
        
        ISTRUZIONI: Rispondi ESCLUSIVAMENTE usando le informazioni del documento sopra. 
        Se la risposta non è nel testo, dici 'Non trovo questa informazione nel mio libro'.
        Lingua: Inglese. Titoli in grassetto."""

        res_ai = requests.post(gen_url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=10).json()
        
        if 'candidates' in res_ai:
            return jsonify({"response": res_ai['candidates'][0]['content']['parts'][0]['text']})
        return jsonify({"response": "Errore nella generazione della risposta."})

    except Exception as e:
        return jsonify({"response": f"Errore tecnico: {str(e)}"}), 200

@app.route('/api/index', methods=['POST', 'GET'])
def index():
    # Simulatore Prezzi Standard
    t = (request.get_json(silent=True) or {}).get('ticker') or request.args.get('ticker', 'SPX')
    try:
        stock = yf.Ticker(t.upper())
        price = stock.fast_info['last_price']
        return jsonify({"ticker": t.upper(), "price": f"{price:.2f}", "date": "May 04, 2026", "machines": []})
    except:
        return jsonify({"error": "Ticker error"}), 500

handler = app
