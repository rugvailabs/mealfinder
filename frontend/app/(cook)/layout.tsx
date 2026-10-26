import { PortalShell } from "@/components/portal-shell";

export default function CookLayout({ children }: LayoutProps<"/">) {
  return (
    <PortalShell title="Cook" nav={[{ href: "/cook", label: "Dashboard" }]}>
      {children}
    </PortalShell>
  );
}
