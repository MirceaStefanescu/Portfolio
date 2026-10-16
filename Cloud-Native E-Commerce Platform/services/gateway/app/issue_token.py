"""Local development issuer. Production identity must use a separately managed issuer."""

import argparse
import os
import time

import jwt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--role", choices=["customer", "admin"], default="customer")
    args = parser.parse_args()
    secret = os.environ.get("JWT_SECRET", "")
    if len(secret.encode()) < 32:
        parser.error("JWT_SECRET must contain at least 32 bytes")
    print(
        jwt.encode(
            {
                "sub": args.subject,
                "roles": [args.role],
                "iss": os.getenv("JWT_ISSUER", "portfolio"),
                "aud": os.getenv("JWT_AUDIENCE", "commerce"),
                "iat": int(time.time()),
                "exp": int(time.time()) + 900,
            },
            secret,
            algorithm="HS256",
        )
    )


if __name__ == "__main__":
    main()
