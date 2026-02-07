import React from "react";

interface StatusBadgeProps {
  status: "running" | "paused" | "error" | "stopped";
  label?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, label }) => {
  const colors = {
    running: "bg-green-600 text-white",
    paused: "bg-yellow-600 text-white",
    error: "bg-red-600 text-white",
    stopped: "bg-gray-600 text-white",
  };

  return (
    <span className={`px-2 py-1 rounded text-xs font-semibold ${colors[status]}`}>
      {label || status.toUpperCase()}
    </span>
  );
};

