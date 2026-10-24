# Plan: protect the BWS access token with SOPS + age

Status: proposed; no credentials, keys, or deployment settings changed.

## Goal and current state

Encrypt the Bitwarden Secrets Manager (`bws`) machine-account access token
at rest with SOPS, using age recipients. Decrypt it only when a host-side
operation needs to fetch secrets from Bitwarden.

Repository observations:

- `bootstrap.enc.env` exists locally and is untracked. It has SOPS metadata
  and one age recipient, but `BWS_ACCESS_TOKEN` is empty. Treat it as an
  unfinished bootstrap file, not a working credential.
- No BWS wrapper or `.sops.yaml` is present. `bws`, `sops`, and `age` were
  not found on the inspection shell's PATH.
- Compose currently reads application secrets from the ignored `.env` file.
  Securing the BWS token alone will not encrypt those application secrets.
- `.env` is ignored; age private keys and decrypted bootstrap files need
  explicit protection too.

## Intended design

```text
Host-only age private key + bootstrap.enc.env (encrypted token)
                         |
                  SOPS decryption
                         |
           BWS_ACCESS_TOKEN in short-lived child environment
                         |
             bws -> permitted Bitwarden project secrets
```

Commit `.sops.yaml`, the encrypted bootstrap file, and a small host-side
wrapper. Store private keys outside the checkout. Neither the age key nor
the BWS token belongs in application containers, images, Compose settings,
frontend variables, or CI logs.

This protects the token in Git and in copies of the ciphertext. A process
running as the key owner, or root on the host, can still decrypt it. A local
age key enables unattended use but does not protect against host compromise.
Use a dedicated deployment account with restricted access; Docker access
itself is effectively privileged.

## Implementation steps

### 1. Establish the account and recovery path

- Create a dedicated Bitwarden machine account for this deployment. Grant
  read-only access to only the required project/secrets; use separate
  accounts and tokens for other environments.
- Record the account owner, required secret IDs, server/region, token
  expiration, and rotation owner without recording secret values in Git.
- Decide who can recover access. Use one host age identity and a separate
  offline recovery identity. Keep the recovery private key in protected
  storage independent of this host and its backups.
- Keep the existing deployment working during bootstrap. Do not replace
  `.env` or change the initialized PostgreSQL password.

### 2. Install tools and provision age identities

- Install supported, pinned releases of BWS CLI, SOPS, and age from their
  official distributions; verify release integrity and record versions.
- As the deployment account, generate a new host age identity with
  `umask 077`. Store it outside the repository, for example at
  `~/.config/budget-tracking/age/keys.txt`; use directory mode `0700` and
  key-file mode `0600`. Check inherited ACLs as well as Unix modes.
- Set `SOPS_AGE_KEY_FILE` explicitly in the wrapper or service environment.
  It contains a path, not the private key itself.
- Generate the recovery identity separately. Only its public recipient
  should reach the server. Verify possession of the private key for any
  existing recipient before retaining it; an unknown recipient must not
  receive the real token.

### 3. Define the encrypted file and repository policy

Add `.sops.yaml` with an exact path rule and the two verified public
recipients. Example template (replace placeholders before use):

```yaml
creation_rules:
  - path_regex: ^bootstrap\.enc\.env$
    age: >-
      <HOST_AGE_PUBLIC_RECIPIENT>,
      <RECOVERY_AGE_PUBLIC_RECIPIENT>
```

- Keep dotenv format for `bootstrap.enc.env`; explicitly select dotenv
  input/output types when creating it. Verify the chosen SOPS version's
  handling of the `.enc.env` filename.
- The only payload field should be `BWS_ACCESS_TOKEN`, with a nonempty
  `ENC[...]` value once provisioned. Keep SOPS integrity checking enabled.
- Add ignore patterns for local age keys, plaintext bootstrap files, editor
  backups, and temporary secret exports. Do not ignore the encrypted file.
- Add a CI check using dummy data or metadata inspection: ensure the
  committed token field is encrypted and nonempty, and reject private-key
  material or plaintext tokens. CI must not receive production decryption
  keys. Never use production values as test fixtures.

### 4. Enroll the token without persistent plaintext

- Obtain the dedicated machine-account token through Bitwarden's supported
  flow. Enter it through a hidden prompt in a small enrollment helper.
- Pass it directly to SOPS through standard input; do not place it in shell
  arguments, command history, terminal output, or a plaintext temporary file.
  Disable shell tracing before reading it.
- Write encryption output to a restrictive temporary ciphertext file,
  validate it, then atomically replace `bootstrap.enc.env`. Preserve the
  existing local file until its recipient ownership is understood.
- Test decryption with both the host and recovery identities, checking only
  success and nonempty output. Do not print the token.
- Review the encrypted diff and stage only named files. If a real token was
  previously exposed in Git, logs, or history, revoke it; encryption does
  not undo exposure.

