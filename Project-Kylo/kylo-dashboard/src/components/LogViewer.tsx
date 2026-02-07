import React, { useEffect, useRef, useState } from "react";
import { useLogTail } from "../hooks/useLogTail";

interface LogViewerProps {
  instanceId: string | null;
}

export const LogViewer: React.FC<LogViewerProps> = ({ instanceId }) => {
  const { logLines, loading, error } = useLogTail(instanceId);
  const [searchTerm, setSearchTerm] = useState("");
  const [autoScroll, setAutoScroll] = useState(true);
  const logEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (autoScroll && logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logLines, autoScroll]);

  const filteredLines = searchTerm
    ? logLines.filter((line) => line.toLowerCase().includes(searchTerm.toLowerCase()))
    : logLines;

  if (!instanceId) {
    return (
      <div className="p-4 text-gray-400 text-center">Select an instance to view logs</div>
    );
  }

  if (error) {
    return <div className="p-4 text-red-400">Error: {error}</div>;
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex gap-2 p-2 border-b border-gray-700">
        <input
          type="text"
          placeholder="Search logs..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="flex-1 px-3 py-1 bg-gray-800 text-gray-100 border border-gray-700 rounded"
        />
        <label className="flex items-center gap-2 text-gray-300">
          <input
            type="checkbox"
            checked={autoScroll}
            onChange={(e) => setAutoScroll(e.target.checked)}
          />
          Auto-scroll
        </label>
      </div>
      <div className="flex-1 overflow-auto bg-gray-900 p-2 font-mono text-sm">
        {loading && logLines.length === 0 ? (
          <div className="text-gray-400">Loading logs...</div>
        ) : (
          filteredLines.map((line, idx) => {
            const isError = line.toLowerCase().includes("error") || line.toLowerCase().includes("exception");
            const isWarning = line.toLowerCase().includes("warning");
            return (
              <div
                key={idx}
                className={`${isError ? "text-red-400" : isWarning ? "text-yellow-400" : "text-gray-300"}`}
              >
                {line || " "}
              </div>
            );
          })
        )}
        <div ref={logEndRef} />
      </div>
    </div>
  );
};

