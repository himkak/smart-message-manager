import { useEffect, useState } from "react";
import { getSyncStatus, startGoogleAuthUrl, syncGmail, type SyncStatus } from "../api";

export function StatusBar() {
  const [status, setStatus] = useState<SyncStatus | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);

  async function refresh() {
    try {
      setStatus(await getSyncStatus());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load status.");
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function handleSync() {
    setSyncing(true);
    setError(null);
    setSyncMessage(null);
    try {
      const result = await syncGmail();
      setSyncMessage(
        `Synced ${result.messages_processed} message(s), indexed ${result.indexed} for search.`
      );
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sync failed.");
    } finally {
      setSyncing(false);
    }
  }

  return (
    <section className="status-bar" aria-label="Gmail connection status">
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {status?.connected ? (
        <>
          <span data-testid="connection-state" className="pill pill-connected">
            Connected as {status.email}
          </span>
          <button type="button" onClick={handleSync} disabled={syncing}>
            {syncing ? "Syncing…" : "Sync Gmail"}
          </button>
          {syncMessage && <span className="hint">{syncMessage}</span>}
        </>
      ) : (
        <>
          <span data-testid="connection-state" className="pill pill-disconnected">
            Not connected
          </span>
          <a className="button-link" href={startGoogleAuthUrl()}>
            Connect Gmail
          </a>
        </>
      )}
    </section>
  );
}
