/** Types miroir des schémas Pydantic (src/api/schemas.py).

Toute modification d'un schéma côté Python doit être répercutée ici
dans la même PR.
*/

// --------------------------------------------------------------- assistant

export type Passage = {
  id: string;
  theme: string;
  question: string;
  source: string;
  score: number;
};

export type Suggestion = {
  id: string;
  question: string;
};

export type AssistantIn = {
  question: string;
  k?: number;
};

export type AssistantOut = {
  reponse: string;
  refus: boolean;
  motif: string | null;
  passages: Passage[];
  suggestions: Suggestion[];
  duree_ms: number;
};

// --------------------------------------------------------------- recherche produits

export type RechercheIn = {
  q: string;
  k?: number;
  categorie?: string;
  langue?: string;
};

export type Produit = {
  product_id: string;
  designation: string;
  categorie_code: string | null;
  score: number;
};

export type RechercheOut = {
  question_posee: string;
  produits: Produit[];
  total: number;
  temps_serveur_ms: number;
};

// --------------------------------------------------------------- indicateurs
//
// Chaque bloc peut être null ou vide : une base fraîchement montée n'a ni
// ventes, ni événements, ni exécutions. La page affiche l'absence, elle ne
// la traite pas comme une erreur.

export type Ventes = {
  chiffre_affaires: number;
  commandes: number;
  articles: number;
  panier_moyen: number;
  premier_jour: string | null;
  dernier_jour: string | null;
};

export type Categorie = {
  categorie: string | null;
  chiffre_affaires: number | null;
  articles: number | null;
  commandes: number | null;
};

export type Qualite = {
  sources: number;
  lignes_lues: number | null;
  lignes_rejetees: number | null;
  taux_rejet_pourcent: number | null;
};

export type MotifRejet = {
  regle: string;
  gravite: string | null;
  rejets: number;
};

/** Compteurs du dernier jour connu. Aucun montant : les événements n'en portent pas. */
export type Jour = {
  jour: string;
  sessions: number;
  pages_vues: number;
  recherches: number;
  ajouts_panier: number;
  achats: number;
  sessions_avec_achat: number | null;
  taux_conversion_pourcent: number | null;
};

export type Heure = {
  heure: number;
  achats: number;
};

export type Alerte = {
  jour: string;
  achats: number;
  achats_habituels: number | null;
  jours_compares: number;
  niveau_pourcent: number | null;
  seuil_pourcent: number;
  declenchee: boolean;
  message: string;
};

export type Segment = {
  clients: number;
  date_reference: string | null;
};

export type Etape = {
  pipeline: string;
  etape: string;
  source: string | null;
  duree_secondes: number | null;
  lignes_lues: number | null;
  lignes_rejetees: number | null;
  statut: string;
  demarre_a: string | null;
};

export type IndicateursIn = {
  top?: number;
  motifs?: number;
  heure?: number;
};

export type IndicateursOut = {
  ventes: Ventes | null;
  categories: Categorie[];
  qualite: Qualite | null;
  motifs_de_rejet: MotifRejet[];
  jour: Jour | null;
  achats_par_heure: Heure[];
  alerte: Alerte | null;
  segment: Segment | null;
  chaine: Etape[];
  trafic_simule: boolean;
};