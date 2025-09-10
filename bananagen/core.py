from PIL import Image
import logging
import os
import base64
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

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


def _get_encryption_key() -> bytes:
    """Get or derive the master encryption key."""
    env_key = os.getenv("BANANAGEN_ENCRYPTION_KEY")
    if env_key:
        logger.debug("Using encryption key from environment variable")
        return env_key.encode('utf-8').ljust(32, b'\0')[:32]  # Ensure 32 bytes

    # Derive from project name
    project_name = "bananagen"
    salt = b"bananastaticsalt"  # Fixed salt for consistent derivation
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=default_backend()
    )
    key = kdf.derive(project_name.encode('utf-8'))
    logger.debug("Derived encryption key from project name")
    return key


def encrypt_key(key: str) -> str:
    """Encrypt an API key string securely using AES-GCM.

    Args:
        key: The plain text API key to encrypt.

    Returns:
        Base64-encoded encrypted key string.
    """
    try:
        logger.info("Encrypting API key", extra={"key_length": len(key)})
        encryption_key = _get_encryption_key()
        iv = os.urandom(12)  # GCM requires 12-byte IV
        cipher = Cipher(algorithms.AES(encryption_key), modes.GCM(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(key.encode('utf-8')) + encryptor.finalize()
        encrypted = iv + encryptor.tag + ciphertext  # Store IV, tag, ciphertext
        result = base64.b64encode(encrypted).decode('utf-8')
        logger.debug("API key encrypted successfully", extra={"encrypted_length": len(result)})
        return result
    except Exception as e:
        logger.error("Failed to encrypt API key", extra={"error": str(e), "error_type": type(e).__name__})
        raise Exception(f"Encryption failed: {e}")


def decrypt_key(encrypted: str) -> str:
    """Decrypt an encrypted API key string using AES-GCM.

    Args:
        encrypted: The base64-encoded encrypted key string.

    Returns:
        The plain text API key.
    """
    try:
        logger.info("Decrypting API key", extra={"encrypted_length": len(encrypted)})
        encryption_key = _get_encryption_key()
        data = base64.b64decode(encrypted)
        if len(data) < 28:  # IV + tag + at least 1 byte ciphertext
            raise ValueError("Invalid encrypted data")
        iv = data[:12]
        tag = data[12:28]
        ciphertext = data[28:]
        cipher = Cipher(algorithms.AES(encryption_key), modes.GCM(iv, tag), backend=default_backend())
        decryptor = cipher.decryptor()
        plaintext = decryptor.update(ciphertext) + decryptor.finalize()
        result = plaintext.decode('utf-8')
        logger.debug("API key decrypted successfully", extra={"key_length": len(result)})
        return result
    except Exception as e:
        logger.error("Failed to decrypt API key", extra={"error": str(e), "error_type": type(e).__name__})
        raise Exception(f"Decryption failed: {e}")
