"use client";

import { useEffect, useState, type FormEvent } from "react";

import { api, problemDetail } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";
import { errorClass, inputClass, secondaryButtonClass } from "@/lib/ui/styles";

type Cook = components["schemas"]["CookAdminOut"];
type Status = Cook["approval_status"];

const FILTERS: { label: string; value: Status | null }[] = [
  { label: "Pending", value: "pending" },
  { label: "Approved", value: "approved" },
  { label: "Suspended", value: "suspended" },
  { label: "Rejected", value: "rejected" },
  { label: "All", value: null },
];

export default function AdminCooksPage() {
  const [filter, setFilter] = useState<Status | null>("pending");
  const [cooks, setCooks] = useState<Cook[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Bumped after a decision, to reload the current tab.
  const [version, setVersion] = useState(0);

  useEffect(() => {
    const query = filter ? { status: filter } : {};
    void api.GET("/api/v1/admin/cooks", { params: { query } }).then(({ data, error }) => {
      setError(error ? problemDetail(error, "Could not load cooks") : null);
      if (data) setCooks(data);
    });
  }, [filter, version]);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Cooks</h1>
      <div className="flex flex-wrap gap-2" role="tablist" aria-label="Filter by status">
        {FILTERS.map((f) => (
          <button
            key={f.label}
            role="tab"
            aria-selected={filter === f.value}
            className={`${secondaryButtonClass} ${filter === f.value ? "bg-black/10 dark:bg-white/15" : ""}`}
            onClick={() => setFilter(f.value)}
          >
            {f.label}
          </button>
        ))}
      </div>
      {error && (
        <p role="alert" className={errorClass}>
          {error}
        </p>
      )}
      {cooks === null ? (
        <p className="opacity-60">Loading…</p>
      ) : cooks.length === 0 ? (
        <p className="opacity-70">No cooks here.</p>
      ) : (
        <ul className="space-y-4">
          {cooks.map((cook) => (
            <CookRow key={cook.id} cook={cook} onDecided={() => setVersion((v) => v + 1)} />
          ))}
        </ul>
      )}
    </div>
  );
}

type Action = "approve" | "reject" | "suspend";

function CookRow({ cook, onDecided }: { cook: Cook; onDecided: () => void }) {
  const [asking, setAsking] = useState<"reject" | "suspend" | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function decide(action: Action, why?: string) {
    setBusy(true);
    setError(null);
    const params = { path: { cook_id: cook.id } };
    const body = { reason: why ?? "" };
    const { error } =
      action === "approve"
        ? await api.POST("/api/v1/admin/cooks/{cook_id}/approve", { params })
        : action === "reject"
          ? await api.POST("/api/v1/admin/cooks/{cook_id}/reject", { params, body })
          : await api.POST("/api/v1/admin/cooks/{cook_id}/suspend", { params, body });
    setBusy(false);
    if (error) return setError(problemDetail(error, `Could not ${action}`));
    setAsking(null);
    setReason("");
    onDecided();
  }

  function submitReason(event: FormEvent) {
    event.preventDefault();
    if (asking) void decide(asking, reason);
  }

  const status = cook.approval_status;
  return (
    <li
      className="space-y-2 rounded border border-black/10 p-4 dark:border-white/15"
      aria-label={cook.display_name}
    >
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <strong>{cook.display_name}</strong>
        <span className="text-sm opacity-70">{cook.phone}</span>
        <span className="text-sm" data-testid="cook-status">
          {status}
        </span>
        <span className="text-sm opacity-70">
          submitted {new Date(cook.submitted_at).toLocaleString()}
        </span>
        <span className="text-sm opacity-70">
          {cook.has_address ? "address on file" : "no address yet"}
        </span>
      </div>
      {cook.bio && <p className="text-sm">{cook.bio}</p>}
      {cook.rejection_reason && (
        <p className="text-sm">
          {status === "rejected" ? "Rejected" : "Previously rejected"}: {cook.rejection_reason}
        </p>
      )}
      {status === "suspended" && cook.suspension_reason && (
        <p className="text-sm">Suspended: {cook.suspension_reason}</p>
      )}

      <div className="flex flex-wrap gap-2">
        {(status === "pending" || status === "suspended") && (
          <button
            className={secondaryButtonClass}
            disabled={busy || !cook.has_address}
            title={cook.has_address ? undefined : "The cook needs to add their address first"}
            onClick={() => void decide("approve")}
          >
            {status === "suspended" ? "Reinstate" : "Approve"}
          </button>
        )}
        {status === "pending" && (
          <button
            className={secondaryButtonClass}
            disabled={busy}
            onClick={() => setAsking("reject")}
          >
            Reject
          </button>
        )}
        {status === "approved" && (
          <button
            className={secondaryButtonClass}
            disabled={busy}
            onClick={() => setAsking("suspend")}
          >
            Suspend
          </button>
        )}
      </div>

      {asking && (
        <form className="flex flex-wrap items-end gap-2" onSubmit={submitReason}>
          <label className="block flex-1 space-y-1">
            <span className="text-sm">Reason to {asking}</span>
            <input
              className={inputClass}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              minLength={3}
              maxLength={500}
              required
              autoFocus
            />
          </label>
          <button className={secondaryButtonClass} disabled={busy}>
            Confirm {asking}
          </button>
          <button type="button" className={secondaryButtonClass} onClick={() => setAsking(null)}>
            Cancel
          </button>
        </form>
      )}
      {error && (
        <p role="alert" className={errorClass}>
          {error}
        </p>
      )}
    </li>
  );
}
