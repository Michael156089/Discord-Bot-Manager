from .config import cipher

def encrypt_token(token: str) -> str:
    return cipher.encrypt(token.encode()).decode()

def decrypt_token(encrypted: str) -> str:
    return cipher.decrypt(encrypted.encode()).decode()
