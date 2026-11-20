"""
Sovereign Encrypted Local Keystore (`netopt/keystore.py`).
Protects P2P device identities (Ed25519) and local secrets using Fernet (AES-128-CBC + HMAC)
with PBKDF2-HMAC-SHA256 key derivation and atomic disk persistence.
"""

from __future__ import annotations
import base64
import json
import os
import secrets
import tempfile
import threading
import time
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


DEFAULT_KEYSTORE_PATH = os.path.expanduser("~/.netopt_state/keystore.json")


def _derive_fernet_key(passphrase: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
    )
    return base64.urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8")))


class SovereignKeystore:
    """Thread-safe encrypted local keystore for Ed25519 device identity and secrets."""

    def __init__(self, keystore_path: str = DEFAULT_KEYSTORE_PATH, passphrase: Optional[str] = None):
        self.keystore_path = keystore_path
        self._lock = threading.RLock()
        self._passphrase = passphrase or os.environ.get("OMNINET_KEYSTORE_PASSPHRASE") or self._default_machine_secret()
        self._salt, self._data = self._load_or_init()

    @staticmethod
    def _default_machine_secret() -> str:
        from .licensing import get_hardware_device_id
        return f"omninet-ks:{get_hardware_device_id()}"

    def _fernet(self, salt: bytes) -> Fernet:
        return Fernet(_derive_fernet_key(self._passphrase, salt))

    def _load_or_init(self) -> tuple[bytes, Dict[str, Any]]:
        if os.path.exists(self.keystore_path):
            try:
                with open(self.keystore_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                salt = base64.b64decode(raw["salt"])
                token = raw["ciphertext"].encode("utf-8")
                plain = self._fernet(salt).decrypt(token)
                data = json.loads(plain.decode("utf-8"))
                if isinstance(data, dict):
                    return salt, data
            except (OSError, KeyError, ValueError, InvalidToken):
                pass
        salt = secrets.token_bytes(16)
        data: Dict[str, Any] = {"identity": None, "secrets": {}, "updated_at": time.time()}
        return salt, data

    def _save(self) -> None:
        with self._lock:
            self._data["updated_at"] = time.time()
            ks_dir = os.path.dirname(os.path.abspath(self.keystore_path)) or "."
            os.makedirs(ks_dir, exist_ok=True)
            token = self._fernet(self._salt).encrypt(json.dumps(self._data).encode("utf-8")).decode("utf-8")
            envelope = {"version": 1, "salt": base64.b64encode(self._salt).decode("ascii"), "ciphertext": token}
            fd, tmp_path = tempfile.mkstemp(dir=ks_dir, prefix=".ks_", suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(envelope, f, indent=2)
                if os.name == "posix":
                    try:
                        os.chmod(tmp_path, 0o600)
                    except OSError:
                        pass
                os.replace(tmp_path, self.keystore_path)
            except Exception:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                raise

    def ensure_device_identity(self) -> Dict[str, str]:
        """Returns existing Ed25519 identity or generates and persists a new one."""
        with self._lock:
            ident = self._data.get("identity")
            if isinstance(ident, dict) and ident.get("public_key_hex") and ident.get("private_key_hex"):
                return {"did": ident["did"], "public_key_hex": ident["public_key_hex"]}
            return self.rotate_device_keys()

    def rotate_device_keys(self) -> Dict[str, str]:
        """Generates a fresh Ed25519 keypair and persists it encrypted."""
        with self._lock:
            priv = ed25519.Ed25519PrivateKey.generate()
            priv_bytes = priv.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption(),
            )
            pub_bytes = priv.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
            pub_hex = pub_bytes.hex()
            did = f"did:omninet:ed25519:{pub_hex[:24]}"
            self._data["identity"] = {
                "did": did,
                "public_key_hex": pub_hex,
                "private_key_hex": priv_bytes.hex(),
                "created_at": time.time(),
            }
            self._save()
            return {"did": did, "public_key_hex": pub_hex}

    def set_secret(self, name: str, value: str) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("secret name must be a non-empty string")
        with self._lock:
            self._data.setdefault("secrets", {})[name.strip()] = str(value)
            self._save()

    def get_secret(self, name: str) -> Optional[str]:
        with self._lock:
            return self._data.get("secrets", {}).get((name or "").strip())

    def export_public_identity(self) -> Dict[str, Any]:
        ident = self.ensure_device_identity()
        return {
            "did": ident["did"],
            "public_key_hex": ident["public_key_hex"],
            "encrypted_at_rest": True,
            "secrets_count": len(self._data.get("secrets", {})),
        }
