import React from "react";

interface YearDropdownProps {
  years: string[];
  selectedYear: string | null;
  onSelect: (year: string | null) => void;
  disabled?: boolean;
}

export const YearDropdown: React.FC<YearDropdownProps> = ({
  years,
  selectedYear,
  onSelect,
  disabled = false,
}) => {
  return (
    <select
      value={selectedYear || ""}
      onChange={(e) => onSelect(e.target.value || null)}
      disabled={disabled}
      className="px-3 py-2 bg-gray-800 text-gray-100 border border-gray-700 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
    >
      <option value="">Select Year</option>
      {years.map((year) => (
        <option key={year} value={year}>
          {year}
        </option>
      ))}
    </select>
  );
};

