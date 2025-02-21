from cryptography import x509
from cryptography.hazmat.backends import default_backend

# Load PEM-encoded certificate
with open("server/server.crt", "rb") as f:
    pem_data = f.read()

# Parse certificate
certificate = x509.load_pem_x509_certificate(pem_data, default_backend())

# Access certificate fields
print(f"Subjet: {certificate.subject}")
print(f"Issuer: {certificate.issuer}")
print(f"MinDate: {certificate.not_valid_before}")
print(f"MaxDate: {certificate.not_valid_after}")
