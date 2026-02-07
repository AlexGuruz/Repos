import React, { useEffect, useState } from "react";
import { CompanyDropdown } from "./components/CompanyDropdown";
import { YearDropdown } from "./components/YearDropdown";
import { InstanceList } from "./components/InstanceList";
import { LogViewer } from "./components/LogViewer";
import { MetricsGraph } from "./components/MetricsGraph";
import { BudgetProjection } from "./components/BudgetProjection";
import { InstanceRow } from "./types/kylo";
import {
  groupInstancesByCompanyYear,
  getCompanies,
  getYearsForCompany,
} from "./services/dataAggregator";

type Tab = "overview" | "logs" | "metrics" | "budget";

function App() {
  const [instances, setInstances] = useState<InstanceRow[]>([]);
  const [grouped, setGrouped] = useState<ReturnType<typeof groupInstancesByCompanyYear>>({});
  const [selectedCompany, setSelectedCompany] = useState<string | null>(null);
  const [selectedYear, setSelectedYear] = useState<string | null>(null);
  const [selectedInstanceId, setSelectedInstanceId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("overview");

  useEffect(() => {
    const loadInstances = async () => {
      const result = await window.electronAPI.listInstances();
      if (result.success && result.instances) {
        setInstances(result.instances);
        setGrouped(groupInstancesByCompanyYear(result.instances));
      }
    };

    loadInstances();

    window.electronAPI.onDashboardUpdate((data) => {
      if (data.instances) {
        setInstances(data.instances);
        setGrouped(groupInstancesByCompanyYear(data.instances));
      }
    });
  }, []);

  const companies = getCompanies(grouped);
  const years = selectedCompany ? getYearsForCompany(grouped, selectedCompany) : [];
  const filteredInstances = selectedCompany && selectedYear
    ? grouped[selectedCompany]?.[selectedYear] || []
    : [];

  return (
    <div className="h-screen flex flex-col bg-gray-900 text-gray-100">
      {/* Header */}
      <header className="bg-gray-800 border-b border-gray-700 p-4">
        <div className="flex items-center gap-4">
          <h1 className="text-xl font-bold">Kylo Hub Dashboard</h1>
          <div className="flex gap-2">
            <CompanyDropdown
              companies={companies}
              selectedCompany={selectedCompany}
              onSelect={setSelectedCompany}
            />
            <YearDropdown
              years={years}
              selectedYear={selectedYear}
              onSelect={setSelectedYear}
              disabled={!selectedCompany}
            />
          </div>
        </div>
      </header>

      {/* Tabs */}
      <div className="flex border-b border-gray-700 bg-gray-800">
        {(["overview", "logs", "metrics", "budget"] as Tab[]).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 capitalize ${
              activeTab === tab
                ? "border-b-2 border-blue-500 text-blue-400"
                : "text-gray-400 hover:text-gray-200"
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden flex">
        {activeTab === "overview" && (
          <div className="flex-1 p-4 overflow-auto">
            <InstanceList
              instances={filteredInstances}
              selectedInstanceId={selectedInstanceId}
              onSelect={setSelectedInstanceId}
            />
          </div>
        )}

        {activeTab === "logs" && (
          <div className="flex-1 flex flex-col">
            <LogViewer instanceId={selectedInstanceId} />
          </div>
        )}

        {activeTab === "metrics" && selectedCompany && (
          <div className="flex-1 overflow-auto">
            <MetricsGraph company={selectedCompany} instances={filteredInstances} />
          </div>
        )}

        {activeTab === "budget" && <BudgetProjection />}
      </div>
    </div>
  );
}

export default App;

