#!/bin/bash
# Key, request and signature on the machine of the CA: for a demo, or a machine whose key may be
# copied. Between organizations, each site runs gen_component_csr.sh and keeps its key.
#   ./gen_component_cert.sh <machine name> [extra subjectAltName entries]
set -euo pipefail

if [ $# -lt 1 ] || [ $# -gt 2 ]; then
  echo "usage: $0 <machine name> [extra subjectAltName entries]" >&2
  exit 1
fi
here="$(dirname "$0")"
"$here/gen_component_csr.sh" "$1"
"$here/sign_component_csr.sh" "$here/components/$1/$1.csr" "$@"
