import { api } from "@/lib/api";
import type { CustomerAccountData, TeamData } from "@/types";

const SYNC_DELAY_MS = 3_000;

export type OrgSyncOp =
  | {
      key: string;
      type: "updateTeam";
      teamId: number;
      body: { name?: string; description?: string };
    }
  | {
      key: string;
      type: "addTeamMember";
      teamId: number;
      body: { name: string; email: string; designation?: string; is_lead?: boolean };
    }
  | {
      key: string;
      type: "updateTeamMember";
      teamId: number;
      personId: number;
      body: { name?: string; email?: string; designation?: string; is_lead?: boolean };
    }
  | {
      key: string;
      type: "removeTeamMember";
      teamId: number;
      personId: number;
    }
  | {
      key: string;
      type: "deleteTeam";
      teamId: number;
    }
  | {
      key: string;
      type: "createTeam";
      body: { name: string; description?: string };
      tempId: number;
    }
  | {
      key: string;
      type: "updateCustomer";
      customerId: number;
      body: {
        workshop_name?: string;
        support_person_name?: string;
        support_person_email?: string;
        workshop_email?: string;
        support_contact_email?: string;
        ax_id?: string;
        tier?: string;
        location?: string;
      };
    }
  | {
      key: string;
      type: "deleteCustomer";
      customerId: number;
    }
  | {
      key: string;
      type: "createCustomer";
      body: {
        workshop_name: string;
        support_person_name?: string;
        support_person_email?: string;
        workshop_email?: string;
        support_contact_email?: string;
        ax_id?: string;
        tier?: string;
        location?: string;
      };
      tempId: number;
    };

type SyncListener = (state: { pending: number; syncing: boolean; lastError: string | null }) => void;

let timer: ReturnType<typeof setTimeout> | null = null;
const pending = new Map<string, OrgSyncOp>();
const listeners = new Set<SyncListener>();
let syncing = false;
let lastError: string | null = null;

function notify() {
  const state = { pending: pending.size, syncing, lastError };
  listeners.forEach((fn) => fn(state));
}

export function subscribeOrgSync(listener: SyncListener): () => void {
  listeners.add(listener);
  listener({ pending: pending.size, syncing, lastError });
  return () => listeners.delete(listener);
}

export function enqueueOrgSync(op: OrgSyncOp): void {
  pending.set(op.key, op);
  notify();
  if (timer) clearTimeout(timer);
  timer = setTimeout(() => {
    void flushOrgSync();
  }, SYNC_DELAY_MS);
}

export async function flushOrgSync(): Promise<void> {
  if (timer) {
    clearTimeout(timer);
    timer = null;
  }
  if (pending.size === 0 || syncing) return;

  syncing = true;
  lastError = null;
  notify();

  const ops = Array.from(pending.values());
  pending.clear();

  const teamReplacements = new Map<number, TeamData>();
  const customerReplacements = new Map<number, CustomerAccountData>();

  try {
    for (const op of ops) {
      switch (op.type) {
        case "updateTeam":
          teamReplacements.set(op.teamId, await api.updateTeam(op.teamId, op.body));
          break;
        case "addTeamMember":
          teamReplacements.set(op.teamId, await api.addTeamMember(op.teamId, op.body));
          break;
        case "updateTeamMember":
          teamReplacements.set(
            op.teamId,
            await api.updateTeamMember(op.teamId, op.personId, op.body)
          );
          break;
        case "removeTeamMember":
          teamReplacements.set(op.teamId, await api.removeTeamMember(op.teamId, op.personId));
          break;
        case "deleteTeam":
          await api.deleteTeam(op.teamId);
          break;
        case "createTeam": {
          const created = await api.createTeam(op.body);
          teamReplacements.set(op.tempId, created);
          break;
        }
        case "updateCustomer":
          customerReplacements.set(op.customerId, await api.updateCustomerAccount(op.customerId, op.body));
          break;
        case "deleteCustomer":
          await api.deleteCustomerAccount(op.customerId);
          break;
        case "createCustomer": {
          const created = await api.createCustomerAccount(op.body);
          customerReplacements.set(op.tempId, created);
          break;
        }
      }
    }
  } catch (err) {
    lastError = err instanceof Error ? err.message : "Sync failed";
  } finally {
    syncing = false;
    notify();
  }

  if (teamReplacements.size || customerReplacements.size) {
    window.dispatchEvent(
      new CustomEvent("org-sync-reconciled", {
        detail: {
          teams: Object.fromEntries(teamReplacements),
          customers: Object.fromEntries(customerReplacements),
        },
      })
    );
  }
}

if (typeof window !== "undefined") {
  window.addEventListener("beforeunload", () => {
    if (pending.size > 0) void flushOrgSync();
  });
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden" && pending.size > 0) {
      void flushOrgSync();
    }
  });
}
