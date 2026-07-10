import type { CustomerAccountData, TeamData } from "@/types";

const AGENT_NAME_ALIASES: Record<string, string> = {
  aniketh: "aniket",
};

function normalizeAgentLabel(agentName: string): string {
  const first = agentName.trim().split(/\s+/)[0]?.toLowerCase() || "";
  return AGENT_NAME_ALIASES[first] || agentName.trim();
}

function nameKey(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]/g, "");
}

function firstToken(name: string): string {
  return name.trim().split(/\s+/)[0]?.toLowerCase() || "";
}

function namesSimilar(a: string, b: string): boolean {
  if (!a || !b) return false;
  if (a === b) return true;
  if (a.startsWith(b) || b.startsWith(a)) return Math.min(a.length, b.length) >= 4;
  const ak = nameKey(a);
  const bk = nameKey(b);
  if (ak && bk && ak === bk) return true;
  if (ak.length < 5 || bk.length < 5) return false;
  let mismatches = 0;
  const maxLen = Math.max(ak.length, bk.length);
  const minLen = Math.min(ak.length, bk.length);
  for (let i = 0; i < minLen; i++) {
    if (ak[i] !== bk[i]) mismatches++;
  }
  mismatches += maxLen - minLen;
  return mismatches <= 1;
}

function agentMatchesPerson(agent: string, personName: string): boolean {
  const agentNorm = agent.trim().toLowerCase();
  if (!agentNorm || !personName) return false;
  const personFirst = firstToken(personName);
  const personFull = personName.trim().toLowerCase();
  if (agentNorm === personFirst || agentNorm === personFull) return true;
  return namesSimilar(agentNorm, personFirst);
}

/** Resolve support mail from teams roster by matching agent / support person name. */
export function resolveSupportEmailFromTeams(
  agentName: string | undefined,
  teams: TeamData[]
): string | undefined {
  if (!agentName?.trim()) return undefined;
  const resolvedName = normalizeAgentLabel(agentName);
  const supportFirst = teams
    .map((team) => ({
      priority: team.name.toLowerCase().includes("support") ? 0 : 1,
      members: team.members,
    }))
    .sort((a, b) => a.priority - b.priority);

  for (const { members } of supportFirst) {
    for (const member of members) {
      const email = member.person.email;
      if (!email) continue;
      if (agentMatchesPerson(resolvedName, member.person.name)) {
        return email;
      }
      if (resolvedName !== agentName && agentMatchesPerson(agentName, member.person.name)) {
        return email;
      }
    }
  }
  return undefined;
}

export function resolveWorkshopSupportEmail(
  workshop: CustomerAccountData,
  teams: TeamData[]
): string | undefined {
  const fromTeams = resolveSupportEmailFromTeams(workshop.support_person_name, teams);
  if (fromTeams) return fromTeams;
  return workshop.support_contact_email || workshop.support_person_email;
}
