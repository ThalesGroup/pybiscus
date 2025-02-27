 #!/usr/bin/bash 

curl -X POST http://127.0.0.1:5001/client/config -F "file=@configs/toupload/client_1.yml"
curl "http://127.0.0.1:5001/client/1" 
