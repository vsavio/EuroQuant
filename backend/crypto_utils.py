import os
import base64
from cryptography.fernet import Fernet

# Fallback static key if none provided (for development ease)
DEFAULT_KEY = base64.urlsafe_b64encode(b"EuroQuant_Default_Key_32_Bytes_!")
KEY = os.environ.get("ENCRYPTION_KEY")

if KEY:
    try:
        # Ensure key is valid base64
        fernet = Fernet(KEY.encode())
    except Exception:
        print("WARNING: Invalid ENCRYPTION_KEY environment variable. Falling back to default key.")
        fernet = Fernet(DEFAULT_KEY)
else:
    print("WARNING: ENCRYPTION_KEY environment variable not set. Secrets will be encrypted using a default key.")
    fernet = Fernet(DEFAULT_KEY)

def encrypt_data(plain_text: str) -> str:
    if not plain_text:
        return ""
    return fernet.encrypt(plain_text.encode()).decode()

def decrypt_data(cipher_text: str) -> str:
    if not cipher_text:
        return ""
    try:
        return fernet.decrypt(cipher_text.encode()).decode()
    except Exception:
        # Fallback to returning raw text if it wasn't encrypted or if the key doesn't match
        return cipher_text
