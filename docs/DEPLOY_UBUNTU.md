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

## 4. Configure production secrets with Bitwarden

Install the [Bitwarden Secrets Manager CLI (`bws`)](https://bitwarden.com/help/secrets-manager-cli/),
[SOPS](https://github.com/getsops/sops), and
[age](https://github.com/FiloSottile/age) on the server.

In Bitwarden Secrets Manager, create a project for this deployment and add
these secrets. Their names must match exactly because `bws run` exports them
as environment variables:

| Secret | Value |
|---|---|
| `POSTGRES_PASSWORD` | `openssl rand -hex 32` |
| `BUDGET_JWT_SECRET` | a separate `openssl rand -hex 32` value |

Create a machine account with read access only to that project and generate
an access token. The application secrets stay in Bitwarden; the access token
is the only bootstrap secret stored on the server.

Generate an age identity as the deployment user (not with `sudo`):

```bash
umask 077
mkdir -p "$HOME/.config/sops/age" secrets
age-keygen -o "$HOME/.config/sops/age/keys.txt"
age-keygen -y "$HOME/.config/sops/age/keys.txt"
```

Copy the `age1...` recipient printed by the final command. Create `.sops.yaml`
in the repository, replacing the example recipient:

```yaml
creation_rules:
  - path_regex: secrets/.*\.env$
    age: age1REPLACE_WITH_YOUR_PUBLIC_RECIPIENT
```

Create and immediately encrypt the bootstrap file. Paste the Bitwarden
machine access token when prompted:

```bash
read -rsp 'Bitwarden access token: ' BWS_ACCESS_TOKEN; echo
printf 'BWS_ACCESS_TOKEN=%s\n' "$BWS_ACCESS_TOKEN" > secrets/bws-access-token.enc.env
unset BWS_ACCESS_TOKEN
sops --encrypt --in-place secrets/bws-access-token.enc.env
```

Confirm that the file contains `ENC[...]`, not the plaintext token. Back up
the age identity separately with restrictive permissions; never commit it.
The encrypted file and `.sops.yaml` may be committed because they contain
only ciphertext and the public recipient.

Keep non-secret Compose settings in `.env`:

```dotenv
POSTGRES_USER=budget
POSTGRES_DB=budget
BUDGET_ENVIRONMENT=production
BUDGET_SEED_USERS=
```

If using published images, put `BUDGET_IMAGE_TAG` there too. Do not put
`POSTGRES_PASSWORD`, `BUDGET_JWT_SECRET`, or `BWS_ACCESS_TOKEN` in `.env`.
Registration creates the household accounts, so seed passwords are
unnecessary.

Production mode rejects placeholder database passwords and JWT secrets
shorter than 32 bytes. Hexadecimal database passwords also avoid URL-escaping
issues in the Compose connection string. For an existing installation, copy
its current database password into Bitwarden: changing the Bitwarden value
does not change the password inside an initialized PostgreSQL volume.

## 5. Build, start, and verify locally

From `~/apps/budget-tracking`:

```bash
sops exec-env secrets/bws-access-token.enc.env \
  'bws run -- sudo --preserve-env=POSTGRES_PASSWORD,BUDGET_JWT_SECRET docker compose up -d --build'
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
protected second machine or backup destination. Back up the age identity
separately so a replacement server can decrypt the Bitwarden bootstrap token;
the encrypted file alone is not sufficient for recovery.
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
sops exec-env secrets/bws-access-token.enc.env \
  'bws run -- sudo --preserve-env=POSTGRES_PASSWORD,BUDGET_JWT_SECRET docker compose up -d --build'
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
them again with the SOPS/Bitwarden-wrapped `docker compose up -d` command
shown above.

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
sops exec-env secrets/bws-access-token.enc.env \
  'bws run -- sudo --preserve-env=POSTGRES_PASSWORD,BUDGET_JWT_SECRET docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d'
sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

This route uses matching API and web image tags and forces production mode.
Continue using host Tailscale Serve exactly as described above.

## Troubleshooting

- Local health fails: inspect `sudo docker compose logs --tail 100 api postgres web`.
  A secret-validation error usually means a Bitwarden secret is missing,
  misnamed, or shorter than 32 bytes.
- `bws` reports that it is unauthorized: run
  `sops exec-env secrets/bws-access-token.enc.env 'bws project list'`, then
  check
  that the machine account and its project read access are still active.
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
