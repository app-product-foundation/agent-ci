## Focus: security

Report only high-confidence, exploitable vulnerabilities that this pull request introduces or
makes reachable:

- Authentication and session handling
- Authorization and IDOR: reads or writes that are not scoped to the caller
- Injection (SQL, NoSQL, command, template, header, path traversal)
- SSRF and open redirects
- Secrets in code, configuration or logs, and personal data written to logs
- IAM, infrastructure and CI exposure: over-broad roles or policies, public resources, and
  workflow changes that hand secrets or write tokens to untrusted code

For each finding, describe how an attacker reaches it and what they gain. Skip style, theoretical
issues without a reachable path, missing hardening that is not exploitable, and denial of service.
