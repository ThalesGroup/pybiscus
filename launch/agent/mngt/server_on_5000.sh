 #!/usr/bin/bash 

# the agents require the X-Pybiscus header on the requests that change something (CSRF)
curl -X POST -H "X-Pybiscus: 1" http://127.0.0.1:5000/server/config -F "file=@configs/toupload/server.yml"
curl -X POST -H "X-Pybiscus: 1" "http://127.0.0.1:5000/server"
