export default async function handler(req, res) {
  // Gestione CORS e metodo
  if (req.method === 'OPTIONS') {
    res.status(200).end();
    return;
  }
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Metodo non consentito' });
  }

  const { question } = req.body;
  const apiKey = process.env.GOOGLE_GENAI_API_KEY;

  if (!apiKey) {
    console.error("ERRORE: API Key non configurata su Vercel.");
    return res.status(500).json({ error: "Configurazione server incompleta." });
  }

  const systemInstruction = "Sei l'assistente del Prof. Riolfo. Rispondi in modo tecnico e matematico sul framework CRPM. Sii breve.";

  try {
    const apiURL = `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent?key=${apiKey}`;
    
    const response = await fetch(apiURL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        contents: [{
          parts: [{ text: `${systemInstruction}\n\nDomanda: ${question}` }]
        }]
      })
    });

    const data = await response.json();

    if (!response.ok) {
      console.error("Errore API Google:", data);
      return res.status(500).json({ error: "Errore dall'API di Google." });
    }

    const answer = data.candidates[0].content.parts[0].text;
    return res.status(200).json({ answer });

  } catch (error) {
    console.error("Errore generico backend:", error);
    return res.status(500).json({ error: "Errore interno del server." });
  }
}
