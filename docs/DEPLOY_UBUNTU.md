# Ubuntu deployment draft: Docker Compose + host Tailscale Serve

This guide assumes Ubuntu Server 24.04 LTS, a user with sudo access, and
one server for the household. Run the commands on that server. Docker
builds the app; Python and Node do not need to be installed on the host.

The request path is:

```text
Household device on Tailscale
  -> https://<server>.<tailnet>.ts.net
  -> Tailscale Serve on the Ubuntu host (TLS termination)
  -> http://127.0.0.1:8080 (nginx)
  -> FastAPI -> PostgreSQL
```

The existing Compose file already binds web port 8080 and PostgreSQL port
5432 to loopback. Keep those bindings. Host Tailscale handles HTTPS and
certificate renewal; the app containers use HTTP internally. This path
uses the default Compose services, with the optional `tailscale` profile
left disabled. `TS_AUTHKEY` and `TS_HOSTNAME` in `.env` are for that optional
sidecar, not for the host installation.

## 1. Install Docker and supporting tools

For a fresh Ubuntu server, configure Docker's official package repository:

```bash
sudo apt update
sudo apt install -y ca-certificates curl git openssl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

sudo tee /etc/apt/sources.list.d/docker.sources > /dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo docker compose version
```

If Docker is already installed, check its installation before replacing
packages. See [Docker's Ubuntu installation instructions](https://docs.docker.com/engine/install/ubuntu/).
This guide uses `sudo docker` consistently, so adding your user to the
Docker group is optional.

## 2. Install Tailscale on the host

Skip installation if Tailscale already runs on the server. Otherwise,
download and inspect the official installer, then run it:

```bash
curl -fsSL https://tailscale.com/install.sh -o /tmp/tailscale-install.sh
less /tmp/tailscale-install.sh
sudo sh /tmp/tailscale-install.sh
sudo systemctl enable --now tailscaled
sudo tailscale up
sudo tailscale status
```

Open the authentication URL printed by `tailscale up` and join the same
tailnet as the household devices. Use the server's existing Tailscale
hostname, or rename the device in the Tailscale admin console.
See [Tailscale's Linux installation guide](https://tailscale.com/docs/install/linux).

## 3. Get the application code

```bash
mkdir -p "$HOME/apps"
cd "$HOME/apps"
git clone https://github.com/AruanSec/budget-tracking.git
cd budget-tracking
git rev-parse HEAD
```

If the repository is private, authenticate with GitHub using your SSH key
or your usual Git credential helper.

Deploy the commit containing the changes you intend to run. Cloning only
retrieves committed, pushed code; local uncommitted changes on your
workstation must first be committed and pushed, or transferred separately.
Keep this directory name and location stable so subsequent Compose commands
continue using the same project and PostgreSQL volume.

## 4. Configure production settings and secrets

Store deployment configuration and secrets in `.env` in the repository root
on the server. For a new deployment:

```bash
umask 077
cp .env.example .env
chmod 600 .env
nano .env
```

Generate two independent values by running this command twice:

```bash
openssl rand -hex 32
```

Put one value in `POSTGRES_PASSWORD` and the other in `BUDGET_JWT_SECRET`.
The relevant `.env` settings should look like this, with both placeholders
replaced by the generated values:

```dotenv
POSTGRES_USER=budget
POSTGRES_PASSWORD=REPLACE_WITH_DATABASE_PASSWORD
POSTGRES_DB=budget
BUDGET_JWT_SECRET=REPLACE_WITH_SEPARATE_JWT_SECRET
BUDGET_ENVIRONMENT=production
BUDGET_SEED_USERS=
```

If using published images, put `BUDGET_IMAGE_TAG` there too. Registration
creates the household accounts, so seed passwords are unnecessary.
Compose reads `.env` automatically when run from the repository root;
you do not need to source it or export the secrets manually.

Keep `.env` private, never commit it, and back it up in a protected location.
The repository already ignores `.env`.

Production mode rejects placeholder database passwords and JWT secrets
shorter than 32 bytes. Hexadecimal database passwords also avoid URL-escaping
issues in the Compose connection string. For an existing installation, edit
its existing `.env` rather than overwriting it, and retain the current
database password: changing the value in `.env` does not change the password
inside an initialized PostgreSQL volume. Rotating the JWT secret signs
users out.

## 5. Build, start, and verify locally

From `~/apps/budget-tracking`:

```bash
sudo docker compose up -d --build
sudo docker compose ps
sudo docker compose logs --tail 50 api
curl --fail http://127.0.0.1:8080/api/health
```

Expect `{"status":"ok"}`. On first startup, migrations run automatically
before the API begins serving. A brief 502 during startup can occur; retry
after the migration logs show completion. PostgreSQL should be healthy,
and both web and API containers should be running.

## 6. Enable private HTTPS with Tailscale Serve

```bash
sudo tailscale serve --bg --https=443 http://127.0.0.1:8080
sudo tailscale serve status
```

If prompted, follow Tailscale's link to enable HTTPS for your tailnet and
approve the required setup. The command prints the actual HTTPS URL;
use that URL rather than guessing the tailnet suffix. Tailscale manages
the TLS certificate. Background mode persists across reboot or Tailscale
restart. See the [Serve CLI reference](https://tailscale.com/docs/reference/tailscale-cli/serve)
and [Serve setup guide](https://tailscale.com/docs/features/tailscale-serve).

From a household device connected to Tailscale, open the printed URL and
check `/api/health`. Tailnet access policy must allow that device to reach
the server on TCP 443. Serve provides private tailnet access; keep this
household deployment on Serve rather than enabling public Funnel access.

There is no need to open public ports 80, 443, 8080, or 5432 for this app,
configure public DNS, or install Certbot. Preserve your existing SSH access
and server firewall configuration.

Register your own account first at `/register`; it becomes the admin on a
fresh database. Other household members can then register. Each member
needs both Tailscale connectivity and an app login.

## 7. Back up before regular use and updates

Create a custom-format PostgreSQL dump from the app directory:

```bash
umask 077
mkdir -p backups
budget_backup_file="backups/budget-$(date +%Y%m%d-%H%M%S).dump"
sudo docker compose exec -T postgres pg_dump -U budget -d budget -Fc > "$budget_backup_file"
test -s "$budget_backup_file"
printf 'Backup saved to %s\n' "$budget_backup_file"
```

The dump contains household accounts and financial history. Copy it to a
protected second machine or backup destination. Back up `.env` separately
in a protected location so a replacement server has the database password
and JWT secret needed to recreate the deployment.
Use the credentials above only if you retained `POSTGRES_USER=budget` and
`POSTGRES_DB=budget`.

To test restoration, choose a fresh scratch database name and an existing
dump file. This test does not restore over the live `budget` database:

```bash
budget_restore_file="backups/REPLACE-WITH-YOUR-BACKUP.dump"
sudo docker compose exec -T postgres psql -U budget -d postgres -c 'CREATE DATABASE budget_restore_check;'
sudo docker compose exec -T postgres pg_restore -U budget --no-owner --exit-on-error -d budget_restore_check < "$budget_restore_file"
sudo docker compose exec -T postgres psql -U budget -d budget_restore_check -c 'SELECT count(*) FROM users; SELECT count(*) FROM transactions;'
```

Replace the filename and verify the restored counts against the source.
For repeated tests, use a new scratch database name. Establish a scheduled
off-server backup process before relying on the app daily; these commands
are manual backup and verification steps.

## 8. Updates and reboot behavior

Make and copy a backup before updating, then:

```bash
cd "$HOME/apps/budget-tracking"
git pull --ff-only
sudo docker compose up -d --build
sudo docker compose logs --tail 50 api
curl --fail http://127.0.0.1:8080/api/health
sudo tailscale serve status
```

The API applies new migrations on startup. Code rollback alone may be
insufficient after a schema change; retain the previous commit and its
pre-update backup. Restore into a separate database before switching a
production installation back.

Docker and tailscaled are enabled at boot. Compose's `unless-stopped`
restart policy restarts running services after reboot, and Serve's `--bg`
configuration persists. Manually stopped containers remain stopped; start
them again with `sudo docker compose up -d` from the repository root.

`sudo docker compose down` stops the app while preserving the PostgreSQL
volume. The `-v` option removes volumes and must not be used for routine
updates or restarts.

## Optional: use published images

After CI and the Docker Publish workflow have successfully published both
images for a commit, set this in `.env`:

```dotenv
BUDGET_IMAGE_TAG=sha-<full-commit-sha>
```

For private GHCR packages, authenticate interactively with
`sudo docker login ghcr.io -u YOUR_GITHUB_USERNAME`, using a token with
package-read permission when prompted. Then use the same Compose files
for every start, update, and status command:

```bash
sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml pull
sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

This route uses matching API and web image tags and forces production mode.
Continue using host Tailscale Serve exactly as described above.

## Troubleshooting

- Local health fails: inspect `sudo docker compose logs --tail 100 api postgres web`.
  A secret-validation error usually means a secret in `.env` is missing,
  still a placeholder, or shorter than 32 bytes. Check that `.env` is in the
  repository root and run Compose from that directory.
- Database authentication fails: check the credentials used when the volume
  was initialized. Preserve the volume and reconcile the password; deleting
  the volume would delete household data.
- Local health works but HTTPS fails: check `sudo tailscale status`,
  `sudo tailscale serve status`, the client device's connection, and tailnet
  access policy. Use the hostname printed by Serve, not the public IP.
- HTTPS port 443 already serves another app: inspect existing Serve settings
  before changing them. An alternative is
  `sudo tailscale serve --bg --https=8443 http://127.0.0.1:8080`;
  use the printed URL including `:8443` and allow that port in tailnet policy.
