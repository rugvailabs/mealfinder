import { PortalShell } from "@/components/portal-shell";

export default function AgentLayout({ children }: LayoutProps<"/">) {
  return (
    <PortalShell title="Delivery agent" nav={[{ href: "/agent", label: "Deliveries" }]}>
      {children}
    </PortalShell>
  );
}
