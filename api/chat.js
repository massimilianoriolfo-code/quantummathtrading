export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const apiKey = process.env.GOOGLE_GENAI_API_KEY;
  const { question } = req.body;

  // Il tuo Prompt Maestro (ancora generico, in attesa della tua definizione)
  const systemInstruction = "Sei l'assistente esperto del Prof. Riolfo. Rispondi in modo tecnico e sintetico sul framework CRPM. Non dare consigli finanziari.";

  try {
    // Aggiornato il modello a gemini-1.5-flash per maggiore compatibilità
    const response = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${apiKey}`, {
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
       console.error("Errore Google API:", data.error);
       return res.status(500).json({ answer: "Errore API: " + data.error.message });
    }

    if (data.candidates && data.candidates[0].content) {
      const answer = data.candidates[0].content.parts[0].text;
      return res.status(200).json({ answer });
    } else {
      return res.status(500).json({ answer: "Risposta non ricevuta correttamente dall'AI." });
    }

  } catch (error) {
    return res.status(500).json({ answer: "Errore di connessione al backend." });
  }
}
