from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from transformation.normalisation import normaliser_date, normaliser_libelle, normaliser_montant


@pytest.mark.parametrize(
    "entree, attendu",
    [
        ("2017-10-02 10:56:33", "2017-10-02T10:56:33Z"),
        ("2017-10-02T10:56:33", "2017-10-02T10:56:33Z"),
        ("2017-10-02T10:56:33Z", "2017-10-02T10:56:33Z"),
        ("02/10/2017 10:56:33", "2017-10-02T10:56:33Z"),
        ("2017-10-02", "2017-10-02T00:00:00Z"),
    ],
)
def test_les_formats_de_date_convergent_vers_iso(entree, attendu):
    assert normaliser_date(entree) == attendu


def test_un_fuseau_est_ramene_a_utc():
    moment = datetime(2017, 10, 2, 12, 0, tzinfo=timezone(timedelta(hours=2)))
    assert normaliser_date(moment) == "2017-10-02T10:00:00Z"
    assert normaliser_date(datetime(2017, 10, 2, 12, 0, tzinfo=UTC)) == "2017-10-02T12:00:00Z"


def test_une_date_illisible_ou_absente_donne_none():
    assert normaliser_date("pas une date") is None
    assert normaliser_date("") is None
    assert normaliser_date(None) is None


def test_normaliser_une_date_deja_normalisee_ne_change_rien():
    assert normaliser_date(normaliser_date("02/10/2017 10:56:33")) == "2017-10-02T10:56:33Z"


@pytest.mark.parametrize(
    "entree, attendu",
    [
        ("12,5", "12.50"),
        ("12.5", "12.50"),
        (12, "12.00"),
        (12.345, "12.35"),
        ("1 234,56", "1234.56"),
        ("1.234,56", "1234.56"),
        ("1,234.56", "1234.56"),
        (Decimal("7.999"), "8.00"),
    ],
)
def test_les_montants_sont_a_deux_decimales(entree, attendu):
    assert normaliser_montant(entree) == Decimal(attendu)


def test_le_montant_est_un_decimal_jamais_un_flottant():
    assert isinstance(normaliser_montant(0.1), Decimal)


def test_un_montant_illisible_ou_absent_donne_none():
    assert normaliser_montant("abc") is None
    assert normaliser_montant("") is None
    assert normaliser_montant(None) is None
    assert normaliser_montant("NaN") is None


def test_libelle_minuscules_sans_accents():
    assert normaliser_libelle("  Beauté   Santé ") == "beaute sante"
    assert normaliser_libelle("ÉLECTROMÉNAGER") == "electromenager"
    assert normaliser_libelle(None) is None


def test_normaliser_un_libelle_deja_normalise_ne_change_rien():
    une_fois = normaliser_libelle("Bébé & Enfant")
    assert normaliser_libelle(une_fois) == une_fois
