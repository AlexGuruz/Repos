import React from "react";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from "chart.js";
import { Line, Bar } from "react-chartjs-2";
import { InstanceRow } from "../types/kylo";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend
);

interface MetricsGraphProps {
  company: string;
  instances: InstanceRow[];
}

export const MetricsGraph: React.FC<MetricsGraphProps> = ({ company, instances }) => {
  const tickDurationData = {
    labels: instances.map((i) => i.instance_id),
    datasets: [
      {
        label: "Last Tick Duration (ms)",
        data: instances.map((i) => {
          // Parse from heartbeat if available, otherwise use placeholder
          return 0; // TODO: Fetch from heartbeat.json
        }),
        borderColor: "rgb(59, 130, 246)",
        backgroundColor: "rgba(59, 130, 246, 0.1)",
      },
    ],
  };

  const postingSuccessData = {
    labels: instances.map((i) => i.instance_id),
    datasets: [
      {
        label: "Success",
        data: instances.map((i) => (i.last_post_ok === "true" ? 1 : 0)),
        backgroundColor: "rgba(34, 197, 94, 0.8)",
      },
      {
        label: "Failed",
        data: instances.map((i) => (i.last_post_ok === "false" ? 1 : 0)),
        backgroundColor: "rgba(239, 68, 68, 0.8)",
      },
    ],
  };

  return (
    <div className="space-y-6 p-4">
      <h2 className="text-xl font-bold text-gray-100">{company} Metrics</h2>
      
      <div className="bg-gray-800 p-4 rounded">
        <h3 className="text-lg font-semibold text-gray-200 mb-4">Posting Success Rate</h3>
        <Bar
          data={postingSuccessData}
          options={{
            responsive: true,
            plugins: {
              legend: { labels: { color: "#e5e7eb" } },
            },
            scales: {
              x: { ticks: { color: "#9ca3af" }, grid: { color: "#374151" } },
              y: { ticks: { color: "#9ca3af" }, grid: { color: "#374151" } },
            },
          }}
        />
      </div>

      <div className="bg-gray-800 p-4 rounded">
        <h3 className="text-lg font-semibold text-gray-200 mb-4">Activity Summary</h3>
        <div className="grid grid-cols-3 gap-4 text-gray-300">
          <div>
            <div className="text-2xl font-bold text-blue-400">
              {instances.reduce((sum, i) => sum + i.cells_written, 0)}
            </div>
            <div className="text-sm">Total Cells Written</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-green-400">
              {instances.reduce((sum, i) => sum + i.rows_marked_true, 0)}
            </div>
            <div className="text-sm">Rows Processed</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-yellow-400">
              {instances.reduce((sum, i) => sum + i.skipped_no_rule, 0)}
            </div>
            <div className="text-sm">Skipped (No Rule)</div>
          </div>
        </div>
      </div>
    </div>
  );
};

