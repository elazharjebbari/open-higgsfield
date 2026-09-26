#!/usr/bin/env bash
# Installe le studio Seedance 2.5 sur le VPS Fluviqa, à la manière des autres apps
# (cf. fluviqa-deploy/deploy/provision-vhost.sh) :
#   service systemd sur 127.0.0.1:$PORT  <-  vhost OpenLiteSpeed studio.fluviqa.shop (HTTPS certbot)
#
# À lancer en root SUR le VPS, par exemple depuis le Mac :
#   ssh -t -i ~/.ssh/id_ed25520 root@185.172.57.121 \
#     'curl -fsSL https://raw.githubusercontent.com/elazharjebbari/open-higgsfield/claude/higgsfield-ad-generation-cloud-gdknjo/deploy/install-vps.sh | bash'
# Idempotent : le relancer met à jour le code et ne casse rien.
set -Eeuo pipefail
{ # bloc lu en entier avant exécution : sûr avec `curl | bash`

DOMAIN="${DOMAIN:-studio.fluviqa.shop}"
BRANCH="${BRANCH:-claude/higgsfield-ad-generation-cloud-gdknjo}"
REPO="https://github.com/elazharjebbari/open-higgsfield.git"
PORT="${PORT:-8021}"
APP_DIR=/opt/ad-studio
ENV_FILE=/etc/ad-studio.env
SVC=ad-studio
VH=ad-studio
LS=/usr/local/lsws
CONF=$LS/conf/httpd_config.conf
LE="/etc/letsencrypt/live/$DOMAIN"

die() { echo "ERREUR : $*" >&2; exit 1; }
step() { echo "== $*"; }

# --- Garde de cible : uniquement le VPS Fluviqa (OLS + apps Fluviqa présents) -----------------
[ "$(id -u)" = 0 ] || die "à lancer en root"
[ -x "$LS/bin/lswsctrl" ] && [ -f "$CONF" ] || die "OpenLiteSpeed introuvable : mauvaise machine ?"
[ -d /var/www/fluviqa-tracking ] || die "/var/www/fluviqa-tracking absent : mauvaise machine ?"
command -v certbot >/dev/null || die "certbot absent"
python3 -c 'import sys; assert sys.version_info >= (3, 10)' || die "Python 3.10+ requis"

# --- Port libre (8012/8013/8015 = apps Fluviqa, 8014 = voisin) ---------------------------------
if ss -ltnH "sport = :$PORT" | grep -q . && ! systemctl is-active -q "$SVC"; then
  die "le port $PORT est déjà pris ; relancez avec PORT=<autre port>"
fi

step "Code ($BRANCH) dans $APP_DIR"
id adstudio >/dev/null 2>&1 || useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin adstudio
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" fetch -q --depth 1 origin "$BRANCH"
  git -C "$APP_DIR" checkout -q -B "$BRANCH" FETCH_HEAD
else
  git clone -q --depth 1 --branch "$BRANCH" "$REPO" "$APP_DIR"
fi
mkdir -p "$APP_DIR/work" "$APP_DIR/outputs"
chown -R adstudio:adstudio "$APP_DIR/work" "$APP_DIR/outputs"

step "SDK officiel Higgsfield ($APP_DIR/.venv)"
python3 -c 'import ensurepip' 2>/dev/null || apt-get install -y -qq python3-venv >/dev/null
[ -x "$APP_DIR/.venv/bin/python" ] || python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install -q --disable-pip-version-check -r "$APP_DIR/requirements.txt"
# Exemple Seedance 2.5 (génération facturée) avec la clé du studio, jamais affichée.
cat > /usr/local/bin/ad-studio-example <<'CMD'
#!/bin/sh
set -a; . /etc/ad-studio.env; set +a
cd /opt/ad-studio && exec runuser -u adstudio -- /opt/ad-studio/.venv/bin/python main.py "$@"
CMD
chmod 750 /usr/local/bin/ad-studio-example

step "Secrets ($ENV_FILE)"
if [ ! -f "$ENV_FILE" ]; then
  PASS=$(python3 -c 'import secrets; print(secrets.token_urlsafe(18))')
  umask 077
  cat > "$ENV_FILE" <<ENV
# Clé API Higgsfield (console API > API keys). Ne jamais commiter.
HF_API_KEY_ID=
HF_API_KEY_SECRET=
# Accès au studio web (authentification HTTP Basic)
STUDIO_USER=studio
STUDIO_PASSWORD=$PASS
ENV
  umask 022
  echo "   Identifiants du studio (affichés une seule fois) : studio / $PASS"
fi
chown root:adstudio "$ENV_FILE"
chmod 640 "$ENV_FILE"
if ! grep -q '^HF_API_KEY_ID=.\+' "$ENV_FILE" && (: </dev/tty) 2>/dev/null; then
  read -rp "   HF_API_KEY_ID : " KID </dev/tty
  read -rsp "   HF_API_KEY_SECRET (masqué) : " KSEC </dev/tty; echo
  python3 - "$ENV_FILE" "$KID" "$KSEC" <<'PY'
import sys
path, kid, secret = sys.argv[1:]
lines = open(path).read().splitlines()
out = [f"HF_API_KEY_ID={kid}" if l.startswith("HF_API_KEY_ID=") else
       f"HF_API_KEY_SECRET={secret}" if l.startswith("HF_API_KEY_SECRET=") else l for l in lines]
open(path, "w").write("\n".join(out) + "\n")
PY
fi

step "Service systemd $SVC (127.0.0.1:$PORT)"
cat > /etc/systemd/system/$SVC.service <<UNIT
[Unit]
Description=Open Higgsfield Ad Studio (Seedance 2.5)
After=network-online.target
Wants=network-online.target

[Service]
User=adstudio
Group=adstudio
WorkingDirectory=$APP_DIR
EnvironmentFile=$ENV_FILE
# Jamais sans mot de passe : le studio dépense le solde Higgsfield.
ExecStartPre=/bin/sh -c 'test -n "\$STUDIO_PASSWORD"'
ExecStart=/usr/bin/python3 -m ad_studio.server --host 127.0.0.1 --port $PORT
Restart=always
RestartSec=3
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=$APP_DIR/work $APP_DIR/outputs
ProtectHome=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable -q "$SVC"
systemctl restart "$SVC"
sleep 2
systemctl is-active -q "$SVC" || { journalctl -u "$SVC" -n 30 --no-pager; die "service $SVC inactif"; }

step "Vhost OpenLiteSpeed $VH -> $DOMAIN"
cp -n "$CONF" "$CONF.avant-ad-studio" 2>/dev/null || true
mkdir -p "$LS/$VH/html/.well-known/acme-challenge" "$LS/conf/vhosts/$VH"
chown -R www-data:www-data "$LS/$VH"
write_vhost() {
SSL_BLOCK=""
if [ -d "$LE" ]; then
  SSL_BLOCK="vhssl {
  keyFile                 $LE/privkey.pem
  certFile                $LE/cert.pem
  certChain               1
  CACertPath              $LE/fullchain.pem
  CACertFile              $LE/chain.pem
}"
fi
cat > "$LS/conf/vhosts/$VH/vhost.conf" <<VHC
docRoot                   \$VH_ROOT/html
enableGzip                1

extprocessor adStudio {
  type                    proxy
  address                 http://127.0.0.1:$PORT
  maxConns                100
  initTimeout             120
  retryTimeout            10
  respBuffer              0
}

context /.well-known/acme-challenge/ {
  location                \$VH_ROOT/html/.well-known/acme-challenge/
  allowBrowse             1
  addDefaultCharset       off
}

context / {
  type                    proxy
  handler                 adStudio
  addDefaultCharset       off
}

# Tout en HTTPS (le mot de passe ne doit jamais circuler en clair), sauf le défi ACME.
rewrite {
  enable                  1
  rules                   <<<END_rules
RewriteCond %{HTTPS} !on
RewriteCond %{REQUEST_URI} !^/\.well-known/acme-challenge/
RewriteRule ^(.*)\$ https://$DOMAIN/\$1 [R=301,L]
END_rules
}

module cache {
  ls_enabled              0
}

$SSL_BLOCK
VHC
chown -R www-data:www-data "$LS/conf/vhosts/$VH"
}
write_vhost

