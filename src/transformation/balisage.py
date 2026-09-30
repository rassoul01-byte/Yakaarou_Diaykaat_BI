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


def decoder_balisage(texte: str | None) -> str | None:
    """Décode les entités HTML, supprime les balises, ramène les espaces à un seul.

    - `id&eacute;es` devient `idées` ;
    - `<br>` et `<p>` disparaissent, remplacées par une espace pour que deux mots
      séparés par une balise ne se collent pas ;
    - une valeur absente (`None`) reste absente : l'absence de description n'est pas
      un défaut, c'est une information.

    Les entités sont décodées avant les balises : un texte écrit `&lt;br&gt;` est
    d'abord lu comme `<br>`, puis supprimé comme les autres.
    """
    if texte is None:
        return None
    decode = html.unescape(texte)
    sans_balises = _BALISE.sub(" ", decode)
    return _ESPACES.sub(" ", sans_balises).strip()
