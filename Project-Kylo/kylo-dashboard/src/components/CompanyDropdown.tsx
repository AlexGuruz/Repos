import React from "react";

interface CompanyDropdownProps {
  companies: string[];
  selectedCompany: string | null;
  onSelect: (company: string | null) => void;
}

export const CompanyDropdown: React.FC<CompanyDropdownProps> = ({
  companies,
  selectedCompany,
  onSelect,
}) => {
  return (
    <select
      value={selectedCompany || ""}
      onChange={(e) => onSelect(e.target.value || null)}
      className="px-3 py-2 bg-gray-800 text-gray-100 border border-gray-700 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
    >
      <option value="">Select Company</option>
      {companies.map((company) => (
        <option key={company} value={company}>
          {company}
        </option>
      ))}
    </select>
  );
};

