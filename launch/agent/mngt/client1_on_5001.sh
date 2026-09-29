 #!/usr/bin/bash 

# the agents require the X-Pybiscus header on the requests that change something (CSRF)
curl -X POST -H "X-Pybiscus: 1" http://127.0.0.1:5001/client/config -F "file=@configs/toupload/client_1.yml"
curl -X POST -H "X-Pybiscus: 1" "http://127.0.0.1:5001/client"
