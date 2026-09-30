"""Normalisation des formats : dates, montants, libellés servant de clé.

Convention de la stratégie de qualité (catégorie « Formats ») : dates au format ISO
dans un fuseau unique, montants à deux décimales, libellés en minuscules sans accents
lorsqu'ils servent de clé de rapprochement.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

# Formats de date rencontrés ou plausibles, du plus précis au moins précis.
_FORMATS_DATE = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%Y-%m-%d",
    "%d/%m/%Y",
)
_DEUX_DECIMALES = Decimal("0.01")
_ESPACES = re.compile(r"\s+")


def normaliser_date(valeur: str | datetime | None) -> str | None:
    """Ramène une date au format ISO 8601, en UTC : `2017-10-02T10:56:33Z`.

    Une valeur sans fuseau est considérée comme déjà exprimée dans le fuseau de
    référence du projet (UTC) : la source ne dit rien de plus. Une valeur illisible
    renvoie `None` — c'est au contrôle de qualité de la rejeter, pas à la
    transformation de deviner.
    """
    if valeur is None:
        return None
    if isinstance(valeur, datetime):
        moment = valeur
    else:
        moment = _lire_date(str(valeur).strip())
        if moment is None:
            return None
    moment = moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment.astimezone(UTC)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _lire_date(texte: str) -> datetime | None:
    if not texte:
        return None
    try:
        return datetime.fromisoformat(texte.replace("Z", "+00:00"))
    except ValueError:
        pass
    for format_ in _FORMATS_DATE:
        try:
            return datetime.strptime(texte, format_)
        except ValueError:
            continue
    return None


def normaliser_montant(valeur: str | float | Decimal | None) -> Decimal | None:
    """Ramène un montant à deux décimales : `12,5` devient `Decimal('12.50')`.

    Accepte la virgule ou le point décimal, et les séparateurs de milliers
    (`1 234,56`, `1.234,56`, `1,234.56`). Quand les deux signes sont présents, le
    dernier est le séparateur décimal. L'arrondi est celui de la comptabilité
    (moitié vers le haut), et le résultat est un `Decimal`, jamais un flottant.
    """
    if valeur is None:
        return None
    if isinstance(valeur, Decimal):
        nombre = valeur
    else:
        texte = _ESPACES.sub("", str(valeur))
        if not texte:
            return None
        texte = _unifier_separateurs(texte)
        try:
            nombre = Decimal(texte)
        except InvalidOperation:
            return None
    if not nombre.is_finite():
        return None
    return nombre.quantize(_DEUX_DECIMALES, rounding=ROUND_HALF_UP)


def _unifier_separateurs(texte: str) -> str:
    derniere_virgule, dernier_point = texte.rfind(","), texte.rfind(".")
    if derniere_virgule == -1 and dernier_point == -1:
        return texte
    decimal = "," if derniere_virgule > dernier_point else "."
    mille = "." if decimal == "," else ","
    return texte.replace(mille, "").replace(decimal, ".")


def normaliser_libelle(texte: str | None) -> str | None:
    """Minuscules, sans accents, espaces uniques : `Beauté  Santé` devient `beaute sante`.

    À n'employer que pour un libellé qui sert de clé de rapprochement (Sprint 3),
    jamais pour un texte affiché : les accents y sont une information.
    """
    if texte is None:
        return None
    decompose = unicodedata.normalize("NFKD", texte)
    sans_accents = "".join(c for c in decompose if not unicodedata.combining(c))
    return _ESPACES.sub(" ", sans_accents.lower()).strip()
