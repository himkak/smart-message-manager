import { useState } from "react";
import { ApiError, askChat, type ChatResponse } from "../api";

export function ChatPanel() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<ChatResponse | null>(null);
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleAsk(event: React.FormEvent) {
    event.preventDefault();
    if (!question.trim()) return;
    setAsking(true);
    setError(null);
    try {
      setAnswer(await askChat(question.trim()));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Ask failed.");
    } finally {
      setAsking(false);
    }
  }

  return (
    <section className="panel" aria-label="Ask your messages">
      <h2>Ask</h2>
      <form onSubmit={handleAsk}>
        <input
          type="text"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Ask a question about your messages…"
          aria-label="Question"
        />
        <button type="submit" disabled={asking || !question.trim()}>
          {asking ? "Asking…" : "Ask"}
        </button>
      </form>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {answer && (
        <div className="answer" data-testid="chat-answer">
          <span
            className={`pill ${answer.has_evidence ? "pill-connected" : "pill-disconnected"}`}
            data-testid="evidence-badge"
          >
            {answer.has_evidence ? "Evidence found" : "No evidence"}
          </span>
          <p>{answer.answer}</p>
          {answer.citations.length > 0 && (
            <ul className="citations" data-testid="citations">
              {answer.citations.map((citation, index) => (
                <li key={`${citation.message_id}-${index}`}>
                  <span className="citation-source">{citation.source}</span>
                  <blockquote>{citation.quote}</blockquote>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}
