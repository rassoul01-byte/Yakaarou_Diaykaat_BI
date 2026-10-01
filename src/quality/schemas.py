"""
Schémas Pandera - Contrôle qualité DataFlow360.

F1.5 - Catalogue des règles de validation.
"""

import pandera.pandas as pa

# ===============================================================
# OLIST_AVIS_01
# Un review_id doit être unique et non nul.
# ===============================================================

schema_avis = pa.DataFrameSchema(
    {
        "review_id": pa.Column(
            str,
            nullable=False,
        ),
    },
    checks=[
        pa.Check(
            lambda df: ~df["review_id"].duplicated(keep=False),
            error="OLIST_AVIS_01",
        )
    ],
    strict=False,
    coerce=False,
)
