import hashlib
import secrets
import time

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def generate_token():
    return secrets.token_urlsafe(8)

def get_expiry(seconds):
    return int(time.time()) + seconds
