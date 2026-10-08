import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  Bot,
  Boxes,
  Database,
  Gauge,
  LayoutDashboard,
  Menu,
  MessageCircle,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  Users,
  X,
} from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type Page = "dashboard" | "prediction" | "assistant";

type Kpis = {
  chiffre_affaires: number;
  commandes: number;
  articles: number;
  panier_moyen: number;
  date_debut: string;
  date_fin: string;
};

type PredictionRow = {
  client_id: string;
  proba_retour: number;
  risque_depart: number;
};

type AssistantResponse = {
  question: string;
  refus: boolean;
  motif: string | null;
  reponse: string | null;
  passages: Array<{
    id: string;
    theme: string;
    question: string;
    source: string;
    score: number;
  }>;
  suggestions: Array<{
    id: string;
    question: string;
  }>;
};

const API = "http://localhost:8000/api";

const fallbackKpis: Kpis = {
  chiffre_affaires: 138420000,
  commandes: 99433,
  articles: 112650,
  panier_moyen: 1392,
  date_debut: "2016-09-04",
  date_fin: "2018-10-17",
};

const fallbackPrediction: PredictionRow[] = [
  { client_id: "C-10482", proba_retour: 0.11, risque_depart: 0.89 },
  { client_id: "C-08421", proba_retour: 0.14, risque_depart: 0.86 },
  { client_id: "C-13208", proba_retour: 0.17, risque_depart: 0.83 },
  { client_id: "C-09211", proba_retour: 0.19, risque_depart: 0.81 },
  { client_id: "C-04172", proba_retour: 0.22, risque_depart: 0.78 },
];

const salesData = [
  { label: "Nov", value: 18 },
  { label: "Déc", value: 24 },
  { label: "Jan", value: 21 },
  { label: "Fév", value: 28 },
  { label: "Mars", value: 31 },
  { label: "Avr", value: 35 },
  { label: "Mai", value: 39 },
  { label: "Juin", value: 43 },
];

const categoryData = [
  { name: "Informatique", value: 34 },
  { name: "Maison", value: 27 },
  { name: "Beauté", value: 21 },
  { name: "Autres", value: 18 },
];

const navItems = [
  { id: "dashboard" as Page, label: "Vue générale", icon: LayoutDashboard },
  { id: "prediction" as Page, label: "Prédiction", icon: TrendingUp },
  { id: "assistant" as Page, label: "Assistant client", icon: MessageCircle },
];

function formatMoney(value: number) {
  return new Intl.NumberFormat("fr-FR", {
    maximumFractionDigits: 0,
  }).format(value);
}

function formatNumber(value: number) {
  return new Intl.NumberFormat("fr-FR").format(value);
}

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

export default function App() {
  const [page, setPage] = useState<Page>("dashboard");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [kpis, setKpis] = useState<Kpis>(fallbackKpis);
  const [prediction, setPrediction] =
    useState<PredictionRow[]>(fallbackPrediction);
  const [apiOnline, setApiOnline] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    refreshDashboard();
  }, []);

  async function refreshDashboard() {
    setLoading(true);

    try {
      const data = await fetchJson<Kpis>(`${API}/kpis`);
      setKpis(data);
      setApiOnline(true);
    } catch {
      setKpis(fallbackKpis);
      setApiOnline(false);
    }

    try {
      const data = await fetchJson<PredictionRow[]>(`${API}/prediction`);
      setPrediction(data);
    } catch {
      setPrediction(fallbackPrediction);
    }

    setLoading(false);
  }

  const title = useMemo(
    () =>
      navItems.find((item) => item.id === page)?.label ?? "Vue générale",
    [page]
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
              <span>{apiOnline ? "API opérationnelle" : "Mode démonstration"}</span>
            </div>
            <p>
              Les données servent à alimenter le pilotage, la qualité et
              l'analyse client.
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
            >
              <Menu size={20} />
            </button>
            <div>
              <div className="eyebrow">ESPACE DE PILOTAGE</div>
              <h1>{title}</h1>
            </div>
          </div>

          <div className="topbar-actions">
            <button className="refresh-button" onClick={refreshDashboard}>
              <RefreshCw size={16} className={loading ? "spin" : ""} />
              Actualiser
            </button>
            <div className="avatar">MD</div>
          </div>
        </header>

        <div className="content">
          {page === "dashboard" && (
            <Dashboard kpis={kpis} onNavigate={setPage} />
          )}

          {page === "prediction" && (
            <Prediction prediction={prediction} />
          )}

          {page === "assistant" && <Assistant />}
        </div>
      </main>
    </div>
  );
}

