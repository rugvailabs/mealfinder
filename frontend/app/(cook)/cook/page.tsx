import Link from "next/link";

export default function CookDashboardPage() {
  return (
    <section className="space-y-3">
      <h1 className="text-2xl font-semibold">Cook dashboard</h1>
      <p className="opacity-70">
        Keep your profile and home address up to date; your application status is on your{" "}
        <Link href="/cook/profile" className="underline">
          profile
        </Link>
        .
      </p>
    </section>
  );
}
