import { PortalShell } from "@/components/portal-shell";
import { RoleGate } from "@/components/role-gate";

export default function AdminLayout({ children }: LayoutProps<"/">) {
  return (
    <PortalShell title="Admin" nav={[{ href: "/admin", label: "Overview" }]}>
      <RoleGate role="admin">{children}</RoleGate>
    </PortalShell>
  );
}
