/** Types miroir des schémas Pydantic (src/api/schemas.py).

Toute modification d'un schéma côté Python doit être répercutée ici
dans la même PR.
*/

export type Passage = {
  id: string;
  theme: string;
  question: string;
  source: string;
  score: number;
};

// --------------------------------------------------------------- assistant

export type AssistantIn = {
  question: string;
  k?: number;
};

export type AssistantOut = {
  reponse: string;
  refus: boolean;
  motif: string | null;
  passages: Passage[];
  suggestions: Passage[];
  duree_ms: number;
};

// --------------------------------------------------------------- recherche

export type RechercheIn = {
  q: string;
  k?: number;
};

export type RechercheResultat = {
  id: string;
  theme: string;
  question: string;
  reponse: string;
  source: string;
  score: number;
};

export type RechercheOut = {
  question_posee: string;
  resultats: RechercheResultat[];
};
