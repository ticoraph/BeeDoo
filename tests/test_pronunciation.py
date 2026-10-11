from beedoo.voice.pronunciation import normalize_heard_name, to_spoken


def test_name_is_written_phonetically_for_speech():
    assert to_spoken("Je suis BeeDoo, un petit robot.") == "Je suis Bidou, un petit robot."
    assert to_spoken("Salut beedoo !") == "Salut Bidou !"
    assert to_spoken("Bee-Doo") == "Bidou"


def test_other_words_untouched():
    assert to_spoken("Il fait beau, et toi ?") == "Il fait beau, et toi ?"


def test_heard_variants_become_beedoo():
    assert normalize_heard_name("Bonjour Didou, tu vas bien ?") == "Bonjour BeeDoo, tu vas bien ?"
    assert normalize_heard_name("dis bidou") == "dis BeeDoo"
    assert normalize_heard_name("Il y a du doux") == "Il y a du doux"
