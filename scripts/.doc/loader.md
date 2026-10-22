# `loader.py` — lecture des données d'un site

## But
Relire ce que `build.py` a écrit sous `data/AAAA/MM/JJ.json` et `JJ.briefing.txt`, pour que `render.py` n'ait qu'à
afficher. Module importé (`from loader import load_all`), pas un script exécutable. Aucun accès réseau.

## Fonction
| Fonction | Entrée | Sortie |
|---|---|---|
| `load_all(data_dir)` | `Path` du dossier `data` d'un site | `(articles, briefing)` |

- `articles` : liste dédoublonnée **par lien et par titre normalisé** (minuscules, sans ponctuation), triée du plus récent au plus ancien. Chaque article reçoit une clé `first_seen` (le jour du fichier où il a été vu en premier ; les fichiers sont lus du plus ancien au plus récent).
- `briefing` : `("AAAA-MM-JJ", dict)` pour le **dernier** fichier `*.briefing.txt`, ou `None`.

## Cas particuliers
- Un fichier JSON illisible ou invalide est **ignoré en silence** (`continue`), sans message.
- Un briefing à l'ancien format (texte brut) ou sans `hook` ni `categories` est ignoré : `briefing` vaut alors `None`.
- Le nom du fichier doit être `AAAA/MM/JJ.json` : un nom qui ne se convertit pas en date lève une `ValueError`.

## Exemple
```python
from pathlib import Path
from loader import load_all

articles, briefing = load_all(Path("web_sites/loreal/data"))
len(articles)          # 62 pour loreal à la date de rédaction
briefing               # None, ou ("2026-10-21", {"hook": "...", "categories": {...}})
```

## Limites connues
- Le dédoublonnage par titre est **sans mémoire de la source** : deux articles distincts au titre identique (rare) sont fusionnés, le plus ancien gagne.
- Un fichier invalide disparaît sans trace : impossible de savoir qu'une journée manque.
- Le « dernier » briefing est le dernier par **nom de fichier**, pas forcément celui d'aujourd'hui.
- Aucun test automatisé.
