// api/chat.js
export default async function handler(req, res) {
  const { question } = req.body;

  // Qui inseriamo il "Prompt Maestro" che definisce la tua autorità
  const systemPrompt = "Sei l'assistente esperto del Prof. Riolfo. Rispondi in modo tecnico e matematico basandoti sul framework CRPM. Non dare consigli finanziari.";

  const response = await fetch('https://api.openai.com/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${process.env.OPENAI_API_KEY}`
    },
    body: JSON.stringify({
      model: "gpt-4",
      messages: [
        { role: "system", content: systemPrompt },
        { role: "user", content: question }
      ]
    })
  });

  const data = await response.json();
  res.status(200).json({ answer: data.choices[0].message.content });
}
