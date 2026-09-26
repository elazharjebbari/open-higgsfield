"""Ad-creative prompt templates tuned for Seedance 2.5.

Each template turns a short product brief into a concrete video prompt:
subject, action, environment, camera movement and sound, which is what
Seedance responds to best. Prompts are written in English (best model
adherence); spoken lines use the language chosen in the brief.
"""

from dataclasses import dataclass

LANGUAGES = {
    "darija": "Moroccan Darija",
    "fr": "French",
    "ar": "Modern Standard Arabic",
    "en": "English",
    "es": "Spanish",
}


@dataclass(frozen=True)
class Template:
    key: str
    name: str
    goal: str
    aspect_ratio: str
    duration: int
    text: str


TEMPLATES = {t.key: t for t in (
    Template(
        "hook", "Hook 3 secondes (scroll-stopper)", "Arrêter le scroll sur TikTok / Reels",
        "9:16", 5,
        "Vertical social ad. Opening frame: an extreme close-up of {product} appearing suddenly with a "
        "fast whip-pan and a satisfying impact sound. {description} Quick punch-in camera move, bold "
        "high-contrast lighting, vibrant colors, energetic pacing. The product stays sharp and centered. "
        "Target audience: {audience}. {voice}No on-screen text, no logos other than the product itself.",
    ),
    Template(
        "hero", "Showcase produit cinématique", "Mettre le produit en valeur (pub premium)",
        "9:16", 8,
        "Premium commercial of {product}. {description} Slow cinematic orbit around the product on a "
        "clean studio set, soft key light with gentle rim light, shallow depth of field, subtle particles "
        "in the air, reflections on a glossy surface. Final shot: product hero pose, perfectly lit. "
        "Target audience: {audience}. {voice}Elegant music bed. No on-screen text.",
    ),
    Template(
        "ugc", "Témoignage UGC (face caméra)", "Preuve sociale, style créateur authentique",
        "9:16", 10,
        "Authentic UGC-style selfie video filmed on a smartphone. A relatable {persona} holds {product} "
        "close to the camera in a bright, lived-in home, speaks directly to the lens with natural "
        "enthusiasm and shows how they use it. {description} Handheld, slight natural shake, natural "
        "window light, real skin texture. Target audience: {audience}. {voice}No on-screen text.",
    ),
    Template(
        "unboxing", "Unboxing", "Créer le désir, montrer le packaging",
        "9:16", 8,
        "Top-down and close-up unboxing of {product}. Hands open the package slowly on a wooden table, "
        "tissue paper rustles, the product is revealed and lifted toward the camera. {description} "
        "Crisp ASMR sounds, warm natural light, satisfying details. Target audience: {audience}. "
        "{voice}No on-screen text.",
    ),
    Template(
        "problem_solution", "Problème → Solution", "Montrer la douleur puis le résultat",
        "9:16", 10,
        "Two-part ad. First half: a {persona} is visibly frustrated by an everyday problem, muted "
        "desaturated colors, slow handheld camera. Then {product} enters the frame and the scene "
        "transforms: warm vivid colors, smooth dolly-in, the person smiles with relief. {description} "
        "Target audience: {audience}. {voice}No on-screen text.",
    ),
    Template(
        "lifestyle", "Lifestyle / mise en situation", "Associer le produit à un style de vie",
        "9:16", 8,
        "Lifestyle commercial. A stylish {persona} uses {product} naturally during a golden-hour moment "
        "in {setting}. {description} Smooth gimbal tracking shot, warm cinematic grade, shallow depth "
        "of field, candid genuine emotions. Target audience: {audience}. {voice}Upbeat music. "
        "No on-screen text.",
    ),
    Template(
        "offer", "Offre / promo e-commerce", "Conversion : livraison, prix, urgence",
        "9:16", 6,
        "Dynamic e-commerce promo for {product}. {description} Fast-paced sequence: product spin, "
        "close-up of details, a happy customer receiving a delivery box at the door. Punchy transitions, "
        "bright saturated lighting, energetic music. Target audience: {audience}. {voice}"
        "No on-screen text (price and offer will be added in editing).",
    ),
)}


def voice_line(language, script):
    if not script:
        return ""
    lang = LANGUAGES.get(language, language)
    return f'Spoken line in {lang}: "{script.strip()}". '


def render(template_key, product, description="", audience="online shoppers",
           persona="young adult", setting="a modern city apartment", language="darija", script=""):
    if template_key not in TEMPLATES:
        raise KeyError(f"Template inconnu '{template_key}'. Choix : {', '.join(TEMPLATES)}")
    if not product or not product.strip():
        raise ValueError("Le nom du produit est obligatoire")
    tpl = TEMPLATES[template_key]
    description = description.strip()
    if description and not description.endswith("."):
        description += "."
    return " ".join(tpl.text.format(
        product=product.strip(), description=description, audience=audience.strip() or "online shoppers",
        persona=persona.strip() or "young adult", setting=setting.strip() or "a modern city apartment",
        voice=voice_line(language, script),
    ).split())
