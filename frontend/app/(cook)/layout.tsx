import { PortalShell } from "@/components/portal-shell";
import { RoleGate } from "@/components/role-gate";

export default function CookLayout({ children }: LayoutProps<"/">) {
  return (
    <PortalShell
      title="Cook"
      nav={[
        { href: "/cook", label: "Dashboard" },
        { href: "/cook/profile", label: "Profile" },
      ]}
    >
      <RoleGate role="cook">{children}</RoleGate>
    </PortalShell>
  );
}
