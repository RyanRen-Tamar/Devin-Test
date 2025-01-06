try:
    from Crypto.Cipher import AES
    from Crypto.Protocol.KDF import PBKDF2
    print("pycryptodome is available")
except ImportError:
    print("pycryptodome is not available")
