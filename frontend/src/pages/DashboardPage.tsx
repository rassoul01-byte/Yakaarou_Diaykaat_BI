import { AlertTriangle, ArrowUpRight, Bot, Database, Search, Sparkles, ShieldCheck } from "lucide-react";

import type { Page } from "../components/Sidebar";

type Props = {
  onNavigate: (page: Page) => void;
};

const captures = [
  { fichier: "qualite-taux-global.png", titre: "Taux de rejet global" },
  { fichier: "qualite-par-source.png", titre: "Taux de rejet" },
  { fichier: "qualite-par-regle.png", titre: "Taux de rejet par règle" },
  { fichier: "qualite-par-gravite.png", titre: "Répartition des rejets par gravité" },
];

export default function DashboardPage({ onNavigate }: Props) {
  return (
    <>
      <section className="hero">
        <div>
          <div className="hero-kicker">
            <Sparkles size={15} />
            DATAFLOW360
          </div>
          <h2>La donnée devient une décision.</h2>
          <p>
            Vue synthétique de l'activité e-commerce, de la qualité des flux
            et des signaux utiles à l'équipe métier.
          </p>
        </div>

        <div className="hero-badge">
          <ShieldCheck size={17} />
          Pipeline supervisé
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <div className="panel-kicker">TABLEAU DE BORD OFFICIEL</div>
            <h3>Power BI</h3>
          </div>
        </div>
        <p style={{ marginBottom: "1rem" }}>
          Le tableau de bord de référence est le fichier{" "}
          <code>dashboards/ventes.pbix</code>. Les captures ci-dessous
          proviennent de ce fichier.
        </p>
      </section>

      <section
        className="capture-grid"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
          gap: "1.5rem",
          marginBottom: "1.5rem",
        }}
      >
        {captures.map((c) => (
          <div className="panel" key={c.fichier}>
            <div className="panel-header">
              <div>
                <div className="panel-kicker">QUALITÉ DES DONNÉES</div>
                <h3>{c.titre}</h3>
              </div>
            </div>
            <img
              src={`/captures/${c.fichier}`}
              alt={c.titre}
              style={{
                width: "100%",
                height: "auto",
                borderRadius: "0.5rem",
                border: "1px solid #e2e8f0",
              }}
            />
          </div>
        ))}
      </section>

      <section className="bottom-grid">
        <div className="panel action-panel">
          <div className="panel-kicker">ACCÈS RAPIDE</div>
          <h3>Explorer les usages</h3>

          <button className="action-card" onClick={() => onNavigate("recherche")}>
            <div className="action-icon blue">
              <Search size={18} />
            </div>
            <div>
              <strong>Recherche produits</strong>
              <span>Interroger le catalogue</span>
            </div>
            <ArrowUpRight size={17} />
          </button>

          <button className="action-card" onClick={() => onNavigate("assistant")}>
            <div className="action-icon purple">
              <Bot size={18} />
            </div>
            <div>
              <strong>Assistant client</strong>
              <span>Poser une question, avec sources citées</span>
            </div>
            <ArrowUpRight size={17} />
          </button>
        </div>

        <div className="panel">
          <div className="panel-header">
            <div>
              <div className="panel-kicker">QUALITÉ DES DONNÉES</div>
              <h3>État du pipeline</h3>
            </div>
            <span className="quality-status">
              <span className="status-dot online" />
              Surveillance active
            </span>
          </div>

          <p>
            Les indicateurs détaillés (taux de rejet, répartition par gravité,
            par règle, par source) sont dans le tableau de bord Power BI
            ci-dessus.
          </p>

          <div className="warning-box" style={{ marginTop: "1rem" }}>
            <AlertTriangle size={18} />
            <div>
              <strong>Power BI reste le tableau de bord officiel</strong>
              <span>Cette page en présente une synthèse, pas un doublon.</span>
            </div>
          </div>
        </div>
      </section>
    </>
  );
}
