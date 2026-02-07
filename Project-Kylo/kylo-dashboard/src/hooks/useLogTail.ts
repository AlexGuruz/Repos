import { useEffect, useState, useRef } from "react";

export function useLogTail(instanceId: string | null, lines: number = 1000) {
  const [logLines, setLogLines] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (!instanceId) {
      setLogLines([]);
      return;
    }

    const fetchLogs = async () => {
      setLoading(true);
      try {
        const result = await window.electronAPI.readLogTail(instanceId, lines);
        if (result.success && result.lines) {
          setLogLines(result.lines);
          setError(null);
        } else {
          setError(result.error || "Failed to read logs");
        }
      } catch (e) {
        setError(String(e));
      } finally {
        setLoading(false);
      }
    };

    fetchLogs();
    intervalRef.current = setInterval(fetchLogs, 1000); // Poll every 1s for new log lines

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [instanceId, lines]);

  return { logLines, loading, error };
}

