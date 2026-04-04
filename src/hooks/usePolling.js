import { useState, useEffect, useCallback, useRef } from 'react';

/**
 * Polls a fetch function on a set interval.
 *
 * @param {Function} fetchFn  - async function that returns data.
 *                              Receives an AbortSignal as its first argument so
 *                              callers can cancel in-flight Axios requests via
 *                              `{ signal }` in the request config.
 * @param {number}   interval - polling interval in ms (default 30s)
 * @param {boolean}  enabled  - set false to pause polling
 */
export function usePolling(fetchFn, interval = 30000, enabled = true) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(enabled);
  const fetchRef = useRef(fetchFn);
  fetchRef.current = fetchFn;

  const refresh = useCallback(async (signal) => {
    try {
      setError(null);
      const result = await fetchRef.current(signal);
      // Guard: don't update state if the component unmounted while we awaited
      if (signal?.aborted) return;
      setData(result);
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.name === 'AbortError' || signal?.aborted) {
        // Request was intentionally cancelled — ignore
        return;
      }
      setError(err?.response?.data?.detail || err?.message || 'Request failed');
    } finally {
      if (!signal?.aborted) setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!enabled) return;

    // Each effect run gets its own AbortController so in-flight requests from
    // the previous run (e.g. before a prop change or unmount) are cancelled.
    const controller = new AbortController();
    const { signal } = controller;

    refresh(signal); // initial fetch

    const id = setInterval(() => refresh(signal), interval);

    return () => {
      controller.abort();   // cancel any in-flight fetch
      clearInterval(id);
    };
  }, [refresh, interval, enabled]);

  return { data, error, isLoading, refresh };
}
