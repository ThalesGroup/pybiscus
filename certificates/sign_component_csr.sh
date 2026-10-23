#!/bin/bash
# Run where the CA is (ca/ca.key): signs a component's request for the names it is reached at.
#   ./sign_component_csr.sh <request.csr> <machine name> [extra subjectAltName entries]
#   e.g. ./sign_component_csr.sh site-a.csr site-a.example.org "IP:10.0.0.5"
# -> components/<name>/<name>.crt, for the manager and the agents of that machine (--tls-cert) and
# for the Flower server running there (flower_server.ssl).
set -euo pipefail

if [ $# -lt 2 ] || [ $# -gt 3 ]; then
  echo "usage: $0 <request.csr> <machine name> [extra subjectAltName entries]" >&2
  exit 1
fi
csr="$(realpath "$1")"
name="$2"
extra="${3:-}"
cd "$(dirname "$0")"
. ./set_env.sh

if [ ! -f ca/ca.crt ] || [ ! -f ca/ca.key ]; then
  echo "ERROR: no CA in $(pwd)/ca: create it once with gen_from_env.sh" >&2
  exit 1
fi
ca_password
if [[ "$name" =~ ^[0-9.]+$ || "$name" == *:* ]]; then
  first="IP:$name"
else
  first="DNS:$name"
fi
# browsers, Python and gRPC check the name against the subjectAltName only, never the CN; the local
# names let a browser on the same machine reach the component as localhost
san="$first,DNS:localhost,IP:127.0.0.1,IP:::1${extra:+,$extra}"

dir="components/$name"
mkdir -p "$dir"
# written aside first: a wrong password left an empty certificate in place
trap 'rm -f "$dir/$name.crt.new"' EXIT
openssl x509 -req -in "$csr" -CA ca/ca.crt -CAkey ca/ca.key -CAcreateserial \
  -out "$dir/$name.crt.new" -days 500 -sha256 -passin env:rootCApass \
  -extfile <(printf "subjectAltName=%s\nbasicConstraints=CA:FALSE\nextendedKeyUsage=serverAuth\n" "$san")
mv "$dir/$name.crt.new" "$dir/$name.crt"
echo "certificate: $(pwd)/$dir/$name.crt ($san)"
echo "send it back with $(pwd)/ca/ca.crt, which every component and browser trusts (--tls-ca)"
