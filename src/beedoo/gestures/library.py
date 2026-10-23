"""Bibliothèque de gestes de BeeDoo.

Un geste est une suite d'étapes (`Step`) : des données, pas du code qui parle au robot. On peut donc
les tester sans robot, et le lecteur (`player.py`) est le seul endroit qui appelle `goto_target()`.
Tout est doux et lent : jamais moins de 0,5 s par étape, angles bornés. Valeurs reprises de l'essai S5.
"""

from dataclasses import dataclass

DUREE_MIN = 0.5  # secondes, règle du projet pour goto_target()

# Bornes de sécurité, en degrés
TANGAGE_MAX = 25.0
LACET_MAX = 45.0
ROULIS_MAX = 20.0
ANTENNE_MAX = 70.0


@dataclass(frozen=True)
class Step:
    """Un mouvement en `duree` secondes, suivi d'une `pause`. Angles en degrés.

    Si aucun angle de tête n'est donné, la tête ne bouge pas ; si l'un l'est, les autres valent 0.
    """

    duree: float = DUREE_MIN
    tangage: float | None = None  # pitch : positif = tête qui descend vers l'avant
    lacet: float | None = None  # yaw : tourner la tête
    roulis: float | None = None  # roll : pencher la tête
    antennes: tuple[float, float] | None = None
    pause: float = 0.0

    def __post_init__(self) -> None:
        if self.duree < DUREE_MIN:
            raise ValueError(f"durée {self.duree} s trop courte (minimum {DUREE_MIN} s)")
        for nom, valeur, borne in (("tangage", self.tangage, TANGAGE_MAX), ("lacet", self.lacet, LACET_MAX),
                                   ("roulis", self.roulis, ROULIS_MAX)):
            if valeur is not None and abs(valeur) > borne:
                raise ValueError(f"{nom} {valeur}° hors limite (±{borne}°)")
        if self.antennes is not None and any(abs(a) > ANTENNE_MAX for a in self.antennes):
            raise ValueError(f"antennes {self.antennes} hors limite (±{ANTENNE_MAX}°)")
        if not 0 <= self.pause <= 5:
            raise ValueError(f"pause {self.pause} s hors limite (0 à 5 s)")

    @property
    def bouge_la_tete(self) -> bool:
        return any(v is not None for v in (self.tangage, self.lacet, self.roulis))


def oui() -> tuple[Step, ...]:
    return (Step(tangage=12), Step(tangage=-8), Step(tangage=12), Step(tangage=-8), Step(tangage=0))


def non() -> tuple[Step, ...]:
    return (Step(lacet=20), Step(lacet=-20), Step(lacet=20), Step(lacet=-20), Step(lacet=0))


def antennes_content() -> tuple[Step, ...]:
    return (Step(antennes=(40, 40)), Step(antennes=(-10, -10))) * 3


def antennes_surprise() -> tuple[Step, ...]:
    return (Step(tangage=-8), Step(antennes=(60, -60), pause=1.0))


def regarder(lacet: float = 25.0, tangage: float = 0.0) -> tuple[Step, ...]:
    """Tourne la tête vers une direction (pour regarder la personne). Les angles sont ramenés aux bornes."""
    lacet = max(-LACET_MAX, min(LACET_MAX, lacet))
    tangage = max(-TANGAGE_MAX, min(TANGAGE_MAX, tangage))
    return (Step(duree=0.8, lacet=lacet, tangage=tangage, pause=1.0),)


def neutre() -> tuple[Step, ...]:
    return (Step(duree=0.8, tangage=0, lacet=0, roulis=0, antennes=(0, 0)),)


GESTES = {
    "oui": oui,
    "non": non,
    "antennes_content": antennes_content,
    "antennes_surprise": antennes_surprise,
    "regarder": regarder,
    "neutre": neutre,
}
