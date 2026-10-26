import { PortalShell } from "@/components/portal-shell";
import { RoleGate } from "@/components/role-gate";

export default function AgentLayout({ children }: LayoutProps<"/">) {
  return (
    <PortalShell title="Delivery agent" nav={[{ href: "/agent", label: "Deliveries" }]}>
      <RoleGate role="agent">{children}</RoleGate>
    </PortalShell>
  );
}
