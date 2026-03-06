export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Metodo non consentito' });
  }

  const apiKey = process.env.GOOGLE_GENAI_API_KEY;
  if (!apiKey) {
    return res.status(500).json({ error: 'Errore: Chiave API non configurata su Vercel.' });
  }

  const { question } = req.body;
  const systemInstruction = "Sei l'assistente esperto del Prof. Riolfo. Rispondi in modo tecnico basandoti sul framework CRPM. Non dare consigli finanziari.";

  try {
    const response = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent?key=${apiKey}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        contents: [{
          parts: [{ text: `${systemInstruction}\n\nDomanda: ${question}` }]
        }]
      })
    });

    const data = await response.json();
    
    // Debug per evitare l'errore 'undefined'
    if (data.candidates && data.candidates[0].content && data.candidates[0].content.parts) {
      const answer = data.candidates[0].content.parts[0].text;
      return res.status(200).json({ answer });
    } else {
      console.error("Risposta inattesa da Google:", data);
      return res.status(500).json({ error: "Risposta non valida dall'AI." });
    }

  } catch (error) {
    return res.status(500).json({ error: 'Errore di connessione al server AI.' });
  }
}
