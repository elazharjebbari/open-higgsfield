"""Seedance 2.5 is the only model family this studio is allowed to call.

The text-to-video schema comes from the Higgsfield console model reference
(bytedance/seedance-2.5/text-to-video, verified 2026-09-16). The
image-to-video endpoint follows the same parameters plus a public
``image_url``; check it against the console before production use.
"""

from dataclasses import dataclass

DURATION_MIN, DURATION_MAX = 4, 30
RESOLUTIONS = ("480p", "720p")
ASPECT_RATIOS = ("9:16", "16:9", "1:1", "3:4", "4:3", "21:9")
OUTPUT_FORMATS = ("mp4", "mov")


@dataclass(frozen=True)
class Model:
    key: str
    endpoint: str
    label: str
    required: tuple = ("prompt",)
    aspect_ratios: tuple = ASPECT_RATIOS


MODELS = {
    "t2v": Model(
        key="t2v",
        endpoint="bytedance/seedance-2.5/text-to-video",
        label="Seedance 2.5 — texte → vidéo",
    ),
    "i2v": Model(
        key="i2v",
        endpoint="bytedance/seedance-2.5/image-to-video",
        label="Seedance 2.5 — image produit → vidéo",
        required=("prompt", "image_url"),
    ),
}

ALLOWED_ENDPOINTS = frozenset(m.endpoint for m in MODELS.values())


class ValidationError(ValueError):
    pass


def get_model(key):
    if key not in MODELS:
        raise ValidationError(f"Modèle inconnu '{key}'. Seuls les modèles Seedance 2.5 sont autorisés : {', '.join(MODELS)}")
    return MODELS[key]


def build_payload(model, prompt, duration=5, resolution="720p", aspect_ratio="9:16",
                  output_format="mp4", generate_audio=True, image_url=None):
    """Return a request body that matches the Seedance 2.5 schema, or raise."""
    prompt = (prompt or "").strip()
    if not prompt:
        raise ValidationError("Le prompt est vide")
    if not isinstance(duration, int) or isinstance(duration, bool) or not DURATION_MIN <= duration <= DURATION_MAX:
        raise ValidationError(f"Durée entre {DURATION_MIN} et {DURATION_MAX} secondes")
    if resolution not in RESOLUTIONS:
        raise ValidationError(f"Résolution parmi {', '.join(RESOLUTIONS)}")
    if aspect_ratio not in model.aspect_ratios:
        raise ValidationError(f"Format parmi {', '.join(model.aspect_ratios)}")
    if output_format not in OUTPUT_FORMATS:
        raise ValidationError(f"Sortie parmi {', '.join(OUTPUT_FORMATS)}")
    payload = {
        "prompt": prompt,
        "duration": duration,
        "resolution": resolution,
        "aspect_ratio": aspect_ratio,
        "output_format": output_format,
        "generate_audio": bool(generate_audio),
    }
    if "image_url" in model.required:
        if not image_url or not str(image_url).startswith("https://"):
            raise ValidationError("L'image produit doit être une URL publique https:// (utilisez l'upload)")
        payload["image_url"] = image_url
    elif image_url:
        raise ValidationError("Le modèle texte → vidéo n'accepte pas d'image ; utilisez --model i2v")
    return payload
