"""Acquisition des données depuis les systèmes sources.

Ce paquet lit la source SQL — la base « boutique » — et dépose ce qu'il lit
dans la zone brute, sans rien transformer.

La lecture de la source est isolée dans `boutique.py` : le reste du module
ignore d'où viennent les données. Le jour où une source change de nature, seul
ce fichier est réécrit.
"""
