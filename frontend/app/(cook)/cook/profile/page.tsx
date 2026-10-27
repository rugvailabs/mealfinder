"use client";

import { useEffect, useState, type FormEvent, type InputHTMLAttributes } from "react";

import { api, problemDetail } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";
import { buttonClass, errorClass, inputClass, secondaryButtonClass } from "@/lib/ui/styles";

type Profile = components["schemas"]["CookProfileOut"];
type AddressIn = components["schemas"]["HomeAddressIn"];

export default function CookProfilePage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void api.GET("/api/v1/cooks/me").then(({ data, error }) => {
      if (error) setError(problemDetail(error, "Could not load your profile"));
      else setProfile(data);
    });
  }, []);

  if (error) {
    return (
      <p role="alert" className={errorClass}>
        {error}
      </p>
    );
  }
  if (!profile) return <p className="opacity-60">Loading…</p>;

  return (
    <div className="max-w-2xl space-y-10">
      <h1 className="text-2xl font-semibold">Your cook profile</h1>
      <StatusPanel profile={profile} onChange={setProfile} />
      <ProfileForm profile={profile} onSaved={setProfile} />
      <AddressForm />
    </div>
  );
}

const STATUS_TEXT: Record<Profile["approval_status"], string> = {
  pending: "Your application is waiting for review.",
  approved: "You're approved. You can start listing meals once listings open.",
  rejected: "Your application was not approved.",
  suspended: "Your account is suspended.",
};

function StatusPanel({
  profile,
  onChange,
}: {
  profile: Profile;
  onChange: (profile: Profile) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function resubmit() {
    setBusy(true);
    setError(null);
    const { data, error } = await api.POST("/api/v1/cooks/me/resubmit");
    setBusy(false);
    if (error) return setError(problemDetail(error, "Could not resubmit"));
    onChange(data);
  }

  return (
    <section
      className="space-y-2 rounded border border-black/10 p-4 dark:border-white/15"
      aria-label="Application status"
    >
      <p>
        Status: <strong data-testid="approval-status">{profile.approval_status}</strong>
      </p>
      <p className="opacity-70">{STATUS_TEXT[profile.approval_status]}</p>
      {profile.approval_status === "rejected" && (
        <>
          {profile.rejection_reason && <p>Reason: {profile.rejection_reason}</p>}
          <p className="text-sm opacity-70">
            Update your profile or address if needed, then ask for another review.
          </p>
          <button className={buttonClass} disabled={busy} onClick={() => void resubmit()}>
            Resubmit for review
          </button>
        </>
      )}
      {profile.approval_status === "suspended" && profile.suspension_reason && (
        <p>Reason: {profile.suspension_reason}</p>
      )}
      {error && (
        <p role="alert" className={errorClass}>
          {error}
        </p>
      )}
    </section>
  );
}

function ProfileForm({
  profile,
  onSaved,
}: {
  profile: Profile;
  onSaved: (profile: Profile) => void;
}) {
  const [displayName, setDisplayName] = useState(profile.display_name);
  const [bio, setBio] = useState(profile.bio ?? "");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage(null);
    const { data, error } = await api.PATCH("/api/v1/cooks/me", {
      body: { display_name: displayName, bio: bio || null },
    });
    setBusy(false);
    if (error) return setMessage({ ok: false, text: problemDetail(error, "Could not save") });
    onSaved(data);
    setMessage({ ok: true, text: "Profile saved" });
  }

  return (
    <form className="space-y-4" onSubmit={save} aria-label="Profile">
      <h2 className="text-lg font-semibold">Profile</h2>
      <label className="block space-y-1">
        <span className="text-sm">Kitchen name</span>
        <input
          className={inputClass}
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          minLength={2}
          maxLength={80}
          required
        />
      </label>
      <label className="block space-y-1">
        <span className="text-sm">About your cooking</span>
        <textarea
          className={inputClass}
          rows={4}
          value={bio}
          onChange={(e) => setBio(e.target.value)}
          maxLength={1000}
        />
      </label>
      <button className={buttonClass} disabled={busy}>
        Save profile
      </button>
      <FormMessage message={message} />
    </form>
  );
}

