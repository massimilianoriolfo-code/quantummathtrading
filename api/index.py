import yfinance as yf
import numpy as np
import requests
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

# Recupero credenziali
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
INDEX_HOST = os.getenv("INDEX_HOST")

def get_now():
    return datetime(2026, 5, 4)

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json(silent=True) or {}
    user_query = data.get('query', '')
    if not user_query: return jsonify({"response": "Inserisci una domanda."})
    
    try:
        # 1. ACCESSO DIRETTO ALLA TUA CONOSCENZA (PINECONE REST)
        # Puliamo l'host per sicurezza
        host = INDEX_HOST.strip().replace("https://", "").replace("http://", "").rstrip("/")
        
        # Proviamo a interrogare il libro nel namespace principale o in quello dedicato
        context = ""
        for ns in ["book-content", ""]:
            url = f"https://{host}/records/namespaces/{ns}/search" if ns else f"https://{host}/records/search"
            try:
                res = requests.post(url, 
                    headers={"Api-Key": PINECONE_API_KEY, "Content-Type": "application/json", "X-Pinecone-Api-Version": "2024-10"},
                    json={"query": {"inputs": {"text": user_query}, "top_k": 5}},
                    timeout=5
                )
                if res.status_code == 200:
                    hits = res.json().get('result', {}).get('hits', [])
                    for h in hits:
                        f = h.get('fields', {})
                        # Rastrella ogni campo testuale che contiene pezzi del libro
                        for k in f:
                            if isinstance(f[k], str) and len(f[k]) > 40:
                                context += f"\n{f[k]}"
                if context: break
            except: continue

        # 2. COMANDO ALL'AI: USA SOLO IL LIBRO DI MASSIMILIANO
        gen_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GOOGLE_API_KEY}"
        
        if not context:
            prompt = f"L'utente chiede: {user_query}. Non ho trovato frammenti specifici nel libro. Rispondi basandoti esclusivamente sulla metodologia CRPM (Calculated Risk and Profit Machines)."
        else:
            prompt = f"Usa ESCLUSIVAMENTE questo contesto dal libro di Massimiliano Riolfo per rispondere:\n{context}\n\nDomanda: {user_query}\nRegole: Risposta professionale, solo inglese, titoli in grassetto."

        ai_res = requests.post(gen_url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=10).json()
        
        if 'candidates' in ai_res:
            return jsonify({"response": ai_res['candidates'][0]['content']['parts'][0]['text']})
        return jsonify({"response": "L'AI non è riuscita a generare una risposta. Riprova."})

    except Exception as e:
        return jsonify({"response": f"Errore tecnico: {str(e)}"}), 200

@app.route('/api/index', methods=['POST', 'GET'])
def index():
    # Simulatore Prezzi Blindato per evitare i 'NaN' delle immagini
    t = (request.get_json(silent=True) or {}).get('ticker') or request.args.get('ticker', 'AAPL')
    try:
        stock = yf.Ticker(t.upper())
        price = stock.fast_info['last_price']
        inv_cap = price * 100
        return jsonify({
            "ticker": t.upper(),
            "company": stock.info.get('longName', t.upper()),
            "price": f"{price:.2f}",
            "inv_cap": f"{inv_cap:.2f}",
            "date": "May 04, 2026",
            "machines": [] # Per ora vuote per garantire il caricamento base
        })
    except:
        return jsonify({"error": "Errore ticker"}), 500

handler = app
