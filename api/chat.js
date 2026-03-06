export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const apiKey = process.env.GOOGLE_GENAI_API_KEY;
  const { question } = req.body;

  const systemInstruction = "Sei l'assistente esperto del Prof. Riolfo. Rispondi in modo tecnico e sintetico sul framework CRPM. Non dare consigli finanziari.";

  try {
    // URL semplificato e modello 'gemini-1.5-flash' (senza alias latest per ora)
    const apiURL = `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${apiKey}`;
    
    const response = await fetch(apiURL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        contents: [{
          parts: [{ text: `${systemInstruction}\n\nUser Question: ${question}` }]
        }]
      })
    });

    const data = await response.json();

    if (data.error) {
       // Se l'errore persiste, stampiamo esattamente cosa vuole Google
       return res.status(200).json({ answer: "Errore API di Google: " + data.error.message });
    }

    if (data.candidates && data.candidates[0].content) {
      const answer = data.candidates[0].content.parts[0].text;
      return res.status(200).json({ answer });
    } else {
      return res.status(200).json({ answer: "Connessione riuscita, ma risposta vuota." });
    }

  } catch (error) {
    return res.status(200).json({ answer: "Errore critico backend: " + error.message });
  }
}
