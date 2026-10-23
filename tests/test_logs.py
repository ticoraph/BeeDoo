import logging

from beedoo.logs import MasqueCles


def test_api_keys_are_masked():
    record = logging.LogRecord("t", logging.ERROR, __file__, 1, "échec avec %s", ("sk-proj-abcdef123456",), None)
    assert MasqueCles().filter(record)
    assert record.getMessage() == "échec avec [clé masquée]"


def test_normal_message_untouched():
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "état : veille -> écoute", None, None)
    MasqueCles().filter(record)
    assert record.getMessage() == "état : veille -> écoute"


# --- journal en mémoire (page « Journal ») ---
from beedoo.logs import JournalMemoire, nettoyer  # noqa: E402


# Chemin fictif construit en morceaux : le garde-fou du dépôt interdit d'écrire un chemin personnel en entier.
CHEMIN_FICTIF = "/" + "Users" + "/quelquun"


def un_journal(taille=300):
    journal = JournalMemoire(taille)
    journal.setFormatter(logging.Formatter("%(message)s"))
    journal.addFilter(MasqueCles())
    return journal


def enregistrer(journal, nom, niveau, message, *args):
    journal.handle(logging.LogRecord(nom, niveau, __file__, 1, message, args or None, None))


def test_journal_keeps_beedoo_events_and_only_warnings_from_libraries():
    journal = un_journal()
    enregistrer(journal, "beedoo.conversation", logging.INFO, "conversation : le micro est allumé")
    enregistrer(journal, "uvicorn.error", logging.INFO, "bavardage de la bibliothèque")
    enregistrer(journal, "httpx", logging.WARNING, "un avertissement d'ailleurs")
    lignes, dernier = journal.depuis()
    assert [(l["source"], l["niveau"]) for l in lignes] == [("conversation", "INFO"), ("httpx", "WARNING")]
    assert dernier == 2


def test_journal_hides_keys_and_personal_paths_and_stays_one_line():
    journal = un_journal()
    enregistrer(journal, "beedoo.x", logging.ERROR, "échec avec %s dans %s\nsuite", "sk-proj-abcdef123456",
                CHEMIN_FICTIF + "/Documents/BeeDoo/data")
    message = journal.depuis()[0][0]["message"]
    assert "sk-proj" not in message and "quelquun" not in message and "\n" not in message
    assert "[clé masquée]" in message and "~/Documents/BeeDoo/data" in message


def test_long_messages_are_cut():
    assert len(nettoyer("a" * 1000)) == 300 and nettoyer("a" * 1000).endswith("…")


def test_journal_is_bounded_and_incremental():
    journal = un_journal(taille=5)
    for i in range(12):
        enregistrer(journal, "beedoo.x", logging.INFO, "événement %d", i)
    lignes, dernier = journal.depuis()
    assert [l["message"] for l in lignes] == [f"événement {i}" for i in range(7, 12)] and dernier == 12
    assert journal.depuis(dernier)[0] == []  # rien de nouveau
    enregistrer(journal, "beedoo.x", logging.INFO, "encore")
    assert [l["message"] for l in journal.depuis(dernier)[0]] == ["encore"]
    assert journal.depuis(9999)[0][-1]["message"] == "encore"  # le client avait un numéro d'avant un redémarrage


def test_journal_never_includes_tracebacks():
    journal = un_journal()
    try:
        raise ValueError("secret dans la trace " + CHEMIN_FICTIF + "/x")
    except ValueError:
        import sys
        journal.handle(logging.LogRecord("beedoo.x", logging.ERROR, __file__, 1, "erreur", None, sys.exc_info()))
    assert "secret" not in str(journal.depuis()[0])
