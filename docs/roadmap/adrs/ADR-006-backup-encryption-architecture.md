# ADR-006: Backup & Encryption Architecture

**Status:** Draft  
**Date:** 2026-07-31  
**Author:** Lucien  
**Deciders:** Steven Page  

## Context

AST-Tools indexes can become valuable assets — hours of indexing time can't be replaced trivially. Without backup/restore, users risk losing their index on hardware failure. For enterprise deployments, backup encryption may be mandatory.

## Decision

Implement a **tar-based archive format with pluggable backends:**

### Archive Format

```
ast-tools-backup-2026-07-31.tar.gz
└── ast-tools-backup/
    ├── meta.yaml              # Backup metadata (version, date, checksums)
    ├── config/                # Copy of ~/.ast-tools/config/
    ├── database/              # SQLite database (VACUUM'd before archiving)
    │   └── codebase.db.gz     # gzip-compressed
    └── cache/
        └── models/            # Only if --include-models flag
```

### Storage Backends

| Backend | Type | Implementation | Phase |
|---------|------|----------------|-------|
| Local | Local filesystem | `shutil.copytree` + tar | 3 |
| S3 | Remote | `boto3` | 3 |
| SFTP | Remote | `paramiko` | 4 |
| rsync | Remote | Subprocess call | 4 |

### Backup Modes

| Mode | Description | Speed | Storage |
|------|-------------|-------|---------|
| **Full** | Complete archive of config + database | Slow | Large |
| **Incremental** | Only changed files since last full backup | Fast | Small |
| **Database-only** | Just the SQLite file (excludes models) | Fast | Medium |

### Encryption

```python
# AES-256-GCM with key derivation
from cryptography.fernet import Fernet
import base64, os

def encrypt_archive(archive_path: str, password: str) -> str:
    salt = os.urandom(16)
    key = base64.urlsafe_b64encode(hashlib.scrypt(
        password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32
    ))
    f = Fernet(key)
    # Encrypts the .tar.gz in-place, prepends salt
    encrypted_path = archive_path + ".encrypted"
    with open(archive_path, "rb") as src:
        encrypted = f.encrypt(src.read())
    with open(encrypted_path, "wb") as dst:
        dst.write(salt + encrypted)
    return encrypted_path

def decrypt_archive(encrypted_path: str, password: str) -> str:
    # Reverse of above: read salt, derive key, decrypt, return .tar.gz
    ...
```

### Key Management

- **Local backup:** User-provided password → derived key (no stored key)
- **Remote backup:** Optional SSH key + passphrase
- **Enterprise:** Optional KMS integration (AWS KMS, Azure Key Vault)

### Consequences
- Positive: Standard tar.gz format — inspectable without ast-tools tools
- Positive: Backend-agnostic — same restore flow for all backends
- Positive: Encryption is optional — users who don't need it don't pay complexity cost
- Negative: Large model files (~500MB for sentence-transformers) excluded by default
- Negative: Incremental backups require a baseline full backup

## Alternatives Considered
1. **Dedicated backup tool (restic/duplicity wrapper)**: Rejected — adds external dependency, inconsistent UX
2. **SQLite-only backup (`.backup` command)**: Rejected — misses config and models
3. **ZIP format**: Rejected — tar.gz is standard for Unix tooling