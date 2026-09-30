from transformation.langue import LANGUE_INCONNUE, detecter_langue


def test_une_designation_francaise_est_detectee():
    assert (
        detecter_langue("Ensemble de cuisine en acier inoxydable, très pratique et robuste") == "fr"
    )


def test_une_designation_anglaise_est_detectee():
    assert detecter_langue("Stainless steel kitchen set, very practical and durable") == "en"


def test_une_designation_allemande_est_detectee():
    assert (
        detecter_langue("Küchenset aus Edelstahl, sehr praktisch und langlebig für die Familie")
        == "de"
    )


def test_un_texte_vide_ou_sans_lettres_donne_inconnue():
    assert detecter_langue(None) == LANGUE_INCONNUE
    assert detecter_langue("   ") == LANGUE_INCONNUE
    assert detecter_langue("12345 6789") == LANGUE_INCONNUE


def test_la_detection_est_reproductible():
    texte = "Lot de 3 pièces"
    resultats = {detecter_langue(texte) for _ in range(30)}
    assert len(resultats) == 1
