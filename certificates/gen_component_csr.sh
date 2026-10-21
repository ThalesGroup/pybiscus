#!/bin/bash
# Run on the machine of the component: its private key never leaves it, only the request goes to
# whoever holds the CA (sign_component_csr.sh).
#   ./gen_component_csr.sh <machine name>   ->   components/<name>/<name>.key, <name>.csr
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "usage: $0 <machine name>" >&2
  exit 1
fi
name="$1"
cd "$(dirname "$0")"
. ./set_env.sh

dir="components/$name"
if [ -e "$dir/$name.key" ]; then
  echo "ERROR: $dir/$name.key exists already: remove it first to make a new key" >&2
  exit 1
fi
mkdir -p "$dir"
# the key is left unencrypted: the manager and the agent load it at start, without a prompt
(umask 077 && openssl genpkey -algorithm RSA -out "$dir/$name.key")
openssl req -new -utf8 -key "$dir/$name.key" -out "$dir/$name.csr" \
  -subj "/C=${SERVER_C:-US}/ST=${SERVER_ST:-State}/L=${SERVER_L:-City}/O=${SERVER_O:-Organization}/OU=${SERVER_OU:-OrgUnit}/CN=$name"
echo "key: $(pwd)/$dir/$name.key (keep it on this machine)"
echo "request to sign: $(pwd)/$dir/$name.csr"
