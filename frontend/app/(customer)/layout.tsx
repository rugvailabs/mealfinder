import { PortalShell } from "@/components/portal-shell";

export default function CustomerLayout({ children }: LayoutProps<"/">) {
  return (
    <PortalShell title="" nav={[{ href: "/become-a-cook", label: "Cook with us" }]}>
      {children}
    </PortalShell>
  );
}
