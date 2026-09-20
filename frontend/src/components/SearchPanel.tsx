import { useState } from "react";
import { ApiError, search, type SearchResultItem } from "../api";

export function SearchPanel() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSearch(event: React.FormEvent) {
    event.preventDefault();
    if (!query.trim()) return;
    setSearching(true);
    setError(null);
    try {
      const response = await search(query.trim());
      setResults(response.results);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Search failed.");
    } finally {
      setSearching(false);
    }
  }

  return (
    <section className="panel" aria-label="Search messages">
      <h2>Search</h2>
      <form onSubmit={handleSearch}>
        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search your messages…"
          aria-label="Search query"
        />
        <button type="submit" disabled={searching || !query.trim()}>
          {searching ? "Searching…" : "Search"}
        </button>
      </form>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <ul className="results" data-testid="search-results">
        {results.map((item) => (
          <li key={item.message.id} className="result-item">
            <div className="result-header">
              <strong>{item.message.subject ?? "(no subject)"}</strong>
              <span className="score">score {item.score.toFixed(2)}</span>
            </div>
            <div className="result-meta">
              {item.message.sender} · {new Date(item.message.timestamp).toLocaleString()}
            </div>
            <p className="result-snippet">{item.message.text.slice(0, 220)}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
