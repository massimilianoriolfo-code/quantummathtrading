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

# Caricamento Variabili Ambiente
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
INDEX_HOST = os.getenv("INDEX_HOST")

def get_now():
    return datetime(2026, 5, 4)

def find_nearest_strike(chain, target):
    strikes = chain['strike'].values
    return strikes[np.abs(strikes - target).argmin()]

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json(silent=True) or {}
    user_query = data.get('query', '')
    if not user_query:
        return jsonify({"response": "Query missing."})
        
    today_str = get_now().strftime('%B %d, %Y')
    
    try:
        # Inizializzazione Pinecone
        pc = Pinecone(api_key=PINECONE_API_KEY)
        index_pc = pc.Index(host=INDEX_HOST)
        
        # RICERCA CON NAMESPACE OBBLIGATORIO
        # query={"inputs": ...} è la sintassi corretta per gli indici Integrated
        search_res = index_pc.search(
            namespace="", 
            query={"inputs": {"text": user_query}}, 
            top_k=5
        )
        
        # Estrazione sicura del contesto
        context_parts = []
        # Trasformiamo l'oggetto in dizionario per evitare errori di attributo
        results = search_res.to_dict() if hasattr(search_res, 'to_dict') else search_res
        hits = results.get('result', {}).get('hits', []) if 'result' in results else results.get('hits', [])
        
        for h in hits:
            text_fragment = h.get('fields', {}).get('text', '')
            if text_fragment:
                context_parts.append(text_fragment)
        
        context = "\n".join(context_parts)
        if not context:
            context = "Focus on general CRPM principles."

        # Chiamata a Google Gemini 1.5 Flash
        gen_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GOOGLE_API_KEY}"
        
        prompt_chat = f"""TODAY IS {today_str}. 
        IDENTITY: CRPM analytical engine. CONTEXT: {context}. QUERY: {user_query}. 
        RULES: English only. Bold titles. Professional tone."""
        
        res_gen = requests.post(gen_url, json={"contents": [{"parts": [{"text": prompt_chat}]}]}, timeout=12).json()
        
        if 'candidates' in res_gen:
            return jsonify({"response": res_gen['candidates'][0]['content']['parts'][0]['text']})
        else:
            # Se Google dà errore, lo mostriamo chiaramente
            error_details = res_gen.get('error', {}).get('message', 'Unknown Google Error')
            return jsonify({"response": f"AI Error: {error_details}"})
            
    except Exception as e:
        # Restituisce l'errore tecnico esatto per la diagnostica finale
        return jsonify({"response": f"TECHNICAL STATUS: {str(e)}"}), 200

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
        price = round(stock.fast_info['last_price'], 2)
        inv_cap = price * 100
        
        expirations = stock.options
        exp_30 = min(expirations, key=lambda x: abs((datetime.strptime(x, '%Y-%m-%d') - (today_dt + timedelta(days=30))).days))
        exp_180 = min(expirations, key=lambda x: abs((datetime.strptime(x, '%Y-%m-%d') - (today_dt + timedelta(days=180))).days))

        chain_30 = stock.option_chain(exp_30)
        chain_180 = stock.option_chain(exp_180)
        iv_val = 0.27
        move = price * iv_val * np.sqrt(30 / 365)

        s_call = find_nearest_strike(chain_30.calls, price + move)
        p_call = round(chain_30.calls[chain_30.calls['strike'] == s_call]['lastPrice'].values[0], 2)
        s_put_30 = find_nearest_strike(chain_30.puts, price - move)
        p_put_30 = round(chain_30.puts[chain_30.puts['strike'] == s_put_30]['lastPrice'].values[0], 2)
        s_put_180 = find_nearest_strike(chain_180.puts, price * 1.02)
        p_put_180 = round(chain_180.puts[chain_180.puts['strike'] == s_put_180]['lastPrice'].values[0], 2)

        def pct(v): return f"{round((v / inv_cap) * 100, 2)}%"
        def f2(v): return "{:.2f}".format(v)

        return jsonify({
            "ticker": ticker_sym, "company": company_name, "price": f2(price), "inv_cap": f2(inv_cap),
            "volatility": 27.0, "high": s_call, "low": s_put_30, "date": today_dt.strftime('%B %d, %Y'),
            "machines": [
                {"name": "Machine 1: Long Call", "action": "BUY CALL", "strike": s_call, "expiry": exp_30, "prem": f2(p_call), "max_profit": "Unlimited", "max_risk": f"${f2(p_call*100)}", "comment": "Bullish."},
                {"name": "Machine 2: Short Put", "action": "SELL PUT", "strike": s_put_30, "expiry": exp_30, "prem": f2(p_put_30), "max_profit": f"${f2(p_put_30*100)}", "max_risk": f"${f2(round((s_put_30 - p_put_30)*100, 2))}", "comment": "Income."},
                {"name": "Machine 3: Married Put", "action": "BUY PUT", "strike": s_put_180, "expiry": exp_180, "prem": f2(p_put_180), "max_profit": "Unlimited", "max_risk": f"${f2(round((p_put_180 + (price - s_put_180))*100, 2))}", "comment": "Hedging."},
                {"name": "Machine 4: Covered Call", "action": "SELL CALL", "strike": s_call, "expiry": exp_30, "prem": f2(p_call), "max_profit": f"${f2(round((p_call + (s_call - price))*100, 2))}", "max_risk": "Stock Ownership", "comment": "Yield."},
                {"name": "Machine 5: Combined", "action": "PUT & CALL", "strike": f"{s_put_30}/{s_call}", "expiry": exp_30, "prem": f2(round(p_call + p_put_30, 2)), "max_profit": "Yield", "max_risk": "Reduced Basis", "comment": "Instability."}
            ]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

handler = app
