# Enterprise Information Security Policy (POL-SEC-2026)

## 1. Authentication and Access Control
1.1 All corporate systems require Multi-Factor Authentication (MFA) via hardware security keys or FIDO2-compliant authenticators. SMS-based MFA is strictly prohibited for administrative access.
1.2 Passwords must contain a minimum of 16 characters, including uppercase, lowercase, numbers, and special symbols. Automated password rotation is enforced every 90 days.
1.3 Workstation sessions automatically lock after 5 minutes of inactivity. Re-authentication is required to resume access.

## 2. Remote Access and Network Security
2.1 Remote access to internal networks must traverse the corporate Zero-Trust Network Access (ZTNA) tunnel with device posture verification.
2.2 Split-tunneling is strictly disabled on company-managed devices.
2.3 Direct remote desktop (RDP) exposure to the public internet is classified as a Critical Severity vulnerability and leads to immediate IP revocation.

## 3. Data Encryption Standards
3.1 All data at rest within enterprise databases and storage volumes must be encrypted using AES-256-GCM.
3.2 All data in transit across public and internal subnets must enforce TLS 1.3 with forward secrecy ciphers.
3.3 Cryptographic keys must be managed in dedicated Hardware Security Modules (HSM) with annual automated key rotation.

## 4. Incident Response and Reporting
4.1 Any suspected security incident or credential compromise must be reported to the Security Operations Center (SOC) within 15 minutes of discovery.
4.2 The SOC emergency hotline is available 24/7/365 at security-emergency@internal.net or via internal extension x4433.
4.3 Incident severity classifications: P1 (Critical Outage/Breach), P2 (Major Impact), P3 (Minor Incident), P4 (Informational).
