"""Tests de la vérification de la foire aux questions."""

import json

import pytest

from documentaire.verifier import main, verifier

PREFIXES = {
    "livraison": "liv",
    "retours": "ret",
    "paiement": "pai",
    "commande": "cmd",
    "compte": "cpt",
}


def entree(theme: str, numero: int) -> dict:
    return {
        "id": f"{PREFIXES[theme]}-{numero:02d}",
        "theme": theme,
        "question": f"Question {theme} {numero} ?",
        "reponse": f"Réponse {theme} {numero}.",
        "source": "politique:essai",
        "maj": "2026-10-04",
    }


def jeu(par_theme: int = 6) -> list[dict]:
    return [entree(theme, n) for theme in PREFIXES for n in range(1, par_theme + 1)]


def numerotees(entrees: list[dict]) -> list[tuple[int, object]]:
    return list(enumerate(entrees, start=1))


def ecrire(chemin, entrees: list[dict]) -> None:
    chemin.write_text("\n".join(json.dumps(e) for e in entrees) + "\n", encoding="utf-8")


def test_jeu_valide_sans_erreur():
    assert verifier(numerotees(jeu())) == []


@pytest.mark.parametrize("champ", ["id", "theme", "question", "reponse", "source", "maj"])
def test_champ_vide_signale(champ):
    entrees = jeu()
    entrees[0][champ] = ""
    erreurs = verifier(numerotees(entrees))
    assert any(champ in message for message in erreurs)


def test_champ_absent_signale():
    entrees = jeu()
    del entrees[0]["source"]
    assert any("source" in message for message in verifier(numerotees(entrees)))


def test_id_en_double_signale():
    entrees = jeu()
    entrees[1]["id"] = entrees[0]["id"]
    assert any("en double" in message for message in verifier(numerotees(entrees)))


def test_theme_inconnu_signale():
    entrees = jeu()
    entrees[0]["theme"] = "autre"
    assert any("thème inconnu" in message for message in verifier(numerotees(entrees)))


def test_prefixe_incoherent_signale():
    entrees = jeu()
    entrees[0]["id"] = "cmd-99"
    assert any("préfixe" in message for message in verifier(numerotees(entrees)))


def test_source_invalide_signale():
    entrees = jeu()
    entrees[0]["source"] = "web:quelque-chose"
    assert any("source" in message for message in verifier(numerotees(entrees)))


def test_source_sans_contenu_signale():
    entrees = jeu()
    entrees[0]["source"] = "donnee:"
    assert any("source" in message for message in verifier(numerotees(entrees)))


def test_date_invalide_signale():
    entrees = jeu()
    entrees[0]["maj"] = "04/10/2026"
    assert any("date" in message for message in verifier(numerotees(entrees)))


def test_question_en_double_signalee():
    entrees = jeu()
    entrees[1]["question"] = entrees[0]["question"]
    assert any("apparaît" in message for message in verifier(numerotees(entrees)))


def test_trop_peu_de_questions():
    erreurs = verifier(numerotees(jeu(par_theme=2)))
    assert any("total de 10" in message for message in erreurs)


def test_trop_de_questions():
    erreurs = verifier(numerotees(jeu(par_theme=11)))
    assert any("total de 55" in message for message in erreurs)


def test_theme_sous_effectif():
    entrees = [entree(t, n) for t in PREFIXES if t != "compte" for n in range(1, 10)]
    entrees += [entree("compte", n) for n in range(1, 5)]
    erreurs = verifier(numerotees(entrees))
    assert any("« compte » : 4" in message for message in erreurs)


def test_main_fichier_conforme(tmp_path, capsys):
    chemin = tmp_path / "faq.jsonl"
    ecrire(chemin, jeu(par_theme=8))
    assert main(["--fichier", str(chemin)]) == 0
    sortie = capsys.readouterr().out
    assert "Fichier conforme." in sortie
    assert "40" in sortie


def test_main_fichier_absent(tmp_path, capsys):
    assert main(["--fichier", str(tmp_path / "absent.jsonl")]) == 1
    assert "introuvable" in capsys.readouterr().out


def test_main_json_invalide(tmp_path, capsys):
    chemin = tmp_path / "faq.jsonl"
    ecrire(chemin, jeu(par_theme=8))
    with chemin.open("a", encoding="utf-8") as fichier:
        fichier.write("{pas du json\n")
    assert main(["--fichier", str(chemin)]) == 1
    assert "JSON invalide" in capsys.readouterr().out


def test_main_code_de_sortie_1_sur_ecart(tmp_path):
    chemin = tmp_path / "faq.jsonl"
    entrees = jeu(par_theme=8)
    entrees[0]["theme"] = "autre"
    ecrire(chemin, entrees)
    assert main(["--fichier", str(chemin)]) == 1
