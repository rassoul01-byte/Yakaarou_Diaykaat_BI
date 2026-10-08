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