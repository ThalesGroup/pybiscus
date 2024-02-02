import pickle
from phe import paillier

# Génération des clés
public_key, private_key = paillier.generate_paillier_keypair(n_length=128)

# Sauvegarde des clés
keys = (public_key, private_key)
with open('keys.pkl', 'wb') as f:
    pickle.dump(keys, f)