### 5. Add a narrowly scoped runtime wrapper

Create `scripts/bws-secure` with this contract:

- Resolve the repository/file paths reliably; require the configured age
  key, SOPS, and BWS CLI before attempting a fetch.
- Decrypt and parse the single expected dotenv field as data. Do not
  `source` or `eval` decrypted content. Validate the key name and nonempty
  token and reject unexpected fields or malformed data.
- Use a small helper with a process API to supply `BWS_ACCESS_TOKEN` only
  to the BWS child environment. Do not export it into the caller's shell,
  pass it as a CLI argument, or interpolate it into shell command text.
- Clear inherited BWS authentication overrides, select the intended
  Bitwarden endpoint explicitly, and invoke a fixed BWS executable with
  argument arrays. Confirm exact CLI options against the pinned version.
- Disable tracing and suppress secret-bearing diagnostics. Keep failure
  messages useful without including decrypted input or CLI response bodies.
- Preserve child exit status, handle interruption, and avoid decrypted
  files. Process memory/environment exposure lasts for the operation;
  language-level cleanup is not guaranteed secure memory erasure.
- Start with one fixed read operation against an allowlisted secret ID.
  Any command that returns a secret must send it directly to its intended
  consumer, never to routine logs or the terminal.

Do not use a generic SOPS environment-loading command without first proving
that its dotenv parsing matches this file format. Do not log full BWS JSON
responses: they can contain secret values.

### 6. Integrate with deployment in a separate step

The initial deliverable secures and verifies BWS authentication. Keep the
existing `.env` deployment path until a secret-consumption workflow is
explicitly implemented and tested.

If BWS will supply application secrets, add a fixed mapping from secret IDs
to expected variables and validate all results before changing deployment
state. Review `DEPLOY_UBUNTU.md` and `SCHEMA.md` before that integration.
Choose either a protected generated env file or a deployment process that
passes values in memory, documenting the remaining plaintext exposure.
Compose/container environments remain inspectable by privileged operators.
Never print resolved `docker compose config` output containing real secrets.
Keep `dev-secret` defaults and ordinary development/CI workflows unchanged.

## Verification and acceptance criteria

Use dummy credentials and a stub BWS executable first; then perform a single
authorized read against the intended Bitwarden project.

- [ ] Both intended recipients decrypt successfully; an unrelated identity
      and a missing key fail without invoking BWS.
- [ ] Empty token, malformed file, and tampered ciphertext fail closed.
- [ ] BWS receives the token through its child environment only; the parent
      shell and application containers do not receive it.
- [ ] Authentication failure, access denial, network failure, and interruption
      return failure without replacing working deployment configuration.
- [ ] Test stdout/stderr, process arguments, and filesystem artifacts contain
      no dummy token or returned secret, except the intended consumer input.
- [ ] Host key permissions and ACLs are restricted; no private keys or
      plaintext bootstrap files are tracked or included in ordinary backups.
- [ ] Live verification reports success without printing secret values.
- [ ] Recovery is tested from a separate environment using the recovery key.

## Rotation, revocation, and recovery

**BWS token:** issue a replacement with the same minimal permissions,
encrypt it atomically, and verify a permitted read. Revoke the old token
and verify it no longer works. Track expiry and schedule rotation before it.
On suspected compromise, revoke immediately, then restore access; rotate
downstream secrets the account could read when warranted.

**Age recipients:** add the new public recipient and run SOPS recipient
updates, verify recovery, then remove retired recipients. When a private
key may be compromised, rotate the BWS token and re-encrypt with a fresh
SOPS data key for the remaining recipients. Removing a recipient alone
cannot invalidate old ciphertext or data keys already obtained.

**Lost host:** recover using the offline identity, provision a new host
identity, and update recipients. Revoke the old BWS token if the old host
is not trusted. Keep ciphertext backups and private-key backups separate.
Recovery of BWS access must not depend solely on secrets locked behind BWS.

**Rollback:** retain the currently working deployment during rollout. A
failed BWS fetch should stop the update while running containers continue.
Restore known-good ciphertext only if its token is still valid and trusted;
never restore a revoked token or copy plaintext credentials into Git.

## Planned files

| File | Purpose |
|------|---------|
| `.sops.yaml` | Exact bootstrap path rule and public age recipients |
| `bootstrap.enc.env` | Nonempty encrypted BWS token and SOPS metadata |
| `scripts/bws-secure` | Restricted host-side decryption and BWS invocation |
| `.gitignore` | Exclude local keys and plaintext artifacts |
| Wrapper checks / CI check | Dummy-token failure cases and repository policy |
| `docs/DEPLOY_UBUNTU.md` | Enrollment, usage, rotation, and recovery instructions |

Implementation can proceed in that order. No application changes, database
migrations, token issuance, or credential rotation are part of this planning
change.
