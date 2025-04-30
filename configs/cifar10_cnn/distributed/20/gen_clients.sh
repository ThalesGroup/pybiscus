
for i in {1..20}; do
	sed "s/CID/$i/g" client.yml > "client_${i}.yml"
done

