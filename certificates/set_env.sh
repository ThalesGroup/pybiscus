
# certificates for the Flower clients: they present none in Pybiscus, keep 0 unless you need them
export NUM_CLIENTS=0

# rootCApass, the password of the CA's key, is never written here (this file is versioned): from the
# environment (rootCApass=... ./gen_from_env.sh), else asked by ca_password
export CA_C="FR"
export CA_ST="Île-de-France"
export CA_L="Palaiseau"
export CA_O="Thales"
export CA_OU="Theresis"
export CA_CN="Pybiscus"

export SERVER_C="FR"
export SERVER_ST="Île-de-France"
export SERVER_L="Palaiseau"
export SERVER_O="Thales"
export SERVER_OU="Theresis"
export SERVER_CN="$(hostname)"

export CLIENT_C="FR"
export CLIENT_ST="Île-de-France"
export CLIENT_L="Palaiseau"
export CLIENT_O="Thales"
export CLIENT_OU="Theresis"
export CLIENT_CN_PREFIX="Pybiscus-Client"

ca_password() {
  if [ -z "${rootCApass:-}" ]; then
    if ! { exec 3</dev/tty; } 2>/dev/null; then
      echo "ERROR: no terminal to ask the password of the CA's key: give it in rootCApass" >&2
      exit 1
    fi
    read -r -s -u 3 -p "password of the CA's key (ca/ca.key): " rootCApass; echo >&2
    # a new CA: a typo would lock its key for good
    if [ "${1:-}" = "new" ]; then
      read -r -s -u 3 -p "again: " again; echo >&2
      [ "$again" = "$rootCApass" ] || { echo "ERROR: the two passwords differ" >&2; exit 1; }
    fi
    exec 3<&-
  fi
  [ -n "$rootCApass" ] || { echo "ERROR: empty password for the CA's key" >&2; exit 1; }
  # openssl reads it from the environment (-pass env:): not in its command line, which ps shows
  export rootCApass
}
