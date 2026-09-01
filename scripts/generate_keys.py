"""Generates the ECDSA key pair used to sign API requests.

Register the printed PUBLIC key in the sandbox Project (web dashboard);
the private key stays local and is referenced by STARKBANK_PRIVATE_KEY_PATH.
"""
import starkbank

private_key, public_key = starkbank.key.create()

with open("private-key.pem", "w") as f:
    f.write(private_key)

print("private key written to private-key.pem (keep it out of git!)")
print("\nregister this public key in your sandbox Project:\n")
print(public_key)
