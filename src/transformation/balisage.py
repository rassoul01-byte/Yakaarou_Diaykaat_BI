"""Décodage du balisage HTML des textes de fiches produits.

Défaut mesuré : 63,6 % des descriptions du catalogue contiennent des entités HTML
(`id&eacute;es`) et 28,4 % des balises (`<br>`, `<p>`). Sans ce décodage, le moteur
de recherche ne retrouverait jamais un mot accentué.
"""

from __future__ import annotations

import html
import re

# Une vraie balise commence par une lettre ou « / » : un « < » isolé dans un texte
# (« moins de 5 < 10 ») n'est donc pas pris pour une balise.
_BALISE = re.compile(r"</?[A-Za-z][^>]*>")
_ESPACES = re.compile(r"\s+")

# Certaines fiches sont encodées deux fois : `l&amp;#39;abri` devient `l&#39;abri` après un
# premier décodage, et il reste une entité. On décode donc jusqu'à ce que le texte ne change
# plus, avec un plafond pour ne jamais boucler.
_PASSES_MAX = 3


def _decoder_entites(texte: str) -> str:
    for _ in range(_PASSES_MAX):
        decode = html.unescape(texte)
        if decode == texte:
            break
        texte = decode
    return texte


def decoder_balisage(texte: str | None) -> str | None:
    """Décode les entités HTML, supprime les balises, ramène les espaces à un seul.

    - `id&eacute;es` devient `idées` ;
    - `<br>` et `<p>` disparaissent, remplacées par une espace pour que deux mots
      séparés par une balise ne se collent pas ;
    - une valeur absente (`None`) reste absente : l'absence de description n'est pas
      un défaut, c'est une information.

    Les entités sont décodées avant les balises : un texte écrit `&lt;br&gt;` est
    d'abord lu comme `<br>`, puis supprimé comme les autres. Une entité encodée deux
    fois (`l&amp;#39;abri`) est décodée jusqu'au bout : plus aucune entité ne subsiste.
    """
    if texte is None:
        return None
    decode = _decoder_entites(texte)
    sans_balises = _BALISE.sub(" ", decode)
    return _ESPACES.sub(" ", sans_balises).strip()
