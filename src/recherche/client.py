"""Connexion à Elasticsearch."""

from __future__ import annotations

import os

from elasticsearch import Elasticsearch

ADRESSE_PAR_DEFAUT = "http://elasticsearch:9200"
DELAI = 30


def adresse() -> str:
    return os.getenv("ES_URL", ADRESSE_PAR_DEFAUT)


def connexion() -> Elasticsearch:
    return Elasticsearch(adresse(), request_timeout=DELAI)
