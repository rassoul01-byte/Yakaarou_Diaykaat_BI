import { useEffect, useState } from "react";

import { api } from "./api/client";
import type { Page } from "./components/navigation";
import Topbar from "./components/Topbar";
import AssistantPage from "./pages/AssistantPage";
import DashboardPage from "./pages/DashboardPage";
import RecherchePage from "./pages/RecherchePage";

export default function App() {
  const [page, setPage] = useState<Page>("dashboard");
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);

  useEffect(() => {
    api
      .health()
      .then(() => setApiOnline(true))
      .catch(() => setApiOnline(false));
  }, []);

  return (
    <div className="app-shell">
      <Topbar
        page={page}
        onNavigate={setPage}
        onRecharger={() => window.location.reload()}
        apiOnline={apiOnline}
      />

      <main className="main">
        <div className="content">
          {/* La clé force React à remonter le composant, ce qui relance l'animation */}
          <div key={page} className="page-enter">
            {page === "dashboard" && <DashboardPage />}
            {page === "recherche" && <RecherchePage />}
            {page === "assistant" && <AssistantPage />}
          </div>
        </div>
      </main>
    </div>
  );
}
