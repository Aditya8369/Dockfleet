# Security Policy

## Supported Versions

We currently support the latest minor release of the project for security updates:

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

If you believe you have found a security vulnerability in this project, please report it privately via the [GitHub Security Advisories](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing/privately-reporting-a-security-vulnerability) feature or by contacting the maintainers directly.

### Scope and Threat Model

DockFleet is designed as a **local, offline container orchestrator**. It does not expose external APIs over the public internet by default. Security reports should focus on vulnerabilities within this context, such as:
* Privilege escalation via the CLI tool.
* Arbitrary code execution or path traversal via maliciously crafted `dockfleet.yaml` files.
* Local network vulnerabilities exposed by the monitoring dashboard.

### Out of Scope Vulnerabilities

When reporting vulnerabilities, please consider the actual security impact. The following issues are generally considered out of scope:
* Vulnerabilities in the underlying Docker engine or SQLite database itself.
* Attacks requiring physical access to the host machine or pre-existing root access.
* Lack of SSL/TLS on the dashboard API (as it is intended for local network use on `localhost`).
* Social engineering attacks.
