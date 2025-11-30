# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.2.x   | :white_check_mark: |
| 1.1.x   | :white_check_mark: |
| < 1.1   | :x:                |

We recommend always using the latest version for the best security.

---

## Reporting a Vulnerability

**⚠️ IMPORTANT: Do NOT create public GitHub issues for security vulnerabilities.**

### Preferred Method: GitHub Security Advisories

1. Go to the repository's **Security** tab
2. Click **"Report a vulnerability"**
3. Fill out the form with details about the vulnerability

This ensures the vulnerability is handled privately until a fix is released.

### Alternative: Email

If you cannot use GitHub Security Advisories, contact the maintainer directly. Include:

- **Subject**: `[SECURITY] Brief description`
- **Description**: Detailed explanation of the vulnerability
- **Steps to Reproduce**: How to trigger the vulnerability
- **Impact Assessment**: Potential impact and severity
- **Suggested Fix**: If you have one (optional)

### Response Timeline

| Stage | Timeframe |
|-------|-----------|
| Initial Response | Within 48 hours |
| Vulnerability Confirmation | Within 7 days |
| Patch Development | Varies by severity |
| Security Advisory Published | Upon fix release |

---

## What to Include in Your Report

### Required Information

1. **Vulnerability Type**: (e.g., path traversal, injection, DoS)
2. **Affected Component**: Which module/file is affected
3. **Affected Versions**: Which versions contain the vulnerability
4. **Steps to Reproduce**: Minimal steps to demonstrate the issue
5. **Proof of Concept**: Code or commands (if safe to share)

### Helpful Information

- CVSS score estimate
- CVE references (if known)
- Suggested mitigation
- Whether you want credit in the advisory

---

## Scope

### In Scope

The following are considered valid security concerns:

- **Path traversal attacks** (tarfile extraction, file paths)
- **Remote code execution** (command injection, unsafe deserialization)
- **Denial of service** (resource exhaustion, infinite loops)
- **Information disclosure** (log leakage, credential exposure)
- **Dependency vulnerabilities** (with proof of exploitability)
- **Authentication/Authorization bypasses** (if applicable)
- **Symlink attacks** (in file extraction or handling)

### Out of Scope

The following are NOT considered security vulnerabilities:

- Vulnerabilities in dependencies without proof of exploitation
- Issues requiring physical access to the machine
- Social engineering attacks
- Spam or phishing attacks
- Denial of service via excessive API usage (rate limiting is documented)
- Bugs that don't have security implications

---

## Security Measures

### Current Security Features

| Feature | Status | Description |
|---------|--------|-------------|
| Path Traversal Protection | ✅ | Validates crate names and extraction paths |
| Symlink Attack Protection | ✅ | Blocks symlinks pointing outside extraction directory |
| Input Validation | ✅ | Validates crate names against allowed patterns |
| Dependency Scanning | ✅ | CodeQL and Bandit scan on every PR |
| License Compliance | ✅ | cargo-license integration |
| Security Auditing | ✅ | cargo-deny integration for advisories |

### Security Best Practices

When contributing, please:

1. **Never log secrets** - Avoid logging API keys, tokens, or credentials
2. **Validate all inputs** - Especially paths, URLs, and user-provided data
3. **Use parameterized queries** - If adding database functionality
4. **Avoid `shell=True`** - Use list-based subprocess calls
5. **Handle errors safely** - Don't expose internal details in error messages

---

## Vulnerability Disclosure Process

### Timeline

1. **Day 0**: Vulnerability reported
2. **Day 1-2**: Initial triage and acknowledgment
3. **Day 3-7**: Vulnerability confirmed and assessed
4. **Day 7-30**: Patch developed and tested
5. **Day 30-45**: Coordinated disclosure with reporter
6. **Day 45+**: Public advisory and fix release

### Severity Classifications

| Severity | Response Time | Description |
|----------|---------------|-------------|
| Critical | 24-48 hours | Remote code execution, authentication bypass |
| High | 72 hours | Data exposure, significant DoS |
| Medium | 7 days | Limited impact vulnerabilities |
| Low | 30 days | Minimal impact, defense in depth |

---

## Safe Harbor

We consider security research conducted in good faith to be authorized and will not pursue legal action against researchers who:

1. **Act in good faith** - Make reasonable efforts to avoid privacy violations, data destruction, and service disruption
2. **Report promptly** - Submit findings through the proper channels
3. **Allow reasonable time** - Give us time to respond before public disclosure
4. **Don't exploit** - Don't use the vulnerability beyond proof of concept

---

## Security Updates

Security advisories are published through:

1. **GitHub Security Advisories** - Primary notification channel
2. **Release Notes** - Mentioned in CHANGELOG
3. **PyPI** - New version with security fix

To receive notifications, **Watch** the repository and enable security alerts.

---

## Contact

- **GitHub Security Advisories**: Preferred method
- **Maintainer**: Dave Tofflemire (@Superuser666-Sigil)

---

## Acknowledgments

We appreciate responsible disclosure and will acknowledge security researchers in our advisories (unless they prefer to remain anonymous).

### Hall of Fame

*Contributors who have helped improve our security will be listed here.*

---

Thank you for helping keep Sigil Pipeline secure! 🔒