map_listeners() {
  python3 - "$CONF" "$VH" "$DOMAIN" "$@" <<'PY'
import sys
path, vh, domain, *listeners = sys.argv[1:]
s = open(path).read()
if f"virtualhost {vh} " not in s and f"virtualhost {vh}{{" not in s:
    s += f"""
virtualhost {vh} {{
  vhRoot                  {vh}
  configFile              conf/vhosts/{vh}/vhost.conf
  allowSymbolLink         1
  enableScript            1
  restrained              0
}}
"""
for header in listeners:
    i = s.index(header)
    j = s.index("\n}", i)
    block = s[i:j]
    if f" {vh} {domain}" in block:
        continue
    line = f"map                     {vh} {domain}"
    marker = "map                     Example *"
    block = block.replace(marker, line + "\n  " + marker, 1) if marker in block else block.rstrip() + "\n  " + line
    s = s[:i] + block + s[j:]
open(path, "w").write(s)
PY
}
map_listeners "listener Default{"
$LS/bin/lswsctrl restart >/dev/null 2>&1 || true
sleep 3

if [ ! -d "$LE" ]; then
  step "Certificat Let's Encrypt pour $DOMAIN"
  certbot certonly --webroot -w "$LS/$VH/html" -d "$DOMAIN" \
    --keep-until-expiring --non-interactive --agree-tos --register-unsafely-without-email \
    || die "certbot en échec (le DNS $DOMAIN pointe-t-il bien sur ce VPS ?)"
  write_vhost  # ajoute le bloc vhssl maintenant que le certificat existe
fi

map_listeners "listener Defaultssl"
HOOK=/etc/letsencrypt/renewal-hooks/deploy/ad-studio-ols.sh
printf '#!/bin/sh\n%s/bin/lswsctrl restart >/dev/null 2>&1 || true\n' "$LS" > "$HOOK"
chmod 755 "$HOOK"
$LS/bin/lswsctrl restart >/dev/null 2>&1 || true
sleep 3

step "Contrôle"
CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "https://$DOMAIN/" || true)
[ "$CODE" = 401 ] || die "https://$DOMAIN/ répond $CODE (attendu : 401, mot de passe demandé)"
grep -q '^HF_API_KEY_ID=.\+' "$ENV_FILE" \
  || echo "   ⚠ Clé Higgsfield absente : complétez $ENV_FILE puis 'systemctl restart $SVC'"
echo "OK — studio en ligne : https://$DOMAIN  (identifiant : $(grep '^STUDIO_USER=' "$ENV_FILE" | cut -d= -f2))"
exit 0
}
