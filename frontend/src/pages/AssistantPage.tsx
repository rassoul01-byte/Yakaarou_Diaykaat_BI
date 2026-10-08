import { useState } from "react";
import { AlertTriangle, Bot, Search, ShieldCheck } from "lucide-react";

import { ApiError, api } from "../api/client";
import BoutonRetry from "../components/BoutonRetry";
import { SkeletonAssistant } from "../components/Skeleton";
import type { AssistantOut, Passage, Suggestion } from "../types/api";

const CLE_LOCALSTORAGE = "assistant.derniereQuestion";

export default function AssistantPage() {
  const [question, setQuestion] = useState(
    () => localStorage.getItem(CLE_LOCALSTORAGE) ?? "",
  );  const [reponse, setReponse] = useState<AssistantOut | null>(null);
  const [loading, setLoading] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  async function demander(texte = question) {
    if (!texte.trim()) return;
    setQuestion(texte);
    localStorage.setItem(CLE_LOCALSTORAGE, texte);
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
              disabled={loading}
            />
            <button onClick={() => demander()} disabled={loading}>
              {loading ? "Recherche…" : "Envoyer"}
            </button>
          </div>

          <div className="suggestions">
            {[
              "Comment suivre une commande ?",
              "Quel est le délai de remboursement ?",
              "Combien coûte un retour ?",
            ].map((item) => (
              <button key={item} onClick={() => demander(item)} disabled={loading}>
                {item}
              </button>
            ))}
          </div>

          {loading && <SkeletonAssistant />}

          {erreur && !loading && (
            <BoutonRetry message={erreur} onRetry={() => demander()} />
          )}

          {reponse && !loading && !erreur && (
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
                  {reponse.passages.map((p: Passage, i: number) => (
                    <div
                      className="source-row"
                      key={p.id}
                      style={{ animationDelay: `${i * 60}ms` }}
                    >
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
                  {reponse.suggestions.map((s: Suggestion, i: number) => (
                    <div
                      className="source-row"
                      key={s.id}
                      style={{ animationDelay: `${i * 60}ms` }}
                    >
                      <strong>{s.question}</strong>
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
