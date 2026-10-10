/** Vue générale — direction « Flux ».
 *
 * La page lit `GET /api/indicateurs` et n'affiche rien qu'elle n'ait reçu.
 * Chaque bloc sait se taire : sur une base montée mais jamais chargée, l'API
 * renvoie 200 avec des blocs nuls, et la page le dit au lieu de mentir.
 */

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Check, Minus, X } from "lucide-react";

import { api, ApiError } from "../api/client";
import BoutonRetry from "../components/BoutonRetry";
import { SkeletonBloc, SkeletonLigne } from "../components/Skeleton";
import { useCompteur } from "../components/useCompteur";
import type { Etape, IndicateursOut } from "../types/api";
import "./DashboardPage.css";

// --------------------------------------------------------------- formats

const NOMBRE = new Intl.NumberFormat("fr-FR");
const MONTANT = new Intl.NumberFormat("fr-FR", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/* `Intl` sépare les milliers par une espace fine insécable (U+202F). Dans
   Familjen Grotesk elle est si étroite que « 1 550 922 » se lit « 1550922 ».
   On la remplace par l'espace insécable ordinaire (U+00A0), qui respire. */
function espacer(texte: string): string {
  return texte.replace(/ /g, " ");
}

function nombre(valeur: number | null | undefined): string {
  return valeur === null || valeur === undefined ? "—" : espacer(NOMBRE.format(valeur));
}

function montant(valeur: number | null | undefined): string {
  return valeur === null || valeur === undefined ? "—" : espacer(MONTANT.format(valeur));
}

/** Une moyenne de comptages : une décimale suffit, deux font faussement précis. */
function decimale(valeur: number | null | undefined): string {
  if (valeur === null || valeur === undefined) return "—";
  return espacer(valeur.toLocaleString("fr-FR", { maximumFractionDigits: 1 }));
}

function pourcent(valeur: number | null | undefined, decimales = 2): string {
  if (valeur === null || valeur === undefined) return "—";
  const chiffre = espacer(
    valeur.toLocaleString("fr-FR", {
      minimumFractionDigits: decimales,
      maximumFractionDigits: decimales,
    }),
  );
  return `${chiffre} %`;
}

/** Une étape à 0,0 seconde n'a pas duré zéro : elle a duré moins d'une seconde. */
function duree(secondes: number | null): string {
  if (secondes === null) return "—";
  if (secondes < 1) return "< 1 s";
  if (secondes < 60) return `${secondes.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} s`;
  const minutes = Math.floor(secondes / 60);
  const reste = Math.round(secondes % 60);
  return `${minutes} min ${String(reste).padStart(2, "0")}`;
}

function jourCourt(horodatage: string | null): string {
  if (!horodatage) return "—";
  return horodatage.slice(0, 10);
}

// --------------------------------------------------------------- chiffres

type Formateur = (valeur: number | null | undefined) => string;

/** Un chiffre qui monte, dans son format définitif.
 *
 * Un composant plutôt qu'un appel direct à `useCompteur` : il y a dix chiffres
 * animés sur cette page, et dix appels de hook alignés dans un même composant
 * se lisent mal et se réordonnent mal.
 */
function Chiffre({
  valeur,
  format,
  className,
  style,
}: {
  valeur: number | null | undefined;
  format: Formateur;
  className?: string;
  style?: React.CSSProperties;
}) {
  const anime = useCompteur(valeur);
  return (
    <span className={className} style={style}>
      {format(anime)}
    </span>
  );
}

// --------------------------------------------------------------- page

export default function DashboardPage() {
  const [donnees, setDonnees] = useState<IndicateursOut | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [chargement, setChargement] = useState(true);

  /* `recuperer` ne touche à l'état qu'après la réponse : appelée depuis l'effet,
     elle ne déclenche donc pas de rendu en cascade au montage. La remise à zéro
     avant un nouvel essai appartient au bouton, pas à l'effet. */
  const recuperer = useCallback(() => {
    api
      .indicateurs()
      .then(setDonnees)
      .catch((cause: unknown) => {
        setErreur(
          cause instanceof ApiError ? cause.message : "Impossible de lire les indicateurs",
        );
      })
      .finally(() => setChargement(false));
  }, []);

  const reessayer = useCallback(() => {
    setChargement(true);
    setErreur(null);
    recuperer();
  }, [recuperer]);

  useEffect(() => {
    recuperer();
  }, [recuperer]);

  if (chargement && !donnees) {
    return (
      <div className="vg">
        <div className="vg-panel">
          <SkeletonLigne largeur="moyen" />
          <SkeletonBloc />
        </div>
        <div className="vg-rangee">
          <div className="vg-panel vg-large">
            <SkeletonLigne largeur="court" />
            <SkeletonLigne largeur="plein" />
          </div>
          <div className="vg-panel vg-etroit">
            <SkeletonLigne largeur="court" />
            <SkeletonLigne largeur="plein" />
          </div>
        </div>
      </div>
    );
  }

  if (erreur || !donnees) {
    return (
      <div className="vg">
        <BoutonRetry message={erreur ?? "Aucune donnée reçue"} onRetry={reessayer} />
      </div>
    );
  }

  const { ventes, categories, qualite, motifs_de_rejet, jour, alerte, segment, chaine } = donnees;

  /* L'ordre compte. Le chiffre d'affaires passe AVANT le schéma : le schéma
     explique comment la plateforme fonctionne, le chiffre dit ce qu'elle
     produit, et c'est le second qu'on doit voir sans dérouler. Le schéma
     occupait six cents pixels de haut, ce qui poussait la figure principale
     sous la ligne de flottaison en 1440 × 900.

     `cascade` fait entrer les blocs l'un après l'autre, à 90 ms d'écart (voir
     index.css) ; le dernier arrive à 540 ms, avant qu'on ait fini de lire le
     premier titre. */
  return (
    <div className="vg cascade">
      <header>
        <h1>Yakaarou Diaykaat BI, en un écran</h1>
        <p className="vg-chapeau">
          Les ventes, la qualité des données et l&apos;activité du jour. Chaque chiffre de cette
          page vient d&apos;une vue de l&apos;entrepôt : la page les met en forme, elle n&apos;en
          recalcule aucun.
        </p>
      </header>
      <Ventes ventes={ventes} qualite={qualite} alerte={alerte} />
      <Chaine chaine={chaine} donnees={donnees} />
      <Categories categories={categories} />
      <Qualite qualite={qualite} motifs={motifs_de_rejet} />
      <Journee jour={jour} simule={donnees.trafic_simule} segment={segment} />
      <Etapes chaine={chaine} />
    </div>
  );
}

// --------------------------------------------------------------- le schéma

type SchemaProps = { chaine: Etape[]; donnees: IndicateursOut };

function Chaine({ chaine, donnees }: SchemaProps) {
  const { ventes, qualite, jour, segment } = donnees;

  // Les sources ne sont pas dans la réponse : on les déduit des étapes
  // d'acquisition, qui les nomment. C'est la même liste que `qualite.sources`.
  const sources = [
    ...new Set(
      chaine.filter((e) => e.pipeline === "acquisition").map((e) => e.source ?? "source"),
    ),
  ].slice(0, 5);

  const lues = qualite?.lignes_lues ?? null;
  const rejetees = qualite?.lignes_rejetees ?? null;

  /* Géométrie du schéma. Tout est dérivé de `milieu` : les boîtes grandissent
     avec la typographie sans qu'aucune coordonnée soit à reprendre à la main.

     La hauteur a un plancher de 400 plutôt que 300 : la quarantaine descend à
     `milieu + 184` et le premier usage monte à `milieu - 135`, donc il faut
     388 d'espace même avec deux sources. */
  const hauteurSources = Math.max(sources.length, 1) * 62;
  const hauteur = Math.max(hauteurSources, 400);
  const milieu = hauteur / 2;
  const railHaut = Math.min(32, milieu);
  const railBas = Math.max(32 + (sources.length - 1) * 62, milieu);

  return (
    <section className="vg-panel">
      <h2>Ce que la plateforme a traité</h2>
      <p className="vg-chapeau">
        Les sources entrent à gauche, passent le contrôle qualité, et ressortent à droite dans
        les trois usages. Ce qui ne passe pas descend en quarantaine.
      </p>

      <div className="vg-cadre-schema">
      <svg
        className="vg-schema"
        viewBox={`0 0 1300 ${hauteur + 30}`}
        role="img"
        preserveAspectRatio="xMidYMid meet"
      >
        <title>
          Schéma de la chaîne de traitement : {sources.length} sources, le contrôle qualité, la
          quarantaine, l&apos;entrepôt et les trois usages
        </title>

        {/* Les liaisons. `pathLength="1"` normalise la longueur de chaque
            chemin : un seul `stroke-dashoffset` suffit alors à tracer un trait
            de quarante pixels comme un rail de trois cents (voir le CSS). Les
            classes `vg-liaison-1` à `-4` donnent l'ordre du tracé, qui est
            l'ordre du pipeline. */}
        <g stroke="#b8cde6" strokeWidth="1.5" fill="none">
          {sources.map((_, i) => (
            <path
              key={i}
              className="vg-liaison vg-liaison-1"
              pathLength="1"
              d={`M192 ${32 + i * 62} H232`}
            />
          ))}
          {/* Le rail vertical doit atteindre la dérivation vers la porte :
              avec peu de sources, il s'arrêtait quatre pixels trop haut et la
              liaison paraissait coupée. */}
          <path
            className="vg-liaison vg-liaison-1"
            pathLength="1"
            d={`M232 ${railHaut} V${railBas}`}
          />
          <path
            className="vg-liaison vg-liaison-2"
            pathLength="1"
            d={`M232 ${milieu} H286`}
          />
          <path
            className="vg-liaison vg-liaison-3"
            pathLength="1"
            d={`M476 ${milieu} H534`}
          />
          <path
            className="vg-liaison vg-liaison-4"
            pathLength="1"
            d={`M792 ${milieu - 100} V${milieu + 100}`}
          />
          <path
            className="vg-liaison vg-liaison-4"
            pathLength="1"
            d={`M792 ${milieu - 100} H840`}
          />
          <path
            className="vg-liaison vg-liaison-4"
            pathLength="1"
            d={`M792 ${milieu + 100} H840`}
          />
        </g>

        {/* Le chemin de l'entrepôt vers les usages : un pointillé qui avance
            en permanence. C'est le « flux » du nom de la direction, et le seul
            mouvement de la page qui ne s'arrête jamais. */}
        <path
          className="vg-flux"
          d={`M744 ${milieu} H840`}
          stroke="#1583ec"
          strokeWidth="2.5"
          fill="none"
        />

        {/* La descente vers la quarantaine, tracée après tout le reste : on
            doit la voir partir du contrôle qualité. */}
        <path
          className="vg-rejet"
          pathLength="1"
          d={`M381 ${milieu + 44} V${milieu + 104}`}
          stroke="#e63946"
          strokeWidth="2.5"
          fill="none"
        />

        {/* sources */}
        <g fontSize="16" fill="#0f1c2e">
          {sources.map((source, i) => (
            <g key={source} className="vg-boite vg-boite-source">
              <rect
                x="8"
                y={10 + i * 62}
                width="184"
                height="44"
                rx="8"
                fill="#ffffff"
                stroke="#dce6f4"
              />
              <text x="22" y={38 + i * 62} fontWeight="500">
                {source}
              </text>
            </g>
          ))}
        </g>

        {/* contrôle qualité */}
        <g className="vg-boite vg-boite-controle">
          <rect
            x="286"
            y={milieu - 44}
            width="190"
            height="88"
            rx="9"
            fill="#ffffff"
            stroke="#0a6bd4"
            strokeWidth="1.75"
          />
          <text x="306" y={milieu - 8} fontSize="18" fontWeight="600" fill="#0f1c2e">
            Contrôle qualité
          </text>
          <text x="306" y={milieu + 18} fontSize="15" fill="#44566e">
            {nombre(lues)} lignes lues
          </text>
        </g>

        {/* quarantaine */}
        <g className="vg-boite vg-boite-quarantaine">
          <rect
            x="286"
            y={milieu + 104}
            width="190"
            height="80"
            rx="9"
            fill="#fdecee"
            stroke="#e63946"
            strokeWidth="1.75"
          />
          <text x="306" y={milieu + 134} fontSize="17" fontWeight="600" fill="#a4242f">
            Quarantaine
          </text>
          <text x="306" y={milieu + 158} fontSize="15" fill="#a4242f">
            {nombre(rejetees)} lignes, {pourcent(qualite?.taux_rejet_pourcent, 3)}
          </text>
        </g>

        {/* entrepôt */}
        <g className="vg-boite vg-boite-entrepot">
          <rect x="534" y={milieu - 54} width="210" height="108" rx="9" fill="#0f1c2e" />
          <text x="556" y={milieu - 18} fontSize="19" fontWeight="600" fill="#ffffff">
            Entrepôt
          </text>
          <text x="556" y={milieu + 8} fontSize="15.5" fill="#c8e2ff">
            {nombre(ventes?.commandes)} commandes
          </text>
          <text x="556" y={milieu + 32} fontSize="15.5" fill="#c8e2ff">
            {montant(ventes?.chiffre_affaires)}
          </text>
        </g>

        {/* usages */}
        <g className="vg-boite vg-boite-usage">
          <rect
            x="840"
            y={milieu - 135}
            width="452"
            height="70"
            rx="9"
            fill="#ffffff"
            stroke="#dce6f4"
          />
          <text x="864" y={milieu - 105} fontSize="17" fontWeight="600" fill="#0f1c2e">
            Recherche
          </text>
          <text x="864" y={milieu - 81} fontSize="15" fill="#44566e">
            {nombre(jour?.recherches)} requêtes le {jour?.jour ?? "—"}
          </text>
        </g>
        <g className="vg-boite vg-boite-usage">
          <rect
            x="840"
            y={milieu - 35}
            width="452"
            height="70"
            rx="9"
            fill="#ffffff"
            stroke="#1583ec"
            strokeWidth="1.75"
          />
          <circle cx="866" cy={milieu - 9} r="5" fill="#1583ec" />
          <text x="882" y={milieu - 3} fontSize="17" fontWeight="600" fill="#0f1c2e">
            Temps réel
          </text>
          <text x="864" y={milieu + 21} fontSize="15" fill="#44566e">
            {nombre(jour?.sessions)} sessions, {nombre(jour?.achats)} achats
          </text>
        </g>
        <g className="vg-boite vg-boite-usage">
          <rect
            x="840"
            y={milieu + 65}
            width="452"
            height="70"
            rx="9"
            fill="#ffffff"
            stroke="#dce6f4"
          />
          <text x="864" y={milieu + 95} fontSize="17" fontWeight="600" fill="#0f1c2e">
            Modèle de réachat
          </text>
          <text x="864" y={milieu + 119} fontSize="15" fill="#44566e">
            {nombre(segment?.clients)} clients retenus
          </text>
        </g>
      </svg>
      </div>
    </section>
  );
}

// --------------------------------------------------------------- ventes

type VentesProps = Pick<IndicateursOut, "ventes" | "qualite" | "alerte">;

function Ventes({ ventes, qualite, alerte }: VentesProps) {
  return (
    <section className="vg-rangee">
      <div className={`vg-large ${ventes ? "vg-heros-carte" : "vg-panel"}`}>
        {ventes ? (
          <div className="vg-figures">
            <div>
              <div className="vg-heros-etiquette">Chiffre d&apos;affaires, hors frais de port</div>
              <div style={{ marginTop: 14 }}>
                <Chiffre
                  className="vg-figure vg-heros"
                  valeur={ventes.chiffre_affaires}
                  format={montant}
                />
              </div>
              <div className="vg-libelle">
                {ventes.premier_jour && ventes.dernier_jour
                  ? `du ${ventes.premier_jour} au ${ventes.dernier_jour}`
                  : "sur l'ensemble de la période"}
              </div>
            </div>
            <div className="vg-figures-petites">
              <div>
                <Chiffre
                  className="vg-figure vg-moyen"
                  valeur={ventes.panier_moyen}
                  format={montant}
                />
                <div className="vg-libelle">Panier moyen</div>
              </div>
              <div>
                <Chiffre
                  className="vg-figure vg-moyen"
                  valeur={ventes.commandes}
                  format={nombre}
                />
                <div className="vg-libelle">Commandes retenues</div>
              </div>
              <div>
                <Chiffre
                  className="vg-figure vg-moyen"
                  valeur={qualite?.taux_rejet_pourcent}
                  format={(v) => pourcent(v, 3)}
                />
                <div className="vg-libelle">Lignes écartées</div>
              </div>
            </div>
          </div>
        ) : (
          <p className="vg-vide">
            Aucune vente dans l&apos;entrepôt. Lancer le chargement, puis actualiser.
          </p>
        )}
      </div>

      {alerte ? (
        <div className="vg-alerte vg-etroit">
          <div className="vg-alerte-tete">
            <AlertTriangle size={22} color="var(--vg-rouge)" aria-hidden />
            <Chiffre className="vg-alerte-nombre" valeur={alerte.achats} format={nombre} />
            <span style={{ fontSize: "var(--t-base)", color: "var(--vg-rouge-ink)" }}>
              achats, contre {decimale(alerte.achats_habituels)} d&apos;habitude
            </span>
          </div>
          <p>
            Le {alerte.jour}, la journée est à {pourcent(alerte.niveau_pourcent, 1)} du niveau
            habituel, sous le seuil de {pourcent(alerte.seuil_pourcent, 0)}. Comparaison sur{" "}
            {alerte.jours_compares} même jour de la semaine.
          </p>
        </div>
      ) : (
        <div className="vg-panel vg-etroit">
          <h2>Surveillance des ventes</h2>
          <p className="vg-vide">
            Aucune journée sous le seuil. L&apos;alerte reste silencieuse, et c&apos;est le
            comportement attendu : une alerte qui se déclenche tous les jours n&apos;est plus lue.
          </p>
        </div>
      )}
    </section>
  );
}

// --------------------------------------------------------------- catégories

function Categories({ categories }: Pick<IndicateursOut, "categories">) {
  if (categories.length === 0) return null;

  const maximum = Math.max(...categories.map((c) => c.chiffre_affaires ?? 0), 1);

  return (
    <section className="vg-panel">
      <div className="vg-entete-bloc">
        <h2>Chiffre d&apos;affaires par catégorie</h2>
        <span className="vg-puce vg-puce-neutre">{categories.length} premières</span>
      </div>
      <div className="vg-defilant">
      <table className="vg-table">
        <thead>
          <tr>
            {/* 250 et non 210 : à la taille de texte actuelle,
                « informatica_acessorios » touchait sa barre. */}
            <th style={{ width: 250, paddingRight: 18 }}>Catégorie</th>
            <th aria-label="Part relative" />
            <th className="vg-chiffre">Chiffre d&apos;affaires</th>
          </tr>
        </thead>
        <tbody>
          {categories.map((categorie, rang) => (
            <tr key={categorie.categorie ?? rang}>
              <td
                className={rang === 0 ? "vg-tete" : undefined}
                style={{ paddingRight: 18 }}
              >
                {categorie.categorie ?? "inconnu"}
              </td>
              <td className="vg-cell-barre">
                {/* Les barres poussent de haut en bas, 60 ms d'écart : le
                    classement se lit dans l'ordre où il s'installe. */}
                <div
                  className={`vg-barre${rang === 0 ? " vg-barre-tete" : ""}`}
                  style={{
                    width: `${(((categorie.chiffre_affaires ?? 0) / maximum) * 100).toFixed(1)}%`,
                    animationDelay: `${260 + rang * 60}ms`,
                  }}
                />
              </td>
              <td className={`vg-chiffre${rang === 0 ? " vg-tete" : ""}`}>
                {montant(categorie.chiffre_affaires)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
    </section>
  );
}

// --------------------------------------------------------------- qualité

type QualiteProps = { qualite: IndicateursOut["qualite"]; motifs: IndicateursOut["motifs_de_rejet"] };

function Qualite({ qualite, motifs }: QualiteProps) {
  if (!qualite) return null;

  const taux = qualite.taux_rejet_pourcent ?? 0;
  const total = motifs.reduce((somme, motif) => somme + motif.rejets, 0);
  const dominant = motifs[0];
  const partDominante = total > 0 && dominant ? (100 * dominant.rejets) / total : null;

  return (
    <section className="vg-rangee">
      <div className="vg-panel vg-large">
        <h2>Ce que le contrôle qualité a écarté</h2>
        <p className="vg-chapeau">
          {nombre(qualite.lignes_rejetees)} lignes sur {nombre(qualite.lignes_lues)} lues, à
          travers {nombre(qualite.sources)} sources.
        </p>

        <div className="vg-jauge" style={{ marginTop: 20 }} role="img"
          aria-label={`Part des lignes écartées : ${pourcent(taux, 3)}`}>
          <div className="vg-jauge-reste" />
          <div className="vg-jauge-rejet" style={{ width: `${taux}%` }} />
        </div>
        <p className="vg-note">
          Le vert, ce sont les lignes acceptées. Le rouge occupe {pourcent(taux, 3)} de la barre :
          à cette échelle il tient dans un pixel, et c&apos;est précisément le résultat cherché.
        </p>

        <div className="vg-separateur">
          <p className="vg-note" style={{ marginTop: 0 }}>
            La même bande, grossie cent fois :
          </p>
          <div className="vg-jauge vg-jauge-loupe" style={{ marginTop: 10 }} aria-hidden>
            <div className="vg-jauge-reste" />
            <div className="vg-jauge-rejet" style={{ width: `${Math.min(taux * 100, 100)}%` }} />
          </div>
        </div>
      </div>

      <div className="vg-panel vg-etroit">
        <h2>Pourquoi elles ont été écartées</h2>
        {motifs.length === 0 ? (
          <p className="vg-vide">Aucun rejet enregistré.</p>
        ) : (
          <>
            <table className="vg-table">
              <thead>
                <tr>
                  <th>Règle</th>
                  <th className="vg-chiffre">Lignes</th>
                </tr>
              </thead>
              <tbody>
                {motifs.map((motif) => (
                  <tr key={motif.regle}>
                    <td>
                      <span className="vg-tete">{motif.regle}</span>
                      {motif.gravite ? (
                        <div
                          style={{
                            fontSize: "var(--t-petit)",
                            color: "var(--vg-ink-3)",
                            marginTop: 3,
                          }}
                        >
                          {motif.gravite}
                        </div>
                      ) : null}
                    </td>
                    <td className="vg-chiffre vg-tete">{nombre(motif.rejets)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {partDominante !== null && dominant ? (
              <p className="vg-note">
                À elle seule, {dominant.regle} explique {pourcent(partDominante, 1)} des rejets.
                Rien n&apos;est supprimé : chaque ligne part en quarantaine avec son motif, et
                reste rejouable.
              </p>
            ) : null}
          </>
        )}
      </div>
    </section>
  );
}

// --------------------------------------------------------------- journée

type JourneeProps = {
  jour: IndicateursOut["jour"];
  segment: IndicateursOut["segment"];
  simule: boolean;
};

function Journee({ jour, segment, simule }: JourneeProps) {
  return (
    <section className="vg-rangee">
      <div className="vg-panel vg-large">
        <div className="vg-entete-bloc">
          <h2>Compteurs du {jour?.jour ?? "jour"}</h2>
          {simule ? (
            <span className="vg-puce vg-puce-neutre">
              Trafic simulé, pas des visiteurs réels
            </span>
          ) : null}
        </div>

        {jour ? (
          <div className="vg-compteurs">
            <div>
              <Chiffre className="vg-figure vg-moyen" valeur={jour.sessions} format={nombre} />
              <div className="vg-libelle">Sessions</div>
            </div>
            <div>
              <Chiffre className="vg-figure vg-moyen" valeur={jour.pages_vues} format={nombre} />
              <div className="vg-libelle">Pages vues</div>
            </div>
            <div>
              <Chiffre className="vg-figure vg-moyen" valeur={jour.recherches} format={nombre} />
              <div className="vg-libelle">Recherches</div>
            </div>
            <div>
              <Chiffre
                className="vg-figure vg-moyen"
                valeur={jour.ajouts_panier}
                format={nombre}
              />
              <div className="vg-libelle">Paniers</div>
            </div>
            <div>
              <Chiffre className="vg-figure vg-moyen" valeur={jour.achats} format={nombre} />
              <div className="vg-libelle">Achats</div>
            </div>
            <div>
              <Chiffre
                className="vg-figure vg-moyen"
                valeur={jour.taux_conversion_pourcent}
                format={(v) => pourcent(v)}
              />
              <div className="vg-libelle">
                Conversion sur {nombre(jour.sessions_avec_achat)} sessions
              </div>
            </div>
          </div>
        ) : (
          <p className="vg-vide">
            Aucun événement reçu. Lancer le générateur, puis les compteurs.
          </p>
        )}

        {jour ? (
          <p className="vg-note">
            Les événements ne portent aucun montant : ces compteurs mesurent l&apos;activité, pas
            le chiffre d&apos;affaires. Les {nombre(jour.achats)} achats sont des événements, et
            les {nombre(jour.sessions_avec_achat)} sessions avec achat en sont le décompte par
            session — deux chiffres proches, deux définitions.
          </p>
        ) : null}
      </div>

      <div className="vg-panel vg-etroit">
        <h2>Le segment à retenir</h2>
        {segment ? (
          <>
            <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
              <Chiffre
                className="vg-figure"
                style={{ fontSize: 48, color: "var(--vg-bleu)" }}
                valeur={segment.clients}
                format={nombre}
              />
              <span style={{ fontSize: "var(--t-base)", color: "var(--vg-ink-2)" }}>
                clients ayant commandé deux fois
              </span>
            </div>
            <p className="vg-note">
              Règle retenue plutôt qu&apos;un score de modèle, qui ne faisait pas mieux sur ce
              volume. Date de référence : {segment.date_reference ?? "—"}.
            </p>
          </>
        ) : (
          <p className="vg-vide">Aucun client ne remplit la règle à la date de référence.</p>
        )}
      </div>
    </section>
  );
}

// --------------------------------------------------------------- étapes

function iconeStatut(statut: string) {
  if (statut === "succes") return <Check size={14} color="var(--vg-vert)" aria-hidden />;
  if (statut === "inchange") return <Minus size={14} color="var(--vg-ink-3)" aria-hidden />;
  return <X size={14} color="var(--vg-rouge)" aria-hidden />;
}

function Etapes({ chaine }: { chaine: Etape[] }) {
  if (chaine.length === 0) return null;

  /* Regroupées par pipeline, dans l'ordre de première apparition. Les étapes
     arrivent triées par date, donc les pipelines s'entrelacent : un
     regroupement par suites consécutives afficherait « acquisition » deux fois. */
  const parPipeline = new Map<string, Etape[]>();
  for (const etape of chaine) {
    const existantes = parPipeline.get(etape.pipeline);
    if (existantes) existantes.push(etape);
    else parPipeline.set(etape.pipeline, [etape]);
  }
  const pipelines = [...parPipeline].map(([nom, etapes]) => ({ nom, etapes }));

  const jours = [...new Set(chaine.map((e) => jourCourt(e.demarre_a)))].sort();
  const echecs = chaine.filter((e) => e.statut !== "succes" && e.statut !== "inchange").length;

  return (
    <section className="vg-panel">
      <div className="vg-entete-bloc">
        <h2>Dernière exécution de chaque étape</h2>
        <span className={`vg-puce ${echecs === 0 ? "vg-puce-vert" : "vg-puce-neutre"}`}>
          {echecs === 0
            ? `${chaine.length} étapes, aucun échec`
            : `${echecs} étape(s) en échec sur ${chaine.length}`}
        </span>
      </div>

      <div className="vg-defilant">
      <table className="vg-table">
        <thead>
          <tr>
            <th>Étape</th>
            <th>Source</th>
            <th className="vg-chiffre">Lignes lues</th>
            <th className="vg-chiffre">Écartées</th>
            <th className="vg-chiffre">Durée</th>
            <th className="vg-chiffre">Le</th>
          </tr>
        </thead>
        {pipelines.map((pipeline) => (
          <tbody key={pipeline.nom}>
            <tr>
              <td className="vg-pipeline" colSpan={6}>
                {pipeline.nom}
              </td>
            </tr>
            {pipeline.etapes.map((etape) => (
              <tr key={`${etape.pipeline}-${etape.etape}-${etape.source ?? ""}`}>
                <td>
                  <span
                    style={{ display: "inline-flex", alignItems: "center", gap: 8 }}
                    title={etape.statut}
                  >
                    {iconeStatut(etape.statut)}
                    <span className="vg-tete">{etape.etape}</span>
                  </span>
                </td>
                <td>{etape.source ?? "—"}</td>
                <td className="vg-chiffre">{nombre(etape.lignes_lues)}</td>
                <td className="vg-chiffre">{nombre(etape.lignes_rejetees)}</td>
                <td className="vg-chiffre">{duree(etape.duree_secondes)}</td>
                <td className="vg-chiffre">{jourCourt(etape.demarre_a)}</td>
              </tr>
            ))}
          </tbody>
        ))}
      </table>
      </div>

      <p className="vg-note">
        Ce tableau n&apos;est pas une exécution : c&apos;est, pour chaque étape, la dernière fois
        qu&apos;elle a tourné.{" "}
        {jours.length > 1
          ? `Les dates s'étalent du ${jours[0]} au ${jours.at(-1)}, les durées ne s'additionnent donc pas.`
          : "Toutes datent du même jour."}{" "}
        « inchangé » signifie qu&apos;une extraction a trouvé la source identique à la précédente
        et n&apos;a rien rechargé.
      </p>
    </section>
  );
}
