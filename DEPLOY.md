# Deploying TOLK on AWS EC2

One server runs everything with Docker Compose: **Caddy** (HTTPS) → **web** (FastAPI) + **bot** (Telegram) + **db** (PostgreSQL).
Telegram Mini Apps require HTTPS on a real domain, so you need a domain name (e.g. `tolk.uz` or `app.tolk.uz`).

## 1. Before you start

- **Telegram bot**: in [@BotFather](https://t.me/BotFather) send `/newbot`, keep the **token** and the **username**.
- **Your Telegram user ID** (for admin access): send any message to [@userinfobot](https://t.me/userinfobot).
- **A domain** where you can add DNS records.

## 2. Create the server

1. EC2 → Launch instance:
   - **Ubuntu Server 24.04 LTS**, type **t3.small** (2 GB RAM; t3.micro works for a pilot if you add swap), 20 GB gp3 disk.
   - Security group inbound rules: **22** (SSH, only your IP), **80** and **443** (HTTP/HTTPS, anywhere).
2. EC2 → Elastic IPs → allocate one and associate it with the instance (so the IP never changes).
3. At your DNS provider add an **A record**: `tolk.example.uz → <elastic IP>`. Wait until `ping tolk.example.uz` shows that IP.

## 3. Install Docker

```bash
ssh ubuntu@<elastic IP>
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu && exit   # log out and back in so the group applies
```

Optional, for 1 GB instances only:

```bash
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

## 4. Get the code and configure

```bash
git clone https://github.com/thealiiheere/TOLK.git && cd TOLK
cp .env.example .env
nano .env
```

Fill in at least: `DOMAIN`, `TOLK_WEBAPP_URL` (`https://` + domain), `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME`,
`ADMIN_TELEGRAM_IDS`, `POSTGRES_PASSWORD` (letters and digits only), `PAYMENT_CARD_NUMBER`, `PAYMENT_CARD_HOLDER`, `SUPPORT_CONTACT`.
Keep `DEMO_MODE=false` for real users.

## 5. Start

```bash
docker compose up -d --build
docker compose ps            # all services should be "running" / "healthy"
docker compose logs -f web   # migrations + startup; CONFIG warnings show missing settings
```

Open `https://<your domain>/health` → `{"status":"ok"}`. The first HTTPS request can take a few seconds while Caddy gets the certificate.

## 6. Connect Telegram

- The bot sets its **menu button** (opens the Mini App) by itself when it starts. Send `/start` to your bot to test.
- For sign-in from a normal browser (Telegram Login Widget): in @BotFather send `/setdomain`, pick the bot, enter your domain.
- Optional: `/newapp` in @BotFather creates a direct link like `t.me/your_bot/app`.

The people listed in `ADMIN_TELEGRAM_IDS` become admins the first time they open the app.
Teachers sign up themselves ("I'm a teacher") and appear in **Admin → Teachers** for approval.

## Updating to a new version

```bash
cd TOLK && git pull
docker compose up -d --build   # migrations run automatically on start
```

## Backups

Database (run daily via `crontab -e`):

```bash
0 3 * * * cd /home/ubuntu/TOLK && docker compose exec -T db pg_dump -U tolk tolk | gzip > /home/ubuntu/backups/tolk-$(date +\%F).sql.gz
```

Receipts live in the `uploads` volume: `docker run --rm -v tolk_uploads:/u -v $PWD:/b alpine tar czf /b/uploads.tgz -C /u .`
(the volume name is `<folder>_uploads`; check with `docker volume ls`). Copy backups off the server (e.g. to S3).

Restore a database dump: `gunzip -c dump.sql.gz | docker compose exec -T db psql -U tolk tolk`.

## Troubleshooting

| Symptom | Check |
|---|---|
| Site doesn't open / certificate error | DNS A record points at the Elastic IP; ports 80/443 open; `docker compose logs caddy` |
| "Telegram sign-in data could not be verified" | `TELEGRAM_BOT_TOKEN` belongs to the bot you open the app from |
| Bot doesn't answer `/start` | `docker compose logs bot`; only one process may poll a bot token (stop any old local bot) |
| Login widget says "Bot domain invalid" | `/setdomain` in @BotFather |
| No Telegram notifications | Users must have pressed **Start** in the bot at least once |
| `web` keeps restarting | `docker compose logs web` (usually a wrong `POSTGRES_PASSWORD` after the DB volume was created with another one) |
