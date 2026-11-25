/** Default background sync interval. Owner asked for 10 seconds. */
export const DEFAULT_SYNC_INTERVAL_MS = 10_000;

/** `0` disables background sync. Invalid or negative values fall back to the default. */
export function resolveSyncInterval(raw: string | undefined): number {
  if (raw === undefined) return DEFAULT_SYNC_INTERVAL_MS;
  if (raw.trim() === "0") return 0;
  if (!/^[1-9][0-9]*$/u.test(raw.trim())) return DEFAULT_SYNC_INTERVAL_MS;
  const value = Number(raw);
  return Number.isSafeInteger(value) ? value : DEFAULT_SYNC_INTERVAL_MS;
}

export interface PeriodicSyncOptions {
  intervalMs: number;
  sync: () => Promise<unknown>;
  onError?: (error: unknown) => void;
}

/**
 * Background sync between conversation turns.
 *
 * The workbench is poll-only by contract (no long connection, no event stream), so
 * without this the local log would only reach the server when a turn starts. Runs are
 * serialized: a slow sync never overlaps the next tick, and a concurrent turn-triggered
 * sync surfaces as a "busy" error that is swallowed rather than treated as failure.
 */
export function startPeriodicSync(options: PeriodicSyncOptions): () => void {
  const { intervalMs, sync, onError } = options;
  if (!Number.isSafeInteger(intervalMs) || intervalMs <= 0) return () => {};
  let inFlight = false, stopped = false;
  const timer = setInterval(() => {
    if (stopped || inFlight) return;
    inFlight = true;
    void sync()
      .catch(error => { try { onError?.(error); } catch { /* diagnostics must not throw */ } })
      .finally(() => { inFlight = false; });
  }, intervalMs);
  // A background helper must never keep the host process alive on its own.
  timer.unref?.();
  return () => { stopped = true; clearInterval(timer); };
}
