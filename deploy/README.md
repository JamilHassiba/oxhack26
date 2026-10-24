# Vultr deployment (Evan)

No Docker. Ubuntu VM → systemd/uvicorn on localhost:8000 → Caddy HTTPS, static Vite build, `/api` prefix stripped. SSE uses `flush_interval -1` ([Caddy reference](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy#streaming)).

## External setup still needed

There is no VM or domain yet. Create an Ubuntu 24.04 VM in Vultr, add your SSH public key, and point a domain's A record at it (and AAAA only if the VM has working IPv6). Allow SSH from your network and public TCP 80/443 in the Vultr firewall. Do not expose port 8000. Provisioning requires your Vultr account and billing; these files do not create or purchase resources.

For an initial hello-world without a domain, use `SITE_ADDRESS=:80` and the VM's HTTP address. ElevenLabs integration requires the real HTTPS domain afterwards.

## First deployment

1. SSH into the VM and clone this repository to a checkout such as `/root/oxhack26`. Fetch the desired branch. The checkout itself never serves requests.
2. Review and run `sudo bash deploy/bootstrap.sh`. It installs Caddy, Python, and a private Node 24 LTS distribution with its official SHA-256 verified.
3. Copy `deploy/api.env.example` and `deploy/caddy.env.example` to `/etc/concierge/api.env` and `/etc/concierge/caddy.env`. Set ownership `root:concierge`, permissions `0640`. Fill in the domain, database URL, and provider values. Never commit these files. `EMAIL_FROM` must be a sender on your verified Resend domain.
4. For the initial HTTP smoke app, leave `BACKEND_APP=app.evan.app:app` and run `sudo DEPLOY_REQUIRE_DB=0 bash deploy/deploy.sh YOUR_COMMIT_SHA`. It serves `/api/health` and Evan's routes, but does not pretend to provide Alex's chat or Jamil's voice endpoints.
5. Once Jamil's base migration is ready, run his migration runner, then `backend/migrations/100_evan_agent_archival_email.sql` once against that database. See `backend/EVAN_INTEGRATION.md`. Migrations are deliberately a separate explicit step because Jamil owns their ordering and runner.
6. Once Alex's app is merged, register Evan's routers with the two lines in `backend/EVAN_INTEGRATION.md`, set `BACKEND_APP=app.main:app`, and deploy with the default database health requirement: `sudo bash deploy/deploy.sh YOUR_COMMIT_SHA`.

The script builds the production frontend with `VITE_DEMO_MODE=false`, creates a separate release/virtualenv, validates Caddy before switching, then atomically switches `/opt/concierge/current`. Build failures leave the current release running. Failed backend/database health restores the prior release. Old releases remain for manual rollback. Schema migrations are not automatically rolled back.

## Verify and operate

- `curl --fail https://YOUR_DOMAIN/api/health` and confirm `db: "ok"` on the integrated deployment.
- Refresh `/chat` and `/history`; both should serve the SPA.
- Confirm `/api` is routed to FastAPI and errors stay JSON, rather than returning index.html.
- Test a call's event stream with `curl -N https://YOUR_DOMAIN/api/calls/CALL_ID/events/stream`; frames should arrive without buffering.
- `sudo journalctl -u oxhack-api -f` and `sudo journalctl -u caddy -f` show service logs. Do not paste secrets from configuration files into logs or chat.
- Manual rollback: point `/opt/concierge/current` at a previous release and restart `oxhack-api`; reload Caddy.

The app is the plan's single-user demo. Put it behind an access gate before storing personal data for multiple users. Production tests and three rehearsals remain pending the VM, domain, shared DB, chat, and voice integrations.
