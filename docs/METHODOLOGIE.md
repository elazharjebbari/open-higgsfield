# Méthodologie (d'après la vidéo) appliquée à ce dépôt

La vidéo décrit comment arrêter de payer les forfaits Higgsfield et passer par leur **API pay-as-you-go**, puis brancher cette clé sur un clone open-source (« Open Higgsfield ») installé **chez soi**. Voici chaque étape et où elle se trouve ici.

| # | Étape de la vidéo | Dans ce dépôt |
|---|---|---|
| 1 | **Pourquoi l'API** : les forfaits (9 $ → 165 $/mois) remettent les crédits non consommés à zéro chaque mois. L'API facture uniquement ce qui est consommé, et le crédit reste valable un an. | `python -m ad_studio consumption` et l'en-tête du studio web affichent ce que vous avez réellement dépensé (estimations par vidéo, enregistrées dans `work/ledger.json`). |
| 2 | **Espace API séparé** : les crédits du site Higgsfield et ceux de l'API sont deux comptes distincts. | Rechargez la partie **API** (minimum 5 $). Astuce de la vidéo : e-mail professionnel vérifié + carte ajoutée = 15 $ offerts. |
| 3 | **Choisir ses modèles** (jusqu'à 50) dans la console API. La vidéo prend Seedance 2.5, Seedance 2.0 et Marketing Studio. | Ici on ne garde **que Seedance 2.5** : sélectionnez-le seul dans la console. Le code refuse tout autre modèle (`ad_studio/models.py`, `ALLOWED_ENDPOINTS`). |
| 4 | **Créer une clé API**, lui donner un nom (ex. « test »), la copier : elle ne s'affiche qu'une fois. Ne la donner à personne ; la supprimer si elle a fuité et en recréer une. | La clé va dans `.env` (ignoré par git) ou dans les variables de l'environnement cloud : `HF_API_KEY_ID`, `HF_API_KEY_SECRET`. Elle n'est jamais envoyée au navigateur ni à un autre hôte qu'`api.higgsfield.ai`. |
| 5 | **Ne pas coller sa clé dans une version en ligne** d'Open Higgsfield hébergée par quelqu'un d'autre : on peut vous la voler. Installer le clone **sur sa propre machine**. | Le studio web écoute sur `127.0.0.1` uniquement. Rien à installer à part Python 3.10+ (aucune dépendance). |
| 6 | **Installer avec un agent IA** (Codex / Claude) qui clone le repo et le lance pour vous. | C'est ce que fait ce dépôt dans une session cloud Claude Code : le hook `.claude/hooks/session-start.sh` prépare la session et vérifie clé + réseau ; `CLAUDE.md` donne les règles à l'agent (Seedance 2.5 uniquement, estimer avant de générer). |
| 7 | **Générer** : choisir le modèle, coller un prompt, lancer, la vidéo arrive comme sur Higgsfield. | Studio web (`python -m ad_studio.server`) ou CLI (`python -m ad_studio generate ... --wait`). Les vidéos sont téléchargées dans `outputs/` (les liens de l'API expirent après quelques jours). |
| 8 | **Ne pas faire un « Higgsfield bis » générique** : se spécialiser sur un usage précis. | La spécialisation choisie : **les pubs vidéo e-commerce**. 7 templates (hook, showcase, UGC, unboxing, problème→solution, lifestyle, offre), voix en darija/français/arabe, mode campagne pour produire plusieurs variantes A/B d'un même brief. |
| 9 | **Brancher l'API à sa propre app** (ex. son outil e-commerce qui crée marque, store Shopify et visuels). | `ad_studio.client.HiggsfieldClient` et `ad_studio.studio` s'importent tels quels dans une autre application Python. Pour une mise en ligne destinée à des clients, ajoutez votre propre authentification devant le serveur. |

## Bonnes pratiques pub avec Seedance 2.5
- **Format** : 9:16 pour TikTok/Reels/Shorts, 1:1 pour le feed, 16:9 pour YouTube.
- **Durée** : 5–10 s suffisent pour une pub ; le prix est proportionnel aux secondes (≈ 0,18 $/s au tarif le plus haut). Testez en **480p** pour valider une idée, puis refaites en **720p**.
- **Prompt** : sujet concret + action + décor + mouvement de caméra + son. Pas de texte à l'écran : prix, logo et CTA s'ajoutent au montage.
- **Image produit** : pour que le produit ressemble vraiment au vôtre, fournissez une photo (mode image → vidéo).
- **Variantes** : lancez 3 angles (hook, UGC, showcase) avec `campaign`, gardez celui qui performe en publicité.
