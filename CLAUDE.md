# Open Higgsfield Ad Studio

Studio de pubs vidéo qui appelle **uniquement Seedance 2.5** via l'API pay-as-you-go de Higgsfield.

## Règles
- N'appeler que les endpoints de `ad_studio/models.py` (`bytedance/seedance-2.5/text-to-video` et `.../image-to-video`). Ne jamais ajouter un autre modèle.
- Toujours estimer (`python -m ad_studio estimate ...`) et annoncer le prix avant une génération que l'utilisateur n'a pas explicitement demandée. Une campagne multi-vidéos passe par `campaign` (confirmation du total).
- Ne jamais afficher, commiter ou envoyer ailleurs que vers api.higgsfield.ai la clé (`HF_API_KEY_ID`/`HF_API_KEY_SECRET`, `.env`).
- Une soumission POST n'est jamais relancée automatiquement (pas d'idempotence) : en cas de doute, vérifier l'historique (`history`) avant de resoumettre.
- Prompts vidéo en anglais ; la phrase parlée (`--script`) dans la langue du marché (darija par défaut).

## Commandes
- Tests : `python3 -m unittest`
- Prompt hors-ligne : `python -m ad_studio prompt --template hero --product "..."`
- Génération : `python -m ad_studio generate --template ugc --product "..." --wait`
- Studio web local : `python -m ad_studio.server` → http://127.0.0.1:8787
- Consommation : `python -m ad_studio consumption`
