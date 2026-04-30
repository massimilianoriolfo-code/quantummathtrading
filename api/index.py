# --- PROMPT QUANTITATIVO AVANZATO ---
prompt = f"""
STRICT INSTRUCTION: Respond EXCLUSIVELY in English. Use a technical, engineering-style tone.
Act as the CRPM Execution Engine for Massimiliano Riolfo. 

ANALYSIS TARGET: {ticker} @ {price}
30-DAY PARAMETERS: 1-Sigma Range [{low} - {high}] | IV: {iv_pct}%

Using the methodology from Chapter 8 (Calculated Risk and Profit Machines), generate an operational setup for each machine:

1. Machine 1: Long Call Based (Para 8.1)
   - Target Strike: Based on {high}. Discuss delta exposure and risk of total premium loss.
2. Machine 2: Short Put Based (Para 8.2)
   - Target Strike: Safety margin relative to {low}. Analyze the "Calculated Profit" vs assignment risk.
3. Machine 3: Married Put Based (Para 8.3)
   - Setup: Synthetic floor placement. Calculate the "Cost of Insurance" for the {ticker} position.
4. Machine 4: Covered Call Based (Para 8.4)
   - Setup: Income generation. Strike selection at the upper {high} boundary to maximize Theta decay[cite: 1].
5. Machine 5: Assigned Short Put + Covered Call (Para 8.6)
   - Strategy: The "Wheel" transition. Managing cost basis after assignment and strike selection for the Call leg[cite: 1].

MANDATORY: 
- Refer to price levels {low} and {high} as hard boundaries for strike selection[cite: 1].
- Maintain focus on "Calculated Risk" and "Profit Machines" as disciplined processes, not guesses[cite: 1].
- NO general advice. ONLY technical execution logic.

CONTEXT FROM BOOK:
{context}
"""
