# `machine_files.py` — fichiers pour moteurs et agents IA

## But
Écrire, à côté des pages HTML d'un site, les fichiers lisibles par des machines. Module importé par `render.py`, pas un
script exécutable. Aucun accès réseau.

## Fonction
`write_machine_files(site, articles, recent, briefing, now, *, site_url, site_name, site_desc, rolling_days, categories, sources)`

Elle ne lit ni `config.json` ni `sys.argv` : tout arrive en paramètres, donc elle est importable et testable seule.

| Paramètre | Détail |
|---|---|
| `site` | `Path` du dossier du site (`<output_dir>/<id>`), qui doit exister. |
| `articles` / `recent` | tous les articles / ceux des `rolling_days` derniers jours. |
| `briefing` | `("AAAA-MM-JJ", dict)` ou `None`. |
| `now` | `datetime` du rendu (horodatage des fichiers). |
| `site_url` | URL publique du site, **avec** `/` final. |

## Fichiers écrits dans `<site>/`
| Fichier | Contenu |
|---|---|
| `robots.txt` | tout autorisé, avec une entrée explicite pour 7 robots d'IA (GPTBot, OAI-SearchBot, ChatGPT-User, PerplexityBot, ClaudeBot, Google-Extended, CCBot) et le lien du sitemap. |
| `sitemap.xml` | accueil, index d'archive et une page par mois ; `lastmod` = jour du rendu pour le mois le plus récent, `AAAA-MM-28` pour les autres. |
| `feed.xml` | flux Atom des **50** derniers articles de `recent`. |
| `data.json` | copie lisible par machine de la page d'accueil : briefing + articles de `recent` (titre, URL, source, catégorie, date, résumé IA, extrait). |
| `llms.txt` | présentation du site pour les agents IA : pages, fichiers machine, catégories, sources. |

## Exemple
```python
from datetime import datetime, timezone
from pathlib import Path
from machine_files import write_machine_files

write_machine_files(Path(".tmp_out/loreal"), articles, recent, None, datetime.now(timezone.utc),
                    site_url="https://example.org/loreal/", site_name="L'Oréal Watch", site_desc="...",
                    rolling_days=30, categories=["📈 Market"], sources=[])
```

## Limites connues
- Le `lastmod` des mois anciens est **inventé** (`AAAA-MM-28`), pas la vraie date de modification.
- Un site sans article ferait échouer le sitemap (`months[0]`) : `render.py` n'appelle cette fonction que s'il y a des articles.
- Le flux Atom date chaque article à `T00:00:00Z` du jour de publication (l'heure n'est pas conservée).
- Les 7 robots d'IA sont listés en dur ; un nouveau robot demande une modification du code.
- Aucun test automatisé.
