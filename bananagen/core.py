from PIL import Image
import logging
import os
import base64
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)

def generate_placeholder(width: int, height: int, color: str = "#ffffff", transparent: bool = False, out_path: str = None):
    """Generate a placeholder image."""
    logger.info("Generating placeholder image", extra={
        "width": width,
        "height": height,
        "color": color,
        "transparent": transparent,
        "out_path": out_path
    })
    
    if transparent:
        mode = "RGBA"
        color_value = (255, 255, 255, 0)  # transparent white
    else:
        mode = "RGB"
        # parse color
        if color.startswith("#"):
            color_value = tuple(int(color[i:i+2], 16) for i in (1, 3, 5))
        else:
            color_value = (255, 255, 255)  # default white

    img = Image.new(mode, (width, height), color_value)
    if out_path:
        img.save(out_path)
        logger.info("Placeholder image saved", extra={"out_path": out_path})
    return img


def _get_encryption_key() -> str:
    """Get or derive the master encryption key."""
    env_key = os.getenv("BANANAGEN_ENCRYPTION_KEY")
    if env_key:
        logger.debug("Using encryption key from environment variable")
        key = env_key.encode('utf-8').ljust(32, b'\0')[:32]
        return base64.urlsafe_b64encode(key).decode()

    # Derive from project name
    project_name = "bananagen"
    salt = b"bananastaticsalt"  # Fixed salt for consistent derivation
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = kdf.derive(project_name.encode('utf-8'))
    logger.debug("Derived encryption key from project name")
    return base64.urlsafe_b64encode(key).decode()


def encrypt_key(key: str) -> str:
    """Encrypt an API key string securely using AES-Fernet.

    Args:
        key: The plain text API key to encrypt.

    Returns:
        Fernet token string.
    """
    try:
        logger.info("Encrypting API key", extra={"key_length": len(key)})
        encryption_key = _get_encryption_key()
        f = Fernet(encryption_key.encode())
        result = f.encrypt(key.encode('utf-8')).decode('utf-8')
        logger.debug("API key encrypted successfully", extra={"encrypted_length": len(result)})
        return result
    except Exception as e:
        logger.error("Failed to encrypt API key", extra={"error": str(e), "error_type": type(e).__name__})
        raise Exception(f"Encryption failed: {e}")


def decrypt_key(encrypted: str) -> str:
    """Decrypt an encrypted API key string using AES-Fernet.

    Args:
        encrypted: The Fernet token string.

    Returns:
        The plain text API key.
    """
    try:
        logger.info("Decrypting API key", extra={"encrypted_length": len(encrypted)})
        encryption_key = _get_encryption_key()
        f = Fernet(encryption_key.encode())
        result = f.decrypt(encrypted.encode()).decode('utf-8')
        logger.debug("API key decrypted successfully", extra={"key_length": len(result)})
        return result
    except InvalidToken:
        # Assume backward compatibility: if not Fernet encrypted, treat as plain
        logger.info("Key does not appear encrypted, assuming plain text", extra={"key_length": len(encrypted)})
        return encrypted
    except Exception as e:
        logger.error("Failed to decrypt API key", extra={"error": str(e), "error_type": type(e).__name__})
        raise Exception(f"Decryption failed: {e}")
