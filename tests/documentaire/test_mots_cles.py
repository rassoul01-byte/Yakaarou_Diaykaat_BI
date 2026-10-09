"""Mots-clés candidats : un mot qui distingue un passage est proposé, un mot partout non."""

from documentaire.mots_cles import proposer


def _faq() -> list[dict]:
    communs = "commande compte"
    return [
        {
            "id": "liv-01",
            "question": f"Comment suivre ma {communs} ?",
            "reponse": "Le suivi est visible.",
        },
        {
            "id": "ret-01",
            "question": f"Comment retourner ma {communs} ?",
            "reponse": "Le remboursement suit.",
        },
        {
            "id": "pai-01",
            "question": f"Quand paie-t-on ma {communs} ?",
            "reponse": "Le débit est immédiat.",
        },
        {
            "id": "cpt-01",
            "question": f"Comment créer ma {communs} ?",
            "reponse": "Un mail est envoyé.",
        },
        {
            "id": "cmd-01",
            "question": f"Peut-on annuler ma {communs} ?",
            "reponse": "Contactez le vendeur.",
        },
        {"id": "cmd-02", "question": f"Où voir ma {communs} ?", "reponse": "Dans la rubrique."},
        {"id": "cmd-03", "question": f"Que devient ma {communs} ?", "reponse": "Elle est traitée."},
    ]


def test_un_mot_distinctif_est_propose():
    propositions = proposer(_faq())
    assert "suivre" in {c["mot"] for c in propositions["liv-01"]}
    assert "annuler" in {c["mot"] for c in propositions["cmd-01"]}


def test_un_mot_present_partout_est_ecarte():
    propositions = proposer(_faq())
    for candidats in propositions.values():
        mots = {c["mot"] for c in candidats}
        assert "commande" not in mots
        assert "compte" not in mots
