# Security Policy

## Supported Versions

| Version | Supported |
| ------- | --------- |
| 1.0.x   | Yes       |
| < 1.0   | No        |

Beta pre-releases (`-beta.N`) are not recommended for compliance-sensitive workflows.

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Report through either of these channels:

1. **GitHub Private Vulnerability Reporting** (preferred) — Submit a private report via the [Security Advisories](https://github.com/infab-app/airgap-fusion/security/advisories/new) page.
2. **Email** — Send a report to **support@infab.app** with the subject line: `AirGap Fusion Security Report: [brief description]`

Please include:

- Description of the vulnerability
- Steps to reproduce
- Affected version(s)
- Potential impact assessment

**Response timeline:**

- Acknowledgment within **48 hours**
- Initial assessment within **7 days**
- Fixes will be released before public disclosure where possible

Reporters will be credited in the release notes unless they prefer to remain anonymous.

**Scope note:** Vulnerabilities in Autodesk Fusion 360 itself should be reported to Autodesk's security team. If a Fusion 360 behavior undermines AirGap's controls, we appreciate being informed.

### Known limitations

- **No code signing** — Release artifacts are not GPG-signed. The `SHA256SUMS` file is hosted on the same GitHub Release as the ZIP. An attacker who compromises the GitHub repository or release could replace both simultaneously. SHA-256 verification protects against download corruption but not against a compromised release.
- **No certificate pinning** — AirGap relies on the system's default TLS certificate store.
- **No automatic retry** — Failed update checks return silently without retrying.
