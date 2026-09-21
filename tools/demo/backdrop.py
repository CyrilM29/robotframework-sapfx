"""Fond opaque plein écran, posé DERRIÈRE les fenêtres filmées.

La démo capture un rectangle fixe de l'écran plutôt qu'une fenêtre nommée, pour
n'avoir qu'une seule prise à recoller. Le revers est qu'un rectangle montre ce
qui s'y trouve : dès qu'une fenêtre filmée ne le couvre pas entièrement (bordure
d'une application, fenêtre qui se redessine, dialogue plus petit), c'est le
BUREAU de la machine qui entre dans l'image.

Ce fond ferme le trou : la région ne peut plus montrer que l'application filmée
ou une surface unie. Il est volontairement sans titre ni contenu, pour qu'un
liseré capté sur un bord reste neutre.

Lancé comme processus séparé (une boucle Tk ne peut pas cohabiter avec la suite
Robot), et arrêté par le teardown de la démo.

    pythonw tools/demo/backdrop.py [couleur]
"""

import sys
import tkinter

DEFAULT_COLOR = "#0a3d62"


def main(argv):
    color = argv[1] if len(argv) > 1 else DEFAULT_COLOR
    root = tkinter.Tk()
    root.configure(background=color)
    # Sans décoration ET plein écran : une barre de titre entrerait dans la
    # région filmée le temps qu'une application se pose par-dessus.
    root.overrideredirect(True)
    root.geometry(
        "%dx%d+0+0" % (root.winfo_screenwidth(), root.winfo_screenheight())
    )
    # Jamais `-topmost` : le fond doit rester DERRIÈRE les fenêtres filmées.
    # Il est simplement affiché avant elles, donc elles passent devant.
    root.lower()
    # Une sortie de secours au clavier : un fond plein écran sans décoration ne
    # se ferme pas à la souris si la démo s'interrompt avant son teardown.
    root.bind("<Escape>", lambda event: root.destroy())
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
