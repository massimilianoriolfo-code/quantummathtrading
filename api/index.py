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

# Credenziali ambiente
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
INDEX_HOST = os.getenv("INDEX_HOST")

# --- ENDPOINT 1: CHAT LIBERA CON IL LIBRO (RAG) ---
@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_query = data.get('query')
    if not user_query: return jsonify({"error": "Query missing"}), 400
    
    try:
        pc = Pinecone(api_key=PINECONE_API_KEY)
        index_pc = pc.Index(host=INDEX_HOST)
        
        # Embedding della domanda utente
        res_emb = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-2:embedContent?key={GOOGLE_API_KEY}", 
            json={"model": "models/gemini-embedding-2", "content": {"parts": [{"text": user_query}]}, "output_dimensionality": 768}).json()
        query_v = res_emb['embedding']['values']
        
        # Recupero contesto dal database vettoriale
        search = index_pc.query(vector=query_v, top_k=10, include_metadata=True)
        context = "\n".join([m.metadata["text"] for m in search.matches])
        
        gen_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemma-3-27b-it:generateContent?key={GOOGLE_API_KEY}"
        
        prompt_chat = f"""You are the expert Assistant for the book 'The Essence of Quantitative Math Trading with Options'.
        CONTEXT FROM BOOK: {context}
        USER QUESTION: {user_query}
        
        INSTRUCTIONS:
        - Use ONLY the provided context and CRPM principles.
        - If asked about protecting a position, explain Machine 3 (Married Put) as: Long Stock + Put Option.
        - For Machine 3, emphasize: In-The-Money (ITM) strike and 6-month+ expiry to mitigate Theta decay.
        - Mention that Machine 3 has UNLIMITED profit potential.
        - Tone: Clinical, Professional, Quantitative. No financial advice disclaimer at the end."""
        
        res_gen = requests.post(gen_url, json={"contents": [{"parts": [{"text": prompt_chat}]}]}).json()
        return jsonify({"response": res_gen['candidates'][0]['content']['parts'][0]['text']})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- ENDPOINT 2: SIMULATORE E ANALISI MACCHINE ---
@app.route('/api/index', methods=['POST', 'GET'])
def index():
    data = request.get_json(silent=True) or {}
    t = data.get('ticker') or request.args.get('ticker')
    if not t: return jsonify({"error": "Ticker missing"}), 400
    ticker_sym = t.upper()

    try:
        stock = yf.Ticker(ticker_sym)
        company_name = stock.info.get('longName', ticker_sym)
        price = stock.fast_info['last_price']
        
        # Gestione Volatilità Implicita con fallback
        expirations = stock.options
        if expirations:
            target_date = datetime.now() + timedelta(days=30)
            closest_exp = min(expirations, key=lambda x: abs((datetime.strptime(x, '%Y-%m-%d') - target_date).days))
            opt_chain = stock.option_chain(closest_exp)
            iv_val = (opt_chain.calls.iloc[(opt_chain.calls['strike'] - price).abs().idxmin()]['impliedVolatility'] + 
                      opt_chain.puts.iloc[(opt_chain.puts['strike'] - price).abs().idxmin()]['impliedVolatility']) / 2
        else:
            iv_val = 0

        if iv_val <= 0:
            hist = stock.history(period="1mo")
            iv_val = np.log(hist['Close'] / hist['Close'].shift(1)).std() * np.sqrt(252) if not hist.empty else 0.25

        # Analisi Tattica (30 giorni)
        move = price * iv_val * np.sqrt(30 / 365)
        high, low = round(price + move, 2), round(price - move, 2)
        
        # Parametri Machine 3 Strategica (6 mesi)
        m3_strike = round(price * 1.02, 2)
        m3_expiry = (datetime.now() + timedelta(days=180)).strftime('%B %Y')
        est_premium = price * 0.08
        max_risk_monetary = round((est_premium - (m3_strike - price)) * 100, 2)
        max_risk_pct = round((max_risk_monetary / (price * 100)) * 100, 2)

        gen_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemma-3-27b-it:generateContent?key={GOOGLE_API_KEY}"
        
        prompt = f"""
        STRICT INSTRUCTION: Respond in English. Use exact CRPM Machine definitions from the methodology.
        DATA: {company_name} ({ticker_sym}) @ {round(price, 2)} | 1-Sigma: {low}-{high}
        
        CORE STRATEGIES TO DETAIL:
        1. Machine 1: Long Call Based (Target: Bullish. Strike: {high}. Expiry: 30 days). Profit: Unbounded.
        2. Machine 2: Short Put Based (Target: Neutral/Bullish. Strike: {low}. Expiry: 30 days). Profit: Limited to Premium.
        3. Machine 3: Married Put Based (Target: Strategic Protection. Action: Long 100 Shares + BUY Put Option. Strike: {m3_strike} (ITM). Expiry: {m3_expiry} (6 months). Profit: UNLIMITED. Risk: {max_risk_pct}%).
        4. Machine 4: Covered Call Based (Target: Yield. Action: Long 100 Shares + SELL Call Option. Strike: {high}. Expiry: 30 days). Profit: Capped.
        5. Machine 5: Assigned Short Put + Covered Call (Target: Cost Basis Reduction).

        FORMAT: Technical tables for each Machine. Highlight UNLIMITED profit for Machine 3.
        """
        
        res_gen = requests.post(gen_url, json={"contents": [{"parts": [{"text": prompt}]}]}).json()
        ai_analysis_result = res_gen['candidates'][0]['content']['parts'][0]['text']

        return jsonify({
            "ticker": ticker_sym, "company": company_name, "price": round(price, 2), 
            "volatility": round(iv_val*100,2), "high": high, "low": low,
            "ai_analysis": ai_analysis_result, "m3_risk_pct": max_risk_pct, "date": "2026-05-04"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

handler = app
