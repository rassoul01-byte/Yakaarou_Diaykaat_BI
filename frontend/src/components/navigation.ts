import { Activity, LayoutDashboard, MessageCircle, Search } from "lucide-react";

export type Page = "dashboard" | "recherche" | "assistant";

export const navItems: { id: Page; label: string; icon: typeof Activity }[] = [
  { id: "dashboard", label: "Vue générale", icon: LayoutDashboard },
  { id: "recherche", label: "Recherche produits", icon: Search },
  { id: "assistant", label: "Assistant client", icon: MessageCircle },
];
