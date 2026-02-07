import React from "react";
import { InstanceRow } from "../types/kylo";
import { StatusBadge } from "./StatusBadge";

interface InstanceListProps {
  instances: InstanceRow[];
  selectedInstanceId: string | null;
  onSelect: (instanceId: string) => void;
}

export const InstanceList: React.FC<InstanceListProps> = ({
  instances,
  selectedInstanceId,
  onSelect,
}) => {
  const getStatus = (instance: InstanceRow): "running" | "paused" | "error" | "stopped" => {
    if (instance.last_error) return "error";
    if (instance.last_post_ok === "false") return "error";
    if (instance.last_tick_at) return "running";
    return "stopped";
  };

  return (
    <div className="space-y-2">
      {instances.length === 0 ? (
        <div className="text-gray-400 p-4 text-center">No instances found</div>
      ) : (
        instances.map((instance) => {
          const status = getStatus(instance);
          const isSelected = selectedInstanceId === instance.instance_id;
          return (
            <div
              key={instance.instance_id}
              onClick={() => onSelect(instance.instance_id)}
              className={`p-3 border rounded cursor-pointer transition-colors ${
                isSelected
                  ? "border-blue-500 bg-gray-800"
                  : "border-gray-700 hover:border-gray-600"
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="font-semibold text-gray-100">{instance.instance_id}</span>
                <StatusBadge status={status} />
              </div>
              <div className="text-sm text-gray-400 space-y-1">
                <div>Last tick: {instance.last_tick_at || "Never"}</div>
                <div>Cells written: {instance.cells_written}</div>
                {instance.last_error && (
                  <div className="text-red-400 truncate">{instance.last_error}</div>
                )}
              </div>
            </div>
          );
        })
      )}
    </div>
  );
};

