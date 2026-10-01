import pytest

from transformation.balisage import decoder_balisage


def test_une_entite_html_est_decodee():
    assert decoder_balisage("id&eacute;es") == "idées"


def test_les_balises_disparaissent_sans_coller_les_mots():
    assert decoder_balisage("Ligne un<br>ligne deux<p>fin</p>") == "Ligne un ligne deux fin"
    assert decoder_balisage("a<br/>b") == "a b"


def test_une_balise_ecrite_en_entite_est_aussi_supprimee():
    assert decoder_balisage("avant &lt;br&gt; apres") == "avant apres"


def test_un_chevron_isole_n_est_pas_une_balise():
    assert decoder_balisage("moins de 5 < 10 pieces") == "moins de 5 < 10 pieces"


def test_l_espace_insecable_devient_une_espace():
    assert decoder_balisage("5&nbsp;cm") == "5 cm"


@pytest.mark.parametrize(
    ("brut", "attendu"),
    [
        ("l&amp;#39;abri", "l'abri"),
        ("qu&amp;apos;une", "qu'une"),
        ("De Rethondes A&amp;#X300; Stresa", "De Rethondes A\u0300 Stresa"),
        ("AT&amp;T", "AT&T"),
    ],
)
def test_une_entite_encodee_deux_fois_est_decodee_jusqu_au_bout(brut, attendu):
    assert decoder_balisage(brut) == attendu


def test_aucune_entite_ne_subsiste_apres_le_decodage():
    import re

    brut = "l&amp;#39;abri et caf&eacute; &amp;amp; th&eacute; &amp;#233;"
    assert not re.search(r"&[a-zA-Z#0-9]+;", decoder_balisage(brut))


def test_l_absence_de_description_reste_une_absence():
    assert decoder_balisage(None) is None
    assert decoder_balisage("") == ""


@pytest.mark.parametrize(
    "texte",
    [
        "id&eacute;es <b>utiles</b>",
        "Caf&eacute; &amp; th&eacute;",
        "d&#233;j&agrave; vu",
        "l&amp;#39;abri",
    ],
)
def test_relancer_le_decodage_ne_change_rien(texte):
    une_fois = decoder_balisage(texte)
    assert decoder_balisage(une_fois) == une_fois
