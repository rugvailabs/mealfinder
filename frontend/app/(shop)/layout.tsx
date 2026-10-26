import { PortalShell } from "@/components/portal-shell";

export default function ShopLayout({ children }: LayoutProps<"/">) {
  return (
    <PortalShell title="Shop" nav={[{ href: "/shop", label: "Stock" }]}>
      {children}
    </PortalShell>
  );
}
