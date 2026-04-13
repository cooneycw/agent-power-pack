# Security Policy

## Reporting a vulnerability

If you discover a security vulnerability in agent-power-pack, please
report it responsibly.

**Email**: <cooneycw@gmail.com>

Please include:

- A description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if you have one)

We will acknowledge receipt within 48 hours and aim to provide a fix
or mitigation within 7 days for critical issues.

**Do not** open a public GitHub issue for security vulnerabilities.

## Tiered secrets layer

agent-power-pack uses a tiered secrets architecture to manage
credentials securely:

| Tier | Backend | Use case |
|------|---------|----------|
| **dotenv** | `.env` file | Local development (default) |
| **env-file** | Docker `env_file` | Container environments |
| **aws** | AWS Secrets Manager via [`aws-secretsmanager-agent`](https://github.com/awslabs/aws-secretsmanager-agent) sidecar | Production |

Secrets are resolved in order (dotenv -> env-file -> aws); the first
tier with a value wins. Writes default to the dotenv tier.

### Security guarantees

- `.env` files are always in `.gitignore` — the validator checks this.
- Secrets are never logged, echoed, or written to tracked files.
- The AWS sidecar runs as a separate container on port 2773, accessed
  only from the local Docker network.
- `/security:scan` and `/security:quick` check for hardcoded secrets
  in code and git history.

## Supported versions

Only the latest release is supported with security updates. This
project is pre-1.0 and the API is not yet stable.

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |
| < 0.1   | No        |
