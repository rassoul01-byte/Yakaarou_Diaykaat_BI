import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  Bot,
  Database,
  ExternalLink,
  LayoutDashboard,
  Menu,
  MessageCircle,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";

import { api, ApiError } from "./api/client";
import type { AssistantOut, Passage, RechercheResultat } from "./types/api";

type Page = "dashboard" | "recherche" | "assistant";

const navItems: { id: Page; label: string; icon: typeof Activity }[] = [
  { id: "dashboard", label: "Vue générale", icon: LayoutDashboard },
  { id: "recherche", label: "Recherche", icon: Search },
  { id: "assistant", label: "Assistant client", icon: MessageCircle },
];

function formatMoney(value: number) {
  return new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 }).format(value);
}

function formatNumber(value: number) {
  return new Intl.NumberFormat("fr-FR").format(value);
}

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

  const title = useMemo(
    () => navItems.find((item) => item.id === page)?.label ?? "Vue générale",
    [page],
  );

  return (
    <div className="app-shell">
      <aside className={`sidebar ${sidebarOpen ? "open" : ""}`}>
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
            onClick={() => setSidebarOpen(false)}
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
                onClick={() => {
                  setPage(item.id);
                  setSidebarOpen(false);
                }}
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

      <main className="main">
        <header className="topbar">
          <div className="topbar-left">
            <button
              className="icon-button mobile-menu"
              onClick={() => setSidebarOpen(true)}
              aria-label="Ouvrir le menu"
            >
              <Menu size={20} />
            </button>
            <div>
              <div className="eyebrow">ESPACE DE PILOTAGE</div>
              <h1>{title}</h1>
            </div>
          </div>

          <div className="topbar-actions">
            <button className="refresh-button" onClick={() => window.location.reload()}>
              <RefreshCw size={16} />
              Recharger
            </button>
            <div className="avatar">MD</div>
          </div>
        </header>

        <div className="content">
          {page === "dashboard" && <Dashboard onNavigate={setPage} />}
          {page === "recherche" && <Recherche />}
          {page === "assistant" && <Assistant />}
        </div>
      </main>
    </div>
  );
}

/* ------------------------------------------------------------------ dashboard */

function Dashboard({ onNavigate }: { onNavigate: (page: Page) => void }) {
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
            Vue synthétique de l'activité e-commerce, de la qualité des flux et
            des signaux utiles à l'équipe métier.
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
          <code>dashboards/ventes.pbix</code>. Les captures de ses pages sont
          disponibles dans <code>docs/captures/</code>.
        </p>
        <div className="action-card" style={{ cursor: "default" }}>
          <div className="action-icon purple">
            <Database size={18} />
          </div>
          <div>
            <strong>Pages disponibles</strong>
            <span>
              Qualité des données · Taux de rejet global · Répartition par
              gravité · Par règle · Par source
            </span>
          </div>
          <ExternalLink size={17} />
        </div>
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
              <strong>Recherche documentaire</strong>
              <span>Interroger la base de connaissances</span>
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
            par règle, par source) sont dans le tableau de bord Power BI.
          </p>
        </div>
      </section>
    </>
  );
}

/* ------------------------------------------------------------------ recherche */

