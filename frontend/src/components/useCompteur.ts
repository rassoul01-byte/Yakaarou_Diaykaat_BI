/** Un chiffre qui monte de zéro à sa valeur.
 *
 * Pourquoi ça existe. Sur un tableau de bord, le chiffre d'affaires est la
 * chose que l'œil cherche en premier ; affiché d'un coup, il se confond avec
 * le reste de la page. Qu'il monte pendant une seconde le désigne sans qu'on
 * ait à l'entourer de rouge.
 *
 * Trois précautions, et chacune compte :
 *
 * - `prefers-reduced-motion` renvoie la valeur finale **tout de suite**. Le
 *   réglage système « réduire les animations » existe pour les personnes que
 *   le mouvement rend malades : un compteur est précisément ce qu'il faut
 *   éteindre. La valeur est alors dérivée au rendu, sans état ni effet.
 * - la fin est la valeur **exacte**, posée hors interpolation. Un arrondi sur
 *   la dernière image afficherait 13 493 151,55 au lieu de 13 493 151,56 — un
 *   centime d'écart avec le dictionnaire des indicateurs, et le chiffre
 *   affiché cesserait d'être le chiffre publié.
 * - l'animation part de la valeur affichée, pas de zéro : rien n'est remis à
 *   zéro dans l'effet, donc aucun rendu en cascade, et une actualisation fait
 *   glisser le chiffre de l'ancien au nouveau au lieu de le faire retomber.
 *   C'est aussi ce qui le rend indifférent au double rendu de `StrictMode`.
 */

import { useEffect, useRef, useState } from "react";

const DUREE_PAR_DEFAUT = 1100;

function mouvementReduit(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** Ralentit à l'arrivée : le chiffre démarre vite et se pose. */
function freiner(avancement: number): number {
  return 1 - (1 - avancement) ** 3;
}

export function useCompteur(
  cible: number | null | undefined,
  duree = DUREE_PAR_DEFAUT,
): number | null | undefined {
  const [anime, setAnime] = useState(0);
  const affiche = useRef(0);
  const image = useRef<number | null>(null);

  // Ce que le rendu renvoie. Rien n'est écrit dans l'état pour ces cas : pas
  // de valeur, ou pas d'animation voulue, et le chiffre est celui de l'API.
  const immobile = cible === null || cible === undefined || duree <= 0 || mouvementReduit();

  useEffect(() => {
    if (immobile || cible === null || cible === undefined) return;

    const depart = affiche.current;
    const ecart = cible - depart;
    if (ecart === 0) return;

    const debut = performance.now();

    const avancer = (maintenant: number) => {
      const avancement = Math.min((maintenant - debut) / duree, 1);
      if (avancement >= 1) {
        // La valeur exacte, pas la dernière interpolation.
        affiche.current = cible;
        setAnime(cible);
        return;
      }
      const valeur = depart + ecart * freiner(avancement);
      affiche.current = valeur;
      setAnime(valeur);
      image.current = requestAnimationFrame(avancer);
    };

    image.current = requestAnimationFrame(avancer);

    return () => {
      if (image.current !== null) cancelAnimationFrame(image.current);
    };
  }, [cible, duree, immobile]);

  return immobile ? cible : anime;
}
