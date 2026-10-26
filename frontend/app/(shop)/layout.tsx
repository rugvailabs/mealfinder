import { PortalShell } from "@/components/portal-shell";
import { RoleGate } from "@/components/role-gate";

export default function ShopLayout({ children }: LayoutProps<"/">) {
  return (
    <PortalShell title="Shop" nav={[{ href: "/shop", label: "Stock" }]}>
      <RoleGate role="shop">{children}</RoleGate>
    </PortalShell>
  );
}
