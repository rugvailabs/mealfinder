import { PortalShell } from "@/components/portal-shell";

export default function AdminLayout({ children }: LayoutProps<"/">) {
  return (
    <PortalShell title="Admin" nav={[{ href: "/admin", label: "Overview" }]}>
      {children}
    </PortalShell>
  );
}
