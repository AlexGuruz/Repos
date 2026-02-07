import { useEffect, useState } from "react";

export function useFileWatcher<T>(
  readFn: () => Promise<{ success: boolean; data?: T; error?: string }>,
  onUpdate?: (data: T) => void
): { data: T | null; error: string | null; loading: boolean } {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    setLoading(true);
    try {
      const result = await readFn();
      if (result.success && result.data) {
        setData(result.data);
        setError(null);
        onUpdate?.(result.data);
      } else {
        setError(result.error || "Failed to read file");
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 2000); // Poll every 2s as fallback
    return () => clearInterval(interval);
  }, []);

  return { data, error, loading };
}

