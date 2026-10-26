import Link from "next/link";
import type { ReactNode } from "react";

import { AccountMenu } from "@/components/account-menu";

type NavItem = { href: string; label: string };

export function PortalShell({
  title,
  nav,
  children,
}: {
  title: string;
  nav: NavItem[];
  children: ReactNode;
}) {
  return (
    <div className="flex min-h-full flex-1 flex-col">
      <header className="border-b border-black/10 dark:border-white/15">
        <div className="mx-auto flex max-w-5xl items-center gap-6 px-4 py-3">
          <Link href="/" className="font-semibold">
            Meal Finder
          </Link>
          <span className="text-sm opacity-60">{title}</span>
          <nav className="ml-auto flex gap-4 text-sm">
            {nav.map((item) => (
              <Link key={item.href} href={item.href} className="hover:underline">
                {item.label}
              </Link>
            ))}
            <AccountMenu />
          </nav>
        </div>
      </header>
      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8">{children}</main>
    </div>
  );
}
