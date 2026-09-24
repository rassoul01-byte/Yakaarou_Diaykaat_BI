"""Chargement des données réelles qui rendent le flux crédible.

- Catalogue Rakuten : identifiants de produits et désignations.
- Clients Olist : `customer_unique_id` (identifiant de PERSONNE).
  La colonne `customer_id` d'Olist est un identifiant de COMMANDE : elle n'est jamais lue ici.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

_HEX32 = re.compile(r"^[0-9a-f]{32}$")


def charger_produits(
    chemin: str | Path,
    colonne_id: str = "productid",
    colonne_designation: str = "designation",
) -> list[tuple[str, str]]:
    """Renvoie [(id_produit, designation)], sans doublon d'identifiant.

    L'identifiant reste du TEXTE (le contrat interdit un nombre) et ne contient que des chiffres.
    """
    vus: dict[str, str] = {}
    with open(chemin, encoding="utf-8", newline="") as f:
        for ligne in csv.DictReader(f):
            pid = (ligne.get(colonne_id) or "").strip()
            designation = (ligne.get(colonne_designation) or "").strip()
            if pid.isdigit() and designation and pid not in vus:
                vus[pid] = designation
    if not vus:
        raise ValueError(f"aucun produit exploitable dans {chemin}")
    return list(vus.items())


def charger_clients(chemin: str | Path, colonne: str = "customer_unique_id") -> list[str]:
    """Renvoie les customer_unique_id distincts (32 caractères hexadécimaux)."""
    vus: dict[str, None] = {}
    with open(chemin, encoding="utf-8", newline="") as f:
        for ligne in csv.DictReader(f):
            cid = (ligne.get(colonne) or "").strip().lower()
            if _HEX32.match(cid):
                vus.setdefault(cid, None)
    if not vus:
        raise ValueError(f"aucun customer_unique_id exploitable dans {chemin}")
    return list(vus)
