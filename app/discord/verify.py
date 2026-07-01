"""
Verifies that incoming requests genuinely came from Discord,
using Ed25519 signature verification as required by Discord's spec.
"""
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError
from app.config import DISCORD_PUBLIC_KEY

_verify_key = VerifyKey(bytes.fromhex(DISCORD_PUBLIC_KEY))


def verify_discord_signature(signature: str, timestamp: str, body: bytes) -> bool:
    """
    Returns True if the request signature is valid, False otherwise.
    signature and timestamp come from request headers:
      X-Signature-Ed25519, X-Signature-Timestamp
    body is the raw request body bytes (NOT parsed JSON).
    """
    if not signature or not timestamp:
        return False
    try:
        _verify_key.verify(
            timestamp.encode() + body,
            bytes.fromhex(signature)
        )
        return True
    except (BadSignatureError, ValueError):
        return False