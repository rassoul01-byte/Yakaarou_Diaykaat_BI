"""État de l'index de recherche.

Usage :
    docker compose exec app python -m recherche.etat

Code de sortie : 0 si l'index contient autant de documents que la zone
intermédiaire de fiches, 1 sinon.
"""

from __future__ import annotations

import sys

from elasticsearch.exceptions import ApiError, TransportError

from .client import adresse, connexion
from .indexation import compter_en_base, compter_indexes
from .schema import INDEX


def main(argv: list[str] | None = None) -> int:
    try:
        client = connexion()
        indexes = compter_indexes(client)
        en_base = compter_en_base()
        taille = 0
        if client.indices.exists(index=INDEX):
            stats = client.indices.stats(index=INDEX)
            taille = stats["indices"][INDEX]["total"]["store"]["size_in_bytes"]
    except (ApiError, TransportError) as erreur:
        print(
            f"ERREUR : Elasticsearch n'a pas répondu ({erreur.__class__.__name__})", file=sys.stderr
        )
        print(f"Vérifier que le service tourne : {adresse()}", file=sys.stderr)
        return 1

    print(f"\nIndex {INDEX} — {adresse()}\n")
    print(f"  documents indexés            : {indexes}")
    print(f"  fiches en zone intermédiaire : {en_base}")
    print(f"  taille de l'index            : {taille / 1024 / 1024:.1f} Mo")

    if indexes != en_base:
        print("\nÉcart : relancer python -m recherche.indexer", file=sys.stderr)
        return 1

    print("\nIndex à jour.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
