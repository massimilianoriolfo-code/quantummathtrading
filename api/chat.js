export default async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });

  const apiKey = process.env.GOOGLE_GENAI_API_KEY;
  const { question } = req.body;

  try {
    // URL ultra-semplificato: puntiamo direttamente al modello flash
    const apiURL = `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${apiKey}`;
    
    const response = await fetch(apiURL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        contents: [{ parts: [{ text: question }] }]
      })
    });

    const data = await response.json();

    if (data.error) {
       return res.status(200).json({ answer: "Errore tecnico: " + data.error.message });
    }

    const answer = data.candidates[0].content.parts[0].text;
    return res.status(200).json({ answer });

  } catch (error) {
    return res.status(200).json({ answer: "Errore di rete." });
  }
}
