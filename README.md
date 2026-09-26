# open-higgsfield — Vidéos publicitaires avec Seedance 2.5

Un « Open Higgsfield » minimal et spécialisé : un studio de **pubs vidéo** qui utilise **uniquement Seedance 2.5** via l'**API pay-as-you-go de Higgsfield**. Vous ne payez que les secondes générées, sans forfait mensuel qui remet vos crédits à zéro.

La méthode suivie (celle de la vidéo) est détaillée dans [docs/METHODOLOGIE.md](docs/METHODOLOGIE.md).

## 1. Préparer Higgsfield (une seule fois)
1. Sur Higgsfield, ouvrez la partie **API** (compte séparé des crédits du site).
2. Dans la sélection de modèles, activez **Seedance 2.5** (text-to-video et image-to-video).
3. Rechargez le solde API (minimum 5 $).
4. Créez une **clé API** et copiez tout de suite le *key id* et le *secret* (ils ne s'affichent qu'une fois).

## 2. Installer
Python 3.10+ suffit : aucune dépendance.

```bash
git clone https://github.com/elazharjebbari/open-higgsfield.git
cd open-higgsfield
cp .env.example .env   # puis collez HF_API_KEY_ID et HF_API_KEY_SECRET dedans
```

### Dans une session cloud Claude Code
- Dans les réglages de l'environnement cloud, ajoutez les variables `HF_API_KEY_ID` et `HF_API_KEY_SECRET`.
- Dans **Accès réseau**, autorisez le domaine `api.higgsfield.ai` (ainsi que l'hôte de stockage des vidéos s'il est bloqué au téléchargement).
- Le hook `.claude/hooks/session-start.sh` vérifie tout au démarrage, et `CLAUDE.md` indique à Claude les règles du studio. Il suffit ensuite de demander : « fais-moi 3 pubs pour mon sérum à l'argan ».

## 3. Générer des pubs

### Studio web (sur votre PC)
```bash
python3 -m ad_studio.server        # http://127.0.0.1:8787
```
Choisissez le type de pub, décrivez le produit, ajoutez une photo si vous en avez une, cliquez **Estimer le prix** puis **Générer**. Les vidéos s'affichent et sont enregistrées dans `outputs/`. La consommation totale est affichée en haut.

### Ligne de commande
```bash
python3 -m ad_studio templates                      # les 7 types de pub
python3 -m ad_studio prompt --template ugc --product "an argan oil bottle" \
    --script "Had zit beddel lia cheefri f simana"  # voir le prompt, gratuit

python3 -m ad_studio estimate --template hero --product "an argan oil bottle"
python3 -m ad_studio generate --template hero --product "an argan oil bottle" \
    --description "amber glass, golden drops, Atlas mountains mood" --wait

# Avec la photo du produit (image → vidéo)
URL=$(python3 -m ad_studio upload --file produit.jpg)
python3 -m ad_studio generate --template unboxing --product "an argan oil bottle" --image-url "$URL" --wait

# Campagne A/B : 3 angles, prix total affiché avant confirmation
python3 -m ad_studio campaign --templates hook,ugc,hero --product "an argan oil bottle" \
    --audience "Moroccan women 25-40" --language darija --wait

python3 -m ad_studio history
python3 -m ad_studio consumption
```

## Types de pub
| Template | Usage | Défaut |
|---|---|---|
| `hook` | scroll-stopper des 3 premières secondes | 9:16, 5 s |
| `hero` | showcase produit cinématique | 9:16, 8 s |
| `ugc` | témoignage face caméra style créateur | 9:16, 10 s |
| `unboxing` | ouverture du colis, ASMR | 9:16, 8 s |
| `problem_solution` | problème → produit → résultat | 9:16, 10 s |
| `lifestyle` | produit dans un moment de vie | 9:16, 8 s |
| `offer` | promo e-commerce (texte prix ajouté au montage) | 9:16, 6 s |

Paramètres Seedance 2.5 : 4 à 30 s, 480p ou 720p, formats 9:16 · 1:1 · 16:9 · 3:4 · 4:3 · 21:9, audio généré en option.

## Sécurité
- `.env`, `work/` et `outputs/` ne sont jamais commités.
- La clé reste côté serveur local ; elle n'est envoyée qu'à `api.higgsfield.ai`.
- Le studio web écoute sur `127.0.0.1`. Ne l'exposez pas sur Internet sans authentification : n'importe qui pourrait dépenser votre solde.
- Si une clé a fuité, supprimez-la dans la console API et créez-en une nouvelle.

## Structure
```
ad_studio/models.py     Seedance 2.5 uniquement + validation des paramètres
ad_studio/client.py     client REST Higgsfield (auth, estimation, upload, statut, téléchargement)
ad_studio/templates.py  templates de prompts publicitaires
ad_studio/studio.py     soumission, suivi, journal de consommation
ad_studio/cli.py        ligne de commande
ad_studio/server.py     studio web local (+ web/index.html)
tests/                  python3 -m unittest
```
