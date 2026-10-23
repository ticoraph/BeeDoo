from beedoo.vision.greeter import INCONNU, SALUE, Event, Greeter


class Horloge:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


def faire(**kwargs):
    horloge = Horloge()
    return Greeter(clock=horloge, **kwargs), horloge


def test_greets_only_after_confirmation():
    greeter, _ = faire(confirmations=2)
    assert greeter.observe(True, "lea") is None
    assert greeter.observe(True, "lea") == Event(SALUE, "lea")


def test_single_wrong_frame_resets_confirmation():
    greeter, _ = faire(confirmations=2)
    greeter.observe(True, "lea")
    assert greeter.observe(True, "paul") is None
    assert greeter.observe(True, "lea") is None
    assert greeter.observe(True, "lea") == Event(SALUE, "lea")


def test_no_greeting_loop_while_person_stays():
    greeter, horloge = faire(confirmations=1, delai_salut=60, absence=10)
    assert greeter.observe(True, "lea") == Event(SALUE, "lea")
    for _ in range(500):  # reste devant le robot bien plus longtemps que le délai
        horloge.t += 2
        assert greeter.observe(True, "lea") is None


def test_regreet_after_leaving_and_delay():
    greeter, horloge = faire(confirmations=1, delai_salut=600, absence=20)
    greeter.observe(True, "lea")
    horloge.t += 60  # part une minute : trop tôt pour resaluer
    assert greeter.observe(False) is None
    horloge.t += 1
    assert greeter.observe(True, "lea") is None
    horloge.t += 30
    greeter.observe(False)
    horloge.t += 700  # revient bien plus tard
    assert greeter.observe(True, "lea") == Event(SALUE, "lea")


def test_long_delay_but_never_left_does_not_regreet():
    greeter, horloge = faire(confirmations=1, delai_salut=600, absence=20)
    greeter.observe(True, "lea")
    for _ in range(400):  # observée toutes les 2 s pendant 800 s, bien plus que le délai
        horloge.t += 2
        assert greeter.observe(True, "lea") is None


def test_unknown_signaled_once_per_presence():
    greeter, horloge = faire(confirmations=2, absence=20)
    assert greeter.observe(True) is None
    assert greeter.observe(True) == Event(INCONNU)
    for _ in range(10):
        horloge.t += 1
        assert greeter.observe(True) is None
    horloge.t += 30  # plus de visage assez longtemps
    greeter.observe(False)
    assert greeter.observe(True) is None
    assert greeter.observe(True) == Event(INCONNU)


def test_forget_makes_person_new_again():
    greeter, _ = faire(confirmations=1)
    greeter.observe(True, "lea")
    greeter.forget("lea")
    assert greeter.observe(True, "lea") == Event(SALUE, "lea")


def test_invalid_confirmations():
    import pytest

    with pytest.raises(ValueError):
        Greeter(confirmations=0)
