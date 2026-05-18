#!/usr/bin/env bash
set -euo pipefail

MAIL_CFG="mail/config"
SSH_KEY="$HOME/.ssh/id_rsa"

setup_ssh() {
    [[ -f "$SSH_KEY" ]] || ssh-keygen -t rsa -b 4096 -f "$SSH_KEY" -N "" -q
    mkdir -p ssh && cp "${SSH_KEY}.pub" ssh/id_rsa.pub 2>/dev/null || true
    echo "SSH: ready"
}

setup_mail() {
    mkdir -p "$MAIL_CFG/ssl"
    [[ -f "$MAIL_CFG/ssl/cert.pem" ]] || \
        openssl req -new -newkey rsa:4096 -days 365 -nodes -x509 \
        -subj "/C=RU/ST=Lab/L=Lab/O=Lab/CN=mail.example.local" \
        -keyout "$MAIL_CFG/ssl/key.pem" -out "$MAIL_CFG/ssl/cert.pem" 2>/dev/null
    chmod 600 "$MAIL_CFG/ssl/key.pem"
    [[ -s "$MAIL_CFG/postfix-accounts.cf" ]] || \
        printf 'user@example.local|{SHA512-CRYPT}$6$lab$xxx\ntest@example.local|{SHA512-CRYPT}$6$lab$yyy\n' > "$MAIL_CFG/postfix-accounts.cf"
    echo "Mail: ready"
}

setup() { setup_ssh; setup_mail; echo "Setup: complete"; }
up()      { docker compose up -d --build; }
down()    { docker compose down; }
restart() { docker compose restart; }
status()  { docker compose ps; }
logs()    { docker compose logs "${1:-}" --tail=50; }

check_mail() {
    docker compose exec -T mail python3 << 'PYEOF'
import email, glob, email.header
def dec(v):
    if not v: return "Unknown"
    return "".join((t.decode(e or "utf-8", errors="replace") if isinstance(t, bytes) else t) for t, e in email.header.decode_header(v))
files = sorted(glob.glob("/var/mail/example.local/user/new/*") + glob.glob("/var/mail/example.local/user/cur/*"))
if not files:
    print("Mailbox is empty.")
else:
    for f in files:
        with open(f, "rb") as fh: msg = email.message_from_binary_file(fh)
        print("=" * 60)
        print("FROM:    {}".format(dec(msg.get("From"))))
        print("TO:      {}".format(dec(msg.get("To"))))
        print("SUBJECT: {}".format(dec(msg.get("Subject"))))
        print("DATE:    {}".format(msg.get("Date", "?")))
        for p in msg.walk():
            if p.get_content_type() == "text/plain" and "attachment" not in str(p.get_content_disposition()):
                b = p.get_payload(decode=True)
                if b:
                    print("-" * 60)
                    print(b.decode(p.get_content_charset() or "utf-8", errors="replace"))
                    break
        print()
PYEOF
}

clean_mail() {
    docker compose exec -T mail bash -c "rm -f /var/mail/example.local/user/new/* /var/mail/example.local/user/cur/*"
    echo "Mailbox: cleaned"
}

send_test() {
    curl -s -X POST http://localhost:5000/api/test
    echo "Test alert: sent"
}

ssh_conn() {
    ssh -p 2222 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null student@127.0.0.1
}

web() {
    xdg-open http://localhost:5000 2>/dev/null || open http://localhost:5000 2>/dev/null || echo "Open: http://localhost:5000"
}

demo() {
    echo ">>> Starting demo..."
    clean_mail
    echo ">>> Wait 5s for monitor..."
    sleep 5
    echo ">>> Stopping web_server..."
    docker compose stop web_server
    sleep 12
    echo ">>> Checking mail:"
    check_mail | head -30
    echo ">>> Restoring web_server..."
    docker compose start web_server
    echo ">>> Demo: done"
}

help() {
    cat << 'EOF'
lab.sh — минималистичный менеджер лабы

Использование: ./lab.sh <command>

Команды:
  setup       SSH-ключи + SSL + аккаунты
  up/down/restart/status/logs  docker compose wrapper
  check-mail  показать все письма (расшифровано)
  clean-mail  очистить ящик
  send-test   отправить тестовое письмо
  ssh         подключиться по SSH
  web         открыть дашборд в браузере
  demo        полная демонстрация инцидента
  help        эта справка
EOF
}

case "${1:-help}" in
    setup) setup ;; up) up ;; down) down ;; restart) restart ;;
    status) status ;; logs) logs "${2:-}" ;; check-mail) check_mail ;;
    clean-mail) clean_mail ;; send-test) send_test ;; ssh) ssh_conn ;;
    web) web ;; demo) demo ;; help|--help|-h) help ;;
    *) echo "Unknown: $1"; help; exit 1 ;;
esac