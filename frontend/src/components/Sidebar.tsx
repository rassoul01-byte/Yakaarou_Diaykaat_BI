import { Activity, X } from "lucide-react";

import { navItems, type Page } from "./navigation";

export type { Page };

type Props = {
  page: Page;
  onNavigate: (page: Page) => void;
  open: boolean;
  onClose: () => void;
  apiOnline: boolean | null;
};

export default function Sidebar({ page, onNavigate, open, onClose, apiOnline }: Props) {
  return (
    <aside className={`sidebar ${open ? "open" : ""}`}>
      <div className="brand">
        <div className="brand-mark">
          <Activity size={20} />
        </div>
        <div>
          <div className="brand-title">DataFlow360</div>
          <div className="brand-subtitle">Data Intelligence</div>
        </div>
        <button
          className="icon-button mobile-close"
          onClick={onClose}
          aria-label="Fermer le menu"
        >
          <X size={19} />
        </button>
      </div>

      <div className="nav-label">PLATEFORME</div>

      <nav className="nav">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              className={`nav-item ${page === item.id ? "active" : ""}`}
              onClick={() => onNavigate(item.id)}
            >
              <Icon size={18} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>

      <div className="sidebar-bottom">
        <div className="system-card">
          <div className="system-head">
            <span className={`status-dot ${apiOnline ? "online" : ""}`} />
            <span>
              {apiOnline === null
                ? "Vérification…"
                : apiOnline
                  ? "API opérationnelle"
                  : "API injoignable"}
            </span>
          </div>
          <p>
            Power BI reste le tableau de bord officiel. Cette interface web
            présente les usages de la plateforme.
          </p>
        </div>
        <div className="version">DataFlow360 · Sprint 5</div>
      </div>
    </aside>
  );
}