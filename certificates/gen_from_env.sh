#!/bin/bash

. ./set_env.sh

# a new CA invalidates every certificate it signed, already copied to the other machines
if [ -e ca/ca.crt ] && [ "${FORCE_NEW_CA:-}" != "1" ]; then
  echo "ERROR: $(pwd)/ca/ca.crt exists already; to replace it and every certificate it signed: FORCE_NEW_CA=1 $0"
  exit 1
fi

# the Flower clients present no certificate (they check the server's with the CA): none by default
NUM_CLIENTS=${NUM_CLIENTS:-0}

ca_password new

# DN Elements for the CA
CA_C=${CA_C:-"US"}
CA_ST=${CA_ST:-"State"}
CA_L=${CA_L:-"City"}
CA_O=${CA_O:-"Organization"}
CA_OU=${CA_OU:-"OrgUnit"}
CA_CN=${CA_CN:-"RootCA"}

# DN Elements for the Server
SERVER_C=${SERVER_C:-"US"}
SERVER_ST=${SERVER_ST:-"State"}
SERVER_L=${SERVER_L:-"City"}
SERVER_O=${SERVER_O:-"Organization"}
SERVER_OU=${SERVER_OU:-"OrgUnit"}
SERVER_CN=${SERVER_CN:-"Server"}

# DN Elements for the Clients
CLIENT_C=${CLIENT_C:-"US"}
CLIENT_ST=${CLIENT_ST:-"State"}
CLIENT_L=${CLIENT_L:-"City"}
CLIENT_O=${CLIENT_O:-"Organization"}
CLIENT_OU=${CLIENT_OU:-"OrgUnit"}
CLIENT_CN_PREFIX=${CLIENT_CN_PREFIX:-"Client"}

# Dossiers pour stocker les clés et certificats
mkdir -p ca
mkdir -p server
[ "$NUM_CLIENTS" -gt 0 ] && mkdir -p clients

# 1. Créer une CA racine
echo "Creating Root CA..."
openssl genpkey -algorithm RSA -out ca/ca.key -aes256 -pass env:rootCApass
openssl req -x509 -new -nodes -utf8 -key ca/ca.key -sha256 -days 1024 -out ca/ca.crt \
  -subj "/C=$CA_C/ST=$CA_ST/L=$CA_L/O=$CA_O/OU=$CA_OU/CN=$CA_CN" -passin env:rootCApass

# 2. Créer une clé privée et une CSR pour le serveur
echo "Creating Server Key and CSR..."
openssl genpkey -algorithm RSA -out server/server.key
openssl req -new -utf8 -key server/server.key -out server/server.csr \
  -subj "/C=$SERVER_C/ST=$SERVER_ST/L=$SERVER_L/O=$SERVER_O/OU=$SERVER_OU/CN=$SERVER_CN"

# Extraire la clé publique du serveur
echo "Extracting Server Public Key..."
openssl rsa -in server/server.key -pubout -out server/server.pub

# Signer le CSR du serveur avec la CA racine
echo "Signing Server CSR with Root CA..."
# gRPC checks the name the clients connect to against the subjectAltName only, not the CN:
# the server's name, plus the local ones for a session on one machine (SERVER_SAN adds others)
SERVER_SAN=${SERVER_SAN:-"DNS:$SERVER_CN,DNS:localhost,IP:127.0.0.1,IP:::1"}
openssl x509 -req -in server/server.csr -CA ca/ca.crt -CAkey ca/ca.key -CAcreateserial \
  -out server/server.crt -days 500 -sha256 -passin env:rootCApass \
  -extfile <(printf "subjectAltName=%s" "$SERVER_SAN")

# 3. Créer des clés privées et des CSR pour les clients
for i in $(seq 1 $NUM_CLIENTS); do
  CLIENT_CN="${CLIENT_CN_PREFIX}${i}"
  echo "Creating Client $i Key and CSR..."
  openssl genpkey -algorithm RSA -out clients/client$i.key
  openssl req -new -utf8 -key clients/client$i.key -out clients/client$i.csr \
    -subj "/C=$CLIENT_C/ST=$CLIENT_ST/L=$CLIENT_L/O=$CLIENT_O/OU=$CLIENT_OU/CN=$CLIENT_CN"

  # Extraire la clé publique du client
  echo "Extracting Client $i Public Key..."
  openssl rsa -in clients/client$i.key -pubout -out clients/client$i.pub

  # Signer le CSR du client avec la CA racine
  echo "Signing Client $i CSR with Root CA..."
  openssl x509 -req -in clients/client$i.csr -CA ca/ca.crt -CAkey ca/ca.key -CAcreateserial \
    -out clients/client$i.crt -days 500 -sha256 -passin env:rootCApass
done

echo "All keys and certificates have been created."
