"""Blague Toto : une blague courte, dite en deux temps (mise en place, puis chute).

Les blagues sont écrites ici (pas de génération par le LLM) pour qu'elles restent gentilles, courtes
et sans surprise. BeeDoo n'en répète pas une avant d'avoir fait le tour de la liste. Pour en ajouter :
une ligne dans BLAGUES.
"""

import random

from beedoo.miniapps.base import Contexte, MiniApp, Reponse

# (mise en place, chute)
BLAGUES: tuple[tuple[str, str], ...] = (
    ("Toto rentre de l'école et dit à sa maman : « Maman, j'ai eu vingt ! » Sa maman est très fière : « Bravo ! En quoi ? »",
     "« Dix en maths et dix en français ! »"),
    ("La maîtresse demande à Toto : « Si j'ai cinq pommes dans une main et six pommes dans l'autre, qu'est-ce que j'ai ? »",
     "Toto répond : « De très grandes mains, maîtresse ! »"),
    ("Toto arrive en retard à l'école. La maîtresse lui demande pourquoi.",
     "« Il y avait un panneau « École, ralentir ». Alors j'ai ralenti ! »"),
    ("Pourquoi Toto emmène-t-il une échelle à l'école ?",
     "Pour aller à l'école supérieure !"),
    ("La maîtresse dit : « Toto, si je dis « je suis belle », c'est quel temps ? »",
     "Toto répond : « C'est du passé, maîtresse ! »"),
    ("La maîtresse demande à Toto qui a découvert l'Amérique.",
     "Toto répond : « Ce n'est pas moi, maîtresse ! »"),
    ("Pourquoi Toto met-il du sucre sur son oreiller ?",
     "Pour avoir des rêves bien doux !"),
    ("Toto va chez le docteur : « Docteur, j'ai mal partout ! Quand j'appuie sur mon bras, ça fait mal. Sur ma jambe, ça fait mal. Sur ma tête, ça fait mal ! »",
     "Le docteur regarde et dit : « C'est normal, vous avez le doigt cassé ! »"),
    ("Toto dit au serveur : « Il y a une mouche dans ma soupe ! »",
     "Le serveur répond tout bas : « Chut ! Ne le dites pas trop fort, tout le monde va en vouloir ! »"),
    ("La maîtresse demande à Toto : « Quel est le futur du verbe « je baille » ? »",
     "Toto répond : « Je dors ! »"),
    ("La maîtresse demande à Toto : « Si tu as dix bonbons et que tu en manges neuf, qu'est-ce qu'il te reste ? »",
     "Toto répond : « Un gros mal de ventre, maîtresse ! »"),
    ("Toto dit à son papa : « Papa, à l'école, je suis le premier de la classe ! » Son papa est surpris : « Vraiment ? »",
     "« Oui ! Quand on range les chaises, c'est moi qui sors le premier ! »"),
)


class Toto(MiniApp):
    nom = "toto"
    titre = "Blague Toto"
    mots_surs = ("blague", "blagues", "toto", "histoire drole", "fais moi rire", "fait moi rire",
                 "raconte moi quelque chose de drole", "une devinette drole")
    mots_vagues = ("rire", "drole", "amuse moi", "m amuser")
    proposition = "Tu veux que je te raconte une blague de Toto ?"

    def __init__(self, rng: random.Random | None = None) -> None:
        self._rng = rng or random.Random()
        self._deja_dites: set[int] = set()
        self._derniere: int | None = None

    def repondre(self, texte: str, contexte: Contexte) -> Reponse:
        restantes = [i for i in range(len(BLAGUES)) if i not in self._deja_dites]
        if not restantes:  # on a fait le tour : on recommence (sans reprendre la dernière tout de suite)
            self._deja_dites.clear()
            restantes = [i for i in range(len(BLAGUES)) if i != self._derniere]
        choix = self._rng.choice(restantes)
        self._deja_dites.add(choix)
        self._derniere = choix
        mise_en_place, chute = BLAGUES[choix]
        return Reponse(("Ah, une blague de Toto ! Écoute bien. " + mise_en_place, chute), geste="antennes_content")
