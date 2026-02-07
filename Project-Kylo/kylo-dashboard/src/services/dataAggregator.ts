import { InstanceRow } from "../types/kylo";

export interface GroupedInstances {
  [company: string]: {
    [year: string]: InstanceRow[];
  };
}

export function groupInstancesByCompanyYear(instances: InstanceRow[]): GroupedInstances {
  const grouped: GroupedInstances = {};
  
  for (const instance of instances) {
    const company = instance.company_key || "UNKNOWN";
    const years = instance.active_years.split(",").map(y => y.trim()).filter(Boolean);
    
    if (!grouped[company]) {
      grouped[company] = {};
    }
    
    for (const year of years) {
      if (!grouped[company][year]) {
        grouped[company][year] = [];
      }
      grouped[company][year].push(instance);
    }
  }
  
  return grouped;
}

export function getCompanies(grouped: GroupedInstances): string[] {
  return Object.keys(grouped).sort();
}

export function getYearsForCompany(grouped: GroupedInstances, company: string): string[] {
  if (!grouped[company]) return [];
  return Object.keys(grouped[company]).sort();
}

