# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.6.x   | Yes |
| < 0.6   | No |

**0.6.x is stable for Tier 1.** Security fixes, if needed, land on the `dev` branch and ship in a 0.6.x patch.

## Reporting a vulnerability

**Do not** open a public issue with a working exploit, credentials, or private user data.

1. Prefer [GitHub private vulnerability reporting](https://github.com/Taha-azizi/contextpress/security/advisories/new) if it is enabled on the repository.
2. Otherwise email the maintainer via the address on [GitHub](https://github.com/Taha-azizi) with:
   - Affected version (`pip show contextpress`)
   - A short description of the impact
   - Steps that are enough to **understand** the issue (not a full weaponized PoC)

You should hear back within **14 days**. If we confirm a vulnerability, we will patch on `dev`, cut a 0.6.x release, and credit you if you want to be named.

contextpress does not call cloud APIs in Tier 1. Treat **Tier 2** backends (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`) as secrets — never commit them. See `.env.example`.
