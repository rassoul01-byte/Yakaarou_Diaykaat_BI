import { useEffect, useMemo, useState } from "react";

import { api } from "./api/client";
import Sidebar from "./components/Sidebar";
import { navItems, type Page } from "./components/navigation";
import Topbar from "./components/Topbar";
import AssistantPage from "./pages/AssistantPage";
import DashboardPage from "./pages/DashboardPage";
import RecherchePage from "./pages/RecherchePage";

export default function App() {
  const [page, setPage] = useState<Page>("dashboard");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);

  useEffect(() => {
    api
      .health()
      .then(() => setApiOnline(true))
      .catch(() => setApiOnline(false));
  }, []);

  const titre = useMemo(
    () => navItems.find((item) => item.id === page)?.label ?? "Vue générale",
    [page],
  );

  function naviguer(p: Page) {
    setPage(p);
    setSidebarOpen(false);
  }

  return (
    <div className="app-shell">
      <Sidebar
        page={page}
        onNavigate={naviguer}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        apiOnline={apiOnline}
      />

      <main className="main">
        <Topbar
          titre={titre}
          onOuvrirMenu={() => setSidebarOpen(true)}
          onRecharger={() => window.location.reload()}
        />

        <div className="content">
          {/* La clé force React à remonter le composant, ce qui relance l'animation */}
          <div key={page} className="page-enter">
            {page === "dashboard" && <DashboardPage onNavigate={naviguer} />}
            {page === "recherche" && <RecherchePage />}
            {page === "assistant" && <AssistantPage />}
          </div>
        </div>
      </main>
    </div>
  );
}
