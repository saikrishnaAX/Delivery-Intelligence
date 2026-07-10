import type { CustomerAccountData, TeamData } from "@/types";

const TEAMS_KEY = "ax_org_teams";
const CUSTOMERS_KEY = "ax_org_customers";

let memTeams: TeamData[] | null = null;
let memCustomers: CustomerAccountData[] | null = null;
let teamsHydrated = false;
let customersHydrated = false;

function readStorage<T>(key: string): T | null {
  try {
    const raw = sessionStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

function writeStorage<T>(key: string, data: T): void {
  try {
    sessionStorage.setItem(key, JSON.stringify(data));
  } catch {
    // sessionStorage full — in-memory cache still works this tab
  }
}

export function isOrgTeamsHydrated(): boolean {
  return teamsHydrated;
}

export function isOrgCustomersHydrated(): boolean {
  return customersHydrated;
}

export function readOrgTeams(): TeamData[] | null {
  if (teamsHydrated && memTeams) return memTeams;
  const stored = readStorage<TeamData[]>(TEAMS_KEY);
  if (stored) {
    memTeams = stored;
    teamsHydrated = true;
    return stored;
  }
  return memTeams;
}

export function writeOrgTeams(teams: TeamData[]): void {
  memTeams = teams;
  teamsHydrated = true;
  writeStorage(TEAMS_KEY, teams);
}

export function readOrgCustomers(): CustomerAccountData[] | null {
  if (customersHydrated && memCustomers) return memCustomers;
  const stored = readStorage<CustomerAccountData[]>(CUSTOMERS_KEY);
  if (stored) {
    memCustomers = stored;
    customersHydrated = true;
    return stored;
  }
  return memCustomers;
}

export function writeOrgCustomers(customers: CustomerAccountData[]): void {
  memCustomers = customers;
  customersHydrated = true;
  writeStorage(CUSTOMERS_KEY, customers);
}

export function markOrgCustomersStale(): void {
  customersHydrated = false;
}

export function markOrgTeamsStale(): void {
  teamsHydrated = false;
}
