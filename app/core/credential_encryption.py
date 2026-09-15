from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def _get_fernet() -> Fernet:
    key = settings.CREDENTIAL_ENCRYPTION_KEY

    if not key:
        raise RuntimeError("CREDENTIAL_ENCRYPTION_KEY is not configured.")

    try:
        return Fernet(key.encode("utf-8"))
    except Exception as exc:
        raise RuntimeError(
            "CREDENTIAL_ENCRYPTION_KEY is invalid. Generate a valid Fernet key."
        ) from exc


def encrypt_password(password: str) -> str:
    """
    Encrypt a staff password so it can be recovered by an authorized
    Super Admin.

    This is intentionally separate from password hashing.
    """
    if not password:
        raise ValueError("Password cannot be empty.")

    fernet = _get_fernet()

    encrypted = fernet.encrypt(password.encode("utf-8"))

    return encrypted.decode("utf-8")


def decrypt_password(encrypted_password: str) -> str:
    """
    Decrypt a staff password for an authorized backend operation.
    """
    if not encrypted_password:
        raise ValueError("Encrypted password cannot be empty.")

    fernet = _get_fernet()

    try:
        decrypted = fernet.decrypt(encrypted_password.encode("utf-8"))

        return decrypted.decode("utf-8")

    except InvalidToken as exc:
        raise RuntimeError(
            "Unable to decrypt credential. "
            "The encryption key may have changed or the credential is invalid."
        ) from exc
