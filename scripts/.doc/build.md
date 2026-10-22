# `build.py` — collecte et enrichissement des articles

## But
Pour **un site** déclaré dans `config.json` : lire ses flux RSS, ne garder que les articles pertinents, classer
chaque article dans une catégorie du site, le résumer avec l'IA (Groq) et écrire le résultat en JSON sur disque.
Il génère aussi le **briefing du jour**. C'est la seule étape qui parle au réseau et à l'IA ; `render.py` ne fait
ensuite que mettre en forme.

## Entrées
| Source | Détail |
|---|---|
| Argument `--site <id>` | **obligatoire** : id du site dans `config.json`. Absent → code `2` et message d'usage ; id inconnu → code `1` avec la liste des ids valides. Les formes `--site loreal` et `--site=loreal` sont acceptées. |
| `config.json` | `data_dir`, `sources_file`, `site_name`, `site_description`, `categories` (optionnel), `account_filters` (sites « Companies & Accounts »), `site_icon.url/path`. |
| `<sources_file>` | liste de sources : `name`, `url`, `rss`, `description`, `score`, `default_category`. Une source avec `"rss": null` est ignorée. |
| `GROQ_API_KEY` (env, optionnel) | active résumés et briefing. Sans clé, le build réussit quand même, sans IA. |
| Fichiers déjà présents dans `<data_dir>` | servent à ne stocker que les articles réellement nouveaux. |

## Sorties
| Fichier | Contenu |
|---|---|
| `<data_dir>/AAAA/MM/JJ.json` | articles **par date de publication** : `source, title, link, summary, date, category` + `ai_summary` si l'IA a répondu. Fusionné avec le fichier existant, jamais écrasé. |
| `<data_dir>/AAAA/MM/JJ.briefing.txt` | JSON `{"hook": "...", "categories": {"<catégorie du site>": "...|null"}}`, daté du jour d'exécution. Écrit seulement si `GROQ_API_KEY` est défini. |
| `site_icon.path` | icône téléchargée depuis `site_icon.url` si le fichier local n'existe pas encore. |
| Code retour | `0` normal (y compris « rien de nouveau »), `1` si **aucun** article n'a pu être récupéré. |

## Déroulement
1. `fetch_site_icon()` — télécharge l'icône si besoin.
2. `load_articles()` — lit chaque flux (15 articles max par source), puis :
   - **sites compte** (`account_filters`) : garde un article seulement s'il mentionne un mot-clé du compte, **y compris pour les flux Google News**. La comparaison se fait sur le texte normalisé (accents, apostrophes `’`/`'`, casse) et en **mot entier** (`extra` ne matche pas `extraordinary`) ;
   - `classify()` — repère M&A / Regulation / Innovation par mots-clés et traduit ce thème vers la catégorie **du site** (`💡 Innovation` → `💡 Innovation & RTD`) ; à défaut, `default_category` de la source ;
   - déduplique par lien **et** par titre normalisé ;
   - **n'accepte que des liens `http(s)` absolus** (`safe_url`) : un article dont le lien est `javascript:`, `data:`, relatif ou contient un espace est écarté avec un `WARN` ;
   - nettoie titres et extraits (`clean_text`) : balises retirées **avant et après** le décodage des entités, pour qu'un flux qui envoie son HTML en `&lt;script&gt;` ne le fasse pas réapparaître comme vraie balise. Un `<` ou `>` isolé (« marge > 20 % ») est conservé.
3. Retire ce qui est déjà stocké ; s'il ne reste rien : « No new article… nothing written », code `0`.
4. `summarize()` — par lots de 6, 20 s de pause entre lots (quota Groq gratuit). Prompt construit avec `site_name` et `site_description`.
5. Écrit les fichiers jour par jour.
6. Briefing : `briefing_inputs()` prend les nouveaux articles **plus ceux publiés dans les 3 derniers jours**, pour qu'un passage calme (1–2 articles) n'écrase pas le briefing de la journée. Le prompt liste les catégories du site. En cas d'échec de l'IA, un briefing existant est **conservé** ; sinon un résumé chiffré sans IA est écrit.

## Exemples d'exécution
```powershell
# Un site, sans IA (aucune clé) — ce que fait un test local
python scripts/build.py --site loreal

# Avec IA
$env:GROQ_API_KEY = "gsk_..."
python scripts/build.py --site beauty-watch
```
Sortie typique :
```
L'Oréal Corporate & M&A (Google News): 15 articles
Cosmetics Business: 15 articles
...
Wrote 2 new articles to web_sites\loreal\data\2026\08\11.json
Total: 12 new articles (0 summarized by Groq)
```
En CI : `python scripts/build.py --site <id>` pour chaque id, en parallèle (voir `.github/workflows/OnSchedule_Site_Update.yml`).

## Limites connues
- Le workflow capture le code retour de `build.py` sans interrompre l'étape : les données sont commitées dans tous les cas (un échec laisse un commit vide `... - BUILD FAILED (exit N)` avec les `WARN`/`ERROR` en corps), puis le job du site échoue en dernière étape. Un **flux isolé en erreur** reste un simple `WARN` (annotation + résumé, job vert) : le code retour `1` n'est renvoyé que si **aucune** source n'a donné d'article.
- `classify()` cherche des **sous-chaînes**, pas des mots entiers : `law` matche `flawless`, `ban ` ou `eu ` aussi dans des phrases sans rapport. Une catégorie peut donc être fausse sans que l'article soit hors sujet.
- Le filtre compte ne regarde que titre + extrait + tags du flux, pas l'article complet. Un article qui ne cite la marque que dans son corps est perdu.
- Les marques s'écrivent en **une seule forme** dans la config : `loreal` et `l'oreal` sont deux mots différents (d'où les deux dans `account_filters`). Les accents et apostrophes, eux, sont normalisés.
- Les flux Google News renvoient des redirections `news.google.com/...` : la déduplication par lien ne détecte pas deux liens différents pour le même article, seule celle par titre le fait.
- Pas de nouvelle tentative sur un flux en erreur (délai 30 s, puis il est sauté avec un `WARN`).
- Quota Groq gratuit : au-delà d'environ 6 articles par minute la durée d'exécution grimpe ; un gros rattrapage (premier lancement d'un site) peut durer plusieurs minutes.
- Le briefing d'un jour peut mélanger des articles des 3 derniers jours : il décrit une **tendance récente**, pas strictement « aujourd'hui ».
- Le script exécute son code au chargement du module (lecture de `sys.argv` et `config.json`) : il n'est pas importable pour des tests.
