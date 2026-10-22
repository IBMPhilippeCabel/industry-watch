# `stats.py` — pages de statistiques de fréquentation

## But
Interroger l'API **GoatCounter** et produire les pages « Stats » : une globale pour le portail et une par site
(pages vues, pages les plus lues, pays, navigateurs).

## Entrées
| Source | Détail |
|---|---|
| `<output_dir>` | argument obligatoire (code `2` sinon). |
| `config.json` | `goatcounter_url` (ex. `https://petfood-watch.goatcounter.com/count`), `site_root_url`, `portal_name`, `sites[].id/site_name`. |
| `GOATCOUNTER_API_KEY` (env) | jeton API GoatCounter. |

## Sorties
| Fichier | Contenu |
|---|---|
| `<output_dir>/stats.html` | stats globales : total de vues, pays, nombre de sites, détail par site. |
| `<output_dir>/<id>/stats.html` | pages les plus vues du site (20 max) + pays et navigateurs **de tout le portail**. |
| Code retour | `0` y compris sans clé ou si l'API échoue ; `2` sans argument. |

Sans jeton ou sans `goatcounter_url`, le script écrit des pages « No data yet » pour qu'aucun lien ne soit en 404.

## Rattachement d'une vue à un site
Le chemin de la page est comparé à `<chemin de site_root_url>/<id>/`. Les chemins qui ne correspondent à aucun site
(page d'accueil du portail, par exemple) sont rangés dans un groupe interne `_portal`, non affiché.

## Exemples d'exécution
```powershell
# Sans clé : pages "No data yet" (utile pour vérifier la mise en page)
python scripts/stats.py .tmp_out
# -> WARN: GOATCOUNTER_API_KEY not set or goatcounter_url missing — writing pending pages
# -> Pending stats pages written for 6 sites

# Avec clé
$env:GOATCOUNTER_API_KEY = "..."
python scripts/stats.py site
# -> stats.html written — global + 6 site pages (42 pages, 11 countries)
```

## Limites connues
- **Il devine l'API** : pour les pays et les navigateurs il essaie plusieurs routes (`/stats/location`, `/locations`, `/countries`, `/browser`, `/browsers`, `/system`) jusqu'à ce qu'une réponde. On ne sait pas laquelle est la bonne, et chaque erreur est avalée (`except Exception: continue`).
- **Les pages affichent « No data yet » aussi bien quand il n'y a aucune visite que quand l'API échoue** : rien ne distingue une panne d'un site vide. Seul un message `WARN` ou `INFO` sur stderr le signale.
- Seulement **100 pages** par appel (`limit=100`) et aucune pagination : un portail très visité sera tronqué.
- Pays et navigateurs sont **globaux** : la page d'un site affiche les chiffres de tous les sites, pas les siens.
- Les compteurs ne couvrent que les visiteurs sans bloqueur de scripts, puisque GoatCounter est chargé côté navigateur.
- Drapeaux : seuls ~25 pays ont un drapeau ; les autres reçoivent 🌐.
- Le workflow lance cette étape avec `continue-on-error: true` : un plantage apparaît comme étape en échec mais ne bloque pas la publication.
- Le CSS est dupliqué par rapport à `render.py` (même charte, copiée), donc un changement de style doit être fait aux deux endroits.