function Dashboard({
  kpis,
  onNavigate,
}: {
  kpis: Kpis;
  onNavigate: (page: Page) => void;
}) {
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
            Vue synthétique de l’activité e-commerce, de la qualité des flux
            et des signaux utiles à l’équipe métier.
          </p>
        </div>

        <div className="hero-badge">
          <ShieldCheck size={17} />
          Pipeline supervisé
        </div>
      </section>

      <section className="kpi-grid">
        <KpiCard
          icon={ArrowUpRight}
          label="Chiffre d’affaires"
          value={`${formatMoney(kpis.chiffre_affaires)} FCFA`}
          trend="+12,4%"
        />
        <KpiCard
          icon={Boxes}
          label="Commandes"
          value={formatNumber(kpis.commandes)}
          trend="+8,7%"
        />
        <KpiCard
          icon={Database}
          label="Articles vendus"
          value={formatNumber(kpis.articles)}
          trend="+6,1%"
        />
        <KpiCard
          icon={Gauge}
          label="Panier moyen"
          value={`${formatMoney(kpis.panier_moyen)} FCFA`}
          trend="+3,8%"
        />
      </section>

      <section className="dashboard-grid">
        <div className="panel panel-large">
          <div className="panel-header">
            <div>
              <div className="panel-kicker">PERFORMANCE</div>
              <h3>Évolution du chiffre d’affaires</h3>
            </div>
            <span className="panel-tag">8 derniers mois</span>
          </div>

          <div className="chart">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={salesData}>
                <defs>
                  <linearGradient id="salesFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopOpacity={0.28} />
                    <stop offset="100%" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid vertical={false} strokeDasharray="4 4" />
                <XAxis dataKey="label" axisLine={false} tickLine={false} />
                <YAxis axisLine={false} tickLine={false} />
                <Tooltip />
                <Area
                  type="monotone"
                  dataKey="value"
                  strokeWidth={3}
                  fill="url(#salesFill)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">
            <div>
              <div className="panel-kicker">RÉPARTITION</div>
              <h3>CA par catégorie</h3>
            </div>
          </div>

          <div className="donut-wrap">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={categoryData}
                  dataKey="value"
                  nameKey="name"
                  innerRadius={56}
                  outerRadius={82}
                  paddingAngle={4}
                >
                  {categoryData.map((entry, index) => (
                    <Cell key={entry.name} fill={["#5b5bf7", "#8b5cf6", "#06b6d4", "#cbd5e1"][index]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>

            <div className="legend">
              {categoryData.map((item, index) => (
                <div className="legend-row" key={item.name}>
                  <span
                    className="legend-dot"
                    style={{
                      background:
                        ["#5b5bf7", "#8b5cf6", "#06b6d4", "#cbd5e1"][index],
                    }}
                  />
                  <span>{item.name}</span>
                  <strong>{item.value}%</strong>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="bottom-grid">
        <div className="panel quality-panel">
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

          <div className="quality-list">
            <QualityRow label="Collecte" value="100%" />
            <QualityRow label="Contrôle qualité" value="99,5%" />
            <QualityRow label="Intégration" value="99,2%" />
            <QualityRow label="Disponibilité" value="99,9%" />
          </div>

          <div className="warning-box">
            <AlertTriangle size={18} />
            <div>
              <strong>8 lignes d’articles orphelines</strong>
              <span>
                Les commandes correspondantes ont été envoyées en quarantaine
                par la règle OLIST_COMMANDES_02.
              </span>
            </div>
          </div>
        </div>

        <div className="panel action-panel">
          <div className="panel-kicker">ACCÈS RAPIDE</div>
          <h3>Explorer les signaux métier</h3>

          <button
            className="action-card"
            onClick={() => onNavigate("prediction")}
          >
            <div className="action-icon purple">
              <TrendingUp size={18} />
            </div>
            <div>
              <strong>Risque de départ</strong>
              <span>Identifier les clients à surveiller</span>
            </div>
            <ArrowUpRight size={17} />
          </button>

          <button
            className="action-card"
            onClick={() => onNavigate("assistant")}
          >
            <div className="action-icon blue">
              <Bot size={18} />
            </div>
            <div>
              <strong>Assistant client</strong>
              <span>Rechercher une réponse dans la base documentaire</span>
            </div>
            <ArrowUpRight size={17} />
          </button>
        </div>
      </section>
    </>
  );
}

function KpiCard({
  icon: Icon,
  label,
  value,
  trend,
}: {
  icon: typeof Activity;
  label: string;
  value: string;
  trend: string;
}) {
  return (
    <div className="kpi-card">
      <div className="kpi-top">
        <div className="kpi-icon">
          <Icon size={18} />
        </div>
        <span className="trend">{trend}</span>
      </div>
      <span className="kpi-label">{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function QualityRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="quality-row">
      <span>{label}</span>
      <div className="quality-bar">
        <span style={{ width: value }} />
      </div>
      <strong>{value}</strong>
    </div>
  );
}

function Prediction({ prediction }: { prediction: PredictionRow[] }) {
  return (
    <>
      <section className="page-intro">
        <div>
          <div className="hero-kicker">
            <TrendingUp size={15} />
            SIGNAL PRÉDICTIF
          </div>
          <h2>Clients à surveiller</h2>
          <p>
            Le score constitue un signal complémentaire. La règle opérationnelle
            reste basée sur l’historique de commandes.
          </p>
        </div>

        <div className="info-pill">
          <Users size={16} />
          {prediction.length} profils affichés
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <div className="panel-kicker">PRIORISATION</div>
            <h3>Top des risques</h3>
          </div>
          <div className="search-box">
            <Search size={16} />
            <input placeholder="Rechercher un client..." />
          </div>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Client</th>
                <th>Probabilité de retour</th>
                <th>Risque de départ</th>
                <th>Niveau</th>
              </tr>
            </thead>
            <tbody>
              {prediction.map((row) => (
                <tr key={row.client_id}>
                  <td className="client-id">{row.client_id}</td>
                  <td>{Math.round(row.proba_retour * 100)}%</td>
                  <td>
                    <div className="risk-cell">
                      <div className="risk-bar">
                        <span style={{ width: `${row.risque_depart * 100}%` }} />
                      </div>
                      <strong>{Math.round(row.risque_depart * 100)}%</strong>
                    </div>
                  </td>
                  <td>
                    <span className="risk-badge">À surveiller</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}

function Assistant() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<AssistantResponse | null>(null);
  const [loading, setLoading] = useState(false);

  async function askQuestion(text = question) {
    if (!text.trim()) return;

    setQuestion(text);
    setLoading(true);

    try {
      const response = await fetch(`${API}/assistant`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: text }),
      });

      if (!response.ok) throw new Error("Assistant indisponible");

      setAnswer(await response.json());
    } catch {
      setAnswer({
        question: text,
        refus: false,
        motif: null,
        reponse:
          "Le backend assistant n’est pas disponible actuellement. L’interface est prête et attend la réponse du service documentaire.",
        passages: [],
        suggestions: [],
      });
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
            L’assistant recherche une réponse dans la base documentaire et
            affiche les passages utilisés.
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
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") askQuestion();
              }}
              placeholder="Ex. Comment suivre une commande ?"
            />
            <button onClick={() => askQuestion()} disabled={loading}>
              {loading ? "..." : "Envoyer"}
            </button>
          </div>

          <div className="suggestions">
            {[
              "Comment suivre une commande ?",
              "Quels sont les délais de livraison ?",
              "Comment fonctionne le remboursement ?",
            ].map((item) => (
              <button key={item} onClick={() => askQuestion(item)}>
                {item}
              </button>
            ))}
          </div>

          {answer && (
            <div className="answer-card">
              <div className="answer-label">RÉPONSE</div>
              <p>{answer.reponse}</p>

              {answer.passages.length > 0 && (
                <div className="sources">
                  <div className="answer-label">PASSAGES UTILISÉS</div>
                  {answer.passages.map((passage) => (
                    <div className="source-row" key={passage.id}>
                      <span>{passage.theme}</span>
                      <strong>{passage.question}</strong>
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
            Il sélectionne les passages pertinents dans la base documentaire.
            Il ne doit pas inventer une réponse absente de la base.
          </p>

          <div className="assistant-rule">
            <ShieldCheck size={18} />
            <span>Réponse traçable</span>
          </div>

          <div className="assistant-rule">
            <Search size={18} />
            <span>Recherche ciblée</span>
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