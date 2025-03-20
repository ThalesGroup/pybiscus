 #!/usr/bin/bash 

curl -X POST http://127.0.0.1:5002/client/config -F "file=@configs/toupload/client_2.yml"
curl "http://127.0.0.1:5002/client/2" 
