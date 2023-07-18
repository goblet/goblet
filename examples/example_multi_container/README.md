# Multi Container Deployment for OPA policies.

This deployment requires an opa server, a goblet app, and a nginx server to service the OPA policies. 

## Local

You will need to set the `proxy_pass` value to `http://api_server:80;` in the `nginx.conf` file 
You can then build the goblet container by running `docker-compose build`.
You can spin up all containers locally by running `docker-compose up`

You can curl `localhost:8080/test` to get the api endpoint from goblet
You can curl `localhost:8080/nginx` to get a response from nginx

## Deployment

You will need to upload your `nginx.conf` to GCP secrets manager in order to mount the bundle as a volume for nginx. Note that the service account for Cloudrun will need permissions to this secret. 

You will need to update the `SERVICE_ACCOUNT` field in `.goblet/config.json`. 

Run `goblet deploy -p PROJECT -l REGION` to deploy. 

## Cleanup 

Run `goblet destroy -p PROJECT -l REGION` to cleanup. 
