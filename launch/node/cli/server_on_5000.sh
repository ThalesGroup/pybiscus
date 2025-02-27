 #!/usr/bin/bash 

curl -X POST http://127.0.0.1:5000/server/config -F "file=@configs/toupload/server.yml"
curl "http://127.0.0.1:5000/server" 
