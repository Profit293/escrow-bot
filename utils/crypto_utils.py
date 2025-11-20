from cryptography.fernet import Fernet
from config import load_config

config = load_config()
cipher = Fernet(config.encryption_key.encode())

def encrypt_data(data: str) -> str:
    return cipher.encrypt(data.encode()).decode()

def decrypt_data(encrypted_data: str) -> str:
    return cipher.decrypt(encrypted_data.encode()).decode()