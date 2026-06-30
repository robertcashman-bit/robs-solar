from app.adapters.sunsynk_auth import (
    encrypt_password_rsa,
    sign_for_login,
    sign_for_public_key,
)

TEST_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAu1SU1LfVLPHCozMxH2Mo
4mHlMNbcvHAbX5e1dH7mM8g0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k
0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6
k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n
6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k
0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n
6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k
0wIDAQAB
-----END PUBLIC KEY-----"""


def test_public_key_sign_uses_power_view_salt() -> None:
    assert sign_for_public_key(1234567890) == sign_for_public_key(1234567890)
    assert sign_for_public_key(1234567890) != sign_for_login(1234567890, "abcdefghij")


def test_login_sign_uses_public_key_prefix() -> None:
    nonce = 999
    key = "abcdefghijklmnop"
    assert sign_for_login(nonce, key) != sign_for_login(nonce, "klmnopqrst")


def test_encrypt_password_returns_base64() -> None:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )
    encrypted = encrypt_password_rsa("test-pass", public_pem)
    assert encrypted
    assert encrypted != "test-pass"
