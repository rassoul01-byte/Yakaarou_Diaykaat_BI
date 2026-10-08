import { useState } from "react";
import { AlertTriangle, Search } from "lucide-react";

import { ApiError, api } from "../api/client";
import type { Produit } from "../types/api";

export default function RecherchePage() {
  const [q, setQ] = useState("");
  const [produits, setProduits] = useState<Produit[] | null>(null);
  const [total, setTotal] = useState<number | null>(null);
  const [temps, setTemps] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  async function lancer(question = q) {
    if (!question.trim()) return;
    setQ(question);
    setLoading(true);
    setErreur(null);
    try {
      const data = await api.rechercher({ q: question, k: 10 });
      setProduits(data.produits);
      setTotal(data.total);
      setTemps(data.temps_serveur_ms);
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Erreur inconnue";
      setErreur(msg);
      setProduits([]);
      setTotal(null);
      setTemps(null);
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
            RECHERCHE PRODUITS
          </div>
          <h2>Interroger le catalogue</h2>
          <p>
            Recherche dans le catalogue Rakuten. Résultats classés par
            pertinence. Aucun prix affiché : le catalogue n'en contient pas.
          </p>
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <div className="panel-kicker">REQUÊTE</div>
            <h3>Votre recherche</h3>
          </div>
          {total !== null && temps !== null && (
            <span className="panel-tag">
              {total} résultat{total > 1 ? "s" : ""} · {temps} ms
            </span>
          )}
        </div>

        <div className="question-row">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && lancer()}
            placeholder="Ex. chaise de bureau, lampe, tapis…"
          />
          <button onClick={() => lancer()} disabled={loading}>
            {loading ? "…" : "Rechercher"}
          </button>
        </div>

        <div className="suggestions">
          {["chaise de bureau", "lampe", "tapis", "coussin"].map((item) => (
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

        {produits && produits.length > 0 && (
          <div className="sources" style={{ marginTop: "1rem" }}>
            <div className="answer-label">
              {produits.length} PRODUIT{produits.length > 1 ? "S" : ""} AFFICHÉ
              {produits.length > 1 ? "S" : ""}
            </div>
            {produits.map((p) => (
              <div className="source-row" key={p.product_id}>
                <span>{p.categorie_code || "—"}</span>
                <strong>{p.designation}</strong>
                <span style={{ marginLeft: "auto", opacity: 0.6 }}>
                  {p.score.toFixed(2)}
                </span>
              </div>
            ))}
          </div>
        )}

        {produits && produits.length === 0 && !erreur && (
          <p style={{ marginTop: "1rem" }}>Aucun résultat pour cette requête.</p>
        )}
      </section>
    </>
  );
}
