"""Command line: python -m ad_studio <command> ...

  templates                          list ad templates
  prompt    --template hero ...      print the prompt (free, offline)
  estimate  --template hero ...      price for these exact settings
  generate  --template hero ... [--wait]
  campaign  --templates hook,ugc,hero ... [--yes]   several ads from one brief
  upload    --file produit.jpg       product image -> public URL for --image-url
  status    REQUEST_ID               refresh + download when done
  consumption                        what you spent so far
"""

import argparse
import json
import sys

from . import studio
from .client import ApiError, HiggsfieldClient, load_dotenv
from .models import ASPECT_RATIOS, RESOLUTIONS, ValidationError
from .templates import LANGUAGES, TEMPLATES, render


def _brief_args(p, multi=False):
    if multi:
        p.add_argument("--templates", default="hook,ugc,hero", help="liste séparée par des virgules")
    else:
        p.add_argument("--template", choices=sorted(TEMPLATES))
        p.add_argument("--prompt", help="prompt libre (remplace le template)")
    p.add_argument("--product", default="", help="nom du produit, ex. 'a rose-gold facial serum bottle'")
    p.add_argument("--description", default="", help="détails visuels : couleurs, matière, bénéfice")
    p.add_argument("--audience", default="online shoppers")
    p.add_argument("--persona", default="young adult")
    p.add_argument("--setting", default="a modern city apartment")
    p.add_argument("--language", default="darija", help=f"langue de la voix : {', '.join(LANGUAGES)}")
    p.add_argument("--script", default="", help="phrase prononcée dans la vidéo (optionnel)")
    p.add_argument("--model", choices=("t2v", "i2v"), default=None,
                   help="t2v = texte→vidéo, i2v = image produit→vidéo (auto si --image-url)")
    p.add_argument("--image-url", default=None, help="URL publique de l'image produit (voir 'upload')")
    p.add_argument("--duration", type=int, default=None, help="4 à 30 s (défaut : celui du template)")
    p.add_argument("--resolution", choices=RESOLUTIONS, default="720p")
    p.add_argument("--aspect-ratio", choices=ASPECT_RATIOS, default=None)
    p.add_argument("--no-audio", action="store_true")
    p.add_argument("--label", default="")


def _job_spec(args, template_key=None):
    template_key = template_key or args.template
    if getattr(args, "prompt", None):
        prompt, tpl = args.prompt, TEMPLATES.get(template_key)
    elif template_key:
        tpl = TEMPLATES[template_key]
        prompt = render(template_key, args.product, args.description, args.audience,
                        args.persona, args.setting, args.language, args.script)
    else:
        raise ValidationError("Indiquez --template ou --prompt")
    model = args.model or ("i2v" if args.image_url else "t2v")
    params = {
        "duration": args.duration or (tpl.duration if tpl else 5),
        "resolution": args.resolution,
        "aspect_ratio": args.aspect_ratio or (tpl.aspect_ratio if tpl else "9:16"),
        "generate_audio": not args.no_audio,
        "image_url": args.image_url,
    }
    return model, prompt, params, template_key or "custom"


def _print(obj):
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def _fmt_usd(value):
    return "?" if value is None else f"{value:.2f} $"


def main(argv=None):
    load_dotenv(studio.ROOT / ".env")
    parser = argparse.ArgumentParser(prog="ad_studio", description="Pubs vidéo Seedance 2.5 via l'API Higgsfield")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("templates")
    for name in ("prompt", "estimate", "generate"):
        p = sub.add_parser(name)
        _brief_args(p)
        if name == "generate":
            p.add_argument("--wait", action="store_true", help="attendre et télécharger la vidéo")
    p = sub.add_parser("campaign")
    _brief_args(p, multi=True)
    p.add_argument("--yes", action="store_true", help="ne pas demander de confirmation du budget")
    p.add_argument("--wait", action="store_true")
    p = sub.add_parser("upload")
    p.add_argument("--file", required=True)
    p = sub.add_parser("status")
    p.add_argument("request_id")
    p.add_argument("--wait", action="store_true")
    sub.add_parser("consumption")
    sub.add_parser("history")
    args = parser.parse_args(argv)
    ledger = studio.Ledger()

    try:
        if args.cmd == "templates":
            for t in TEMPLATES.values():
                print(f"{t.key:18} {t.aspect_ratio:5} {t.duration:>2}s  {t.name} — {t.goal}")
            return 0
        if args.cmd == "prompt":
            model, prompt, params, _ = _job_spec(args)
            _print({"model": model, "prompt": prompt, **{k: v for k, v in params.items() if v is not None}})
            return 0
        if args.cmd == "consumption":
            _print(ledger.consumption())
            return 0
        if args.cmd == "history":
            for j in ledger.load():
                print(f"{j['created_at']}  {j['status']:11} {_fmt_usd(j.get('estimate_usd')):>8}  "
                      f"{j.get('template', ''):16} {j['request_id']}  {' '.join(j.get('files', []))}")
            return 0

        client = HiggsfieldClient()
        if args.cmd == "upload":
            print(client.upload(args.file))
        elif args.cmd == "estimate":
            model, prompt, params, _ = _job_spec(args)
            est = studio.estimate(client, model, prompt, **params)
            print(f"Estimation : {_fmt_usd(est['usd'])}  ({json.dumps(est['raw'])})")
        elif args.cmd == "generate":
            model, prompt, params, tkey = _job_spec(args)
            job = studio.submit(client, ledger, model, prompt, label=args.label, template=tkey, **params)
            print(f"Soumis : {job['request_id']}  (estimation {_fmt_usd(job['estimate_usd'])})")
            if args.wait:
                _finish(client, ledger, job["request_id"])
        elif args.cmd == "campaign":
            keys = [k.strip() for k in args.templates.split(",") if k.strip()]
            specs = [_job_spec(args, k) for k in keys]
            total = 0.0
            for model, prompt, params, tkey in specs:
                usd = studio.estimate(client, model, prompt, **params)["usd"] or 0
                total += usd
                print(f"  {tkey:18} {params['duration']:>2}s {params['aspect_ratio']:5} {_fmt_usd(usd)}")
            print(f"Total estimé : {total:.2f} $ pour {len(specs)} vidéos")
            if not args.yes and input("Lancer la génération ? [o/N] ").strip().lower() not in ("o", "oui", "y", "yes"):
                print("Annulé, rien n'a été facturé.")
                return 0
            ids = []
            for model, prompt, params, tkey in specs:
                job = studio.submit(client, ledger, model, prompt, label=args.label, template=tkey, **params)
                ids.append(job["request_id"])
                print(f"Soumis {tkey}: {job['request_id']}")
            if args.wait:
                for rid in ids:
                    _finish(client, ledger, rid)
        elif args.cmd == "status":
            if args.wait:
                _finish(client, ledger, args.request_id)
            else:
                job = studio.refresh(client, ledger, args.request_id)
                print(f"{job['status']}  {' '.join(job.get('files', []))}")
    except (ApiError, ValidationError, ValueError, KeyError) as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1
    return 0


def _finish(client, ledger, request_id):
    job = studio.wait(client, ledger, request_id,
                      on_tick=lambda j: print(f"  {request_id[:8]}… {j.get('status')}", flush=True))
    if job.get("files"):
        print("Vidéo : " + ", ".join(job["files"]))
    elif job.get("status") not in ("completed",):
        print(f"Statut final : {job.get('status')} (relancez 'status {request_id} --wait' si encore en cours)")