const EMPTY_ADDRESS = { line1: "", line2: "", city: "", pincode: "", lat: "", lng: "" };

function AddressForm() {
  const [fields, setFields] = useState(EMPTY_ADDRESS);
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    void (async () => {
      // 404 just means no address yet. Each read is audit-logged on the server.
      const { data } = await api.GET("/api/v1/cooks/me/address");
      if (data) {
        setFields({
          line1: data.line1,
          line2: data.line2 ?? "",
          city: data.city,
          pincode: data.pincode,
          lat: String(data.lat),
          lng: String(data.lng),
        });
      }
      setLoaded(true);
    })();
  }, []);

  const set = (key: keyof typeof EMPTY_ADDRESS) => (value: string) =>
    setFields((current) => ({ ...current, [key]: value }));

  function locateMe() {
    if (!navigator.geolocation) {
      return setMessage({ ok: false, text: "This browser can't share your location" });
    }
    navigator.geolocation.getCurrentPosition(
      (position) =>
        setFields((current) => ({
          ...current,
          lat: position.coords.latitude.toFixed(6),
          lng: position.coords.longitude.toFixed(6),
        })),
      () => setMessage({ ok: false, text: "Couldn't get your location; enter it instead" }),
    );
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage(null);
    const body: AddressIn = {
      line1: fields.line1,
      line2: fields.line2 || null,
      city: fields.city,
      pincode: fields.pincode,
      lat: Number(fields.lat),
      lng: Number(fields.lng),
    };
    const { error } = await api.PUT("/api/v1/cooks/me/address", { body });
    setBusy(false);
    if (error) return setMessage({ ok: false, text: problemDetail(error, "Could not save") });
    setMessage({ ok: true, text: "Address saved" });
  }

  if (!loaded) return <p className="opacity-60">Loading address…</p>;

  return (
    <form className="space-y-4" onSubmit={save} aria-label="Home address">
      <div className="space-y-1">
        <h2 className="text-lg font-semibold">Home address</h2>
        <p className="text-sm opacity-70">
          Only our delivery agents on your pickups and our admins can see this. It is never shown to
          customers or shops.
        </p>
      </div>
      <Field label="Address line 1" value={fields.line1} onChange={set("line1")} required />
      <Field label="Address line 2 (optional)" value={fields.line2} onChange={set("line2")} />
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="City" value={fields.city} onChange={set("city")} required />
        <Field
          label="Pincode"
          value={fields.pincode}
          onChange={set("pincode")}
          inputMode="numeric"
          pattern="[1-9][0-9]{5}"
          required
        />
        <Field
          label="Latitude"
          value={fields.lat}
          onChange={set("lat")}
          inputMode="decimal"
          required
        />
        <Field
          label="Longitude"
          value={fields.lng}
          onChange={set("lng")}
          inputMode="decimal"
          required
        />
      </div>
      <div className="flex items-center gap-3">
        <button className={buttonClass} disabled={busy}>
          Save address
        </button>
        <button type="button" className={secondaryButtonClass} onClick={locateMe}>
          Use my location
        </button>
      </div>
      <FormMessage message={message} />
    </form>
  );
}

function Field({
  label,
  value,
  onChange,
  ...rest
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
} & Omit<InputHTMLAttributes<HTMLInputElement>, "value" | "onChange">) {
  return (
    <label className="block space-y-1">
      <span className="text-sm">{label}</span>
      <input
        className={inputClass}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        {...rest}
      />
    </label>
  );
}

function FormMessage({ message }: { message: { ok: boolean; text: string } | null }) {
  if (!message) return null;
  return message.ok ? (
    <p role="status" className="text-sm text-green-700 dark:text-green-400">
      {message.text}
    </p>
  ) : (
    <p role="alert" className={errorClass}>
      {message.text}
    </p>
  );
}