function Recherche() {
  const [q, setQ] = useState("");
  const [resultats, setResultats] = useState<RechercheResultat[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  async function lancer(question = q) {
    if (!question.trim()) return;
    setQ(question);
    setLoading(true);
    setErreur(null);
    try {
      const data = await api.rechercher({ q: question, k: 5 });
      setResultats(data.resultats);
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Erreur inconnue";
      setErreur(msg);
      setResultats([]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <section className="page-intro">
        <div>
          <div className="hero-kicker">
            <Search size={15} />
            RECHERCHE DOCUMENTAIRE
          </div>
          <h2>Interroger la base de connaissances</h2>
          <p>
            Recherche vectorielle sur la base documentaire. Résultats classés par
            pertinence.
          </p>
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <div className="panel-kicker">REQUÊTE</div>
            <h3>Votre recherche</h3>
          </div>
        </div>

        <div className="question-row">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && lancer()}
            placeholder="Ex. retour produit, délai de remboursement…"
          />
          <button onClick={() => lancer()} disabled={loading}>
            {loading ? "…" : "Rechercher"}
          </button>
        </div>

        <div className="suggestions">
          {["retour", "livraison", "paiement", "compte"].map((item) => (
            <button key={item} onClick={() => lancer(item)}>
              {item}
            </button>
          ))}
        </div>

        {erreur && (
          <div className="warning-box" style={{ marginTop: "1rem" }}>
            <AlertTriangle size={18} />
            <div>
              <strong>Erreur</strong>
              <span>{erreur}</span>
            </div>
          </div>
        )}

        {resultats && resultats.length > 0 && (
          <div className="sources" style={{ marginTop: "1rem" }}>
            <div className="answer-label">
              {resultats.length} RÉSULTAT{resultats.length > 1 ? "S" : ""}
            </div>
            {resultats.map((r) => (
              <div className="source-row" key={r.id}>
                <span>{r.theme}</span>
                <strong>{r.question}</strong>
                <span style={{ marginLeft: "auto", opacity: 0.6 }}>
                  {r.score.toFixed(3)}
                </span>
              </div>
            ))}
          </div>
        )}

        {resultats && resultats.length === 0 && !erreur && (
          <p style={{ marginTop: "1rem" }}>Aucun résultat pour cette requête.</p>
        )}
      </section>
    </>
  );
}

/* ------------------------------------------------------------------ assistant */

function Assistant() {
  const [question, setQuestion] = useState("");
  const [reponse, setReponse] = useState<AssistantOut | null>(null);
  const [loading, setLoading] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  async function demander(texte = question) {
    if (!texte.trim()) return;
    setQuestion(texte);
    setLoading(true);
    setErreur(null);
    try {
      const data = await api.askAssistant({ question: texte, k: 3 });
      setReponse(data);
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Erreur inconnue";
      setErreur(msg);
      setReponse(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <section className="page-intro">
        <div>
          <div className="hero-kicker">
            <Bot size={15} />
            ASSISTANT DOCUMENTAIRE
          </div>
          <h2>Posez votre question</h2>
          <p>
            L'assistant cherche dans la base documentaire. Il cite ses sources
            et refuse s'il ne sait pas.
          </p>
        </div>
      </section>

      <section className="assistant-layout">
        <div className="panel assistant-main">
          <div className="assistant-head">
            <div className="bot-avatar">
              <Bot size={22} />
            </div>
            <div>
              <strong>Assistant DataFlow360</strong>
              <span>Recherche documentaire</span>
            </div>
          </div>

          <div className="question-row">
            <input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && demander()}
              placeholder="Ex. Comment suivre une commande ?"
            />
            <button onClick={() => demander()} disabled={loading}>
              {loading ? "…" : "Envoyer"}
            </button>
          </div>

          <div className="suggestions">
            {[
              "Comment suivre une commande ?",
              "Quel est le délai de remboursement ?",
              "Combien coûte un retour ?",
            ].map((item) => (
              <button key={item} onClick={() => demander(item)}>
                {item}
              </button>
            ))}
          </div>

          {erreur && (
            <div className="warning-box" style={{ marginTop: "1rem" }}>
              <AlertTriangle size={18} />
              <div>
                <strong>Erreur</strong>
                <span>{erreur}</span>
              </div>
            </div>
          )}

          {reponse && (
            <div className="answer-card">
              <div className="answer-label">
                {reponse.refus ? "REFUS" : "RÉPONSE"}
                {reponse.refus && reponse.motif && ` · ${reponse.motif}`}
                {!reponse.refus && ` · ${reponse.duree_ms} ms`}
              </div>
              <p>{reponse.reponse}</p>

              {reponse.passages.length > 0 && (
                <div className="sources">
                  <div className="answer-label">PASSAGES UTILISÉS</div>
                  {reponse.passages.map((p: Passage) => (
                    <div className="source-row" key={p.id}>
                      <span>{p.theme}</span>
                      <strong>{p.question}</strong>
                      <span style={{ marginLeft: "auto", opacity: 0.6 }}>
                        {p.score.toFixed(3)}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {reponse.suggestions.length > 0 && (
                <div className="sources">
                  <div className="answer-label">SUGGESTIONS</div>
                  {reponse.suggestions.map((p: Passage) => (
                    <div className="source-row" key={p.id}>
                      <span>{p.theme}</span>
                      <strong>{p.question}</strong>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        <div className="panel assistant-side">
          <div className="panel-kicker">PRINCIPE</div>
          <h3>Un assistant qui cite ses sources</h3>
          <p>
            Il sélectionne les passages pertinents dans la base documentaire. Il
            ne doit pas inventer une réponse absente de la base.
          </p>

          <div className="assistant-rule">
            <ShieldCheck size={18} />
            <span>Réponse traçable</span>
          </div>

          <div className="assistant-rule">
            <Search size={18} />
            <span>Recherche vectorielle</span>
          </div>

          <div className="assistant-rule">
            <AlertTriangle size={18} />
            <span>Refus si information hors base</span>
          </div>
        </div>
      </section>
    </>
  );
}