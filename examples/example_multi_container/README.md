# Multi Container Deployment for OPA policies.

This deployment requires an opa server, a goblet app, and a nginx server to service the OPA policies. 

## Local

You will need to install the opa binaries and then build the `bundle.tar.gz` by running `./opa build policy`
You can then build the goblet container by running `docker-compose build`.
You can spin up all containers locally by running `docker-compose up`

## Deployment

You will need to upload your `bundle.tar.gz` to GCP secrets manager in order to mount the bundle as a volume for nginx. Note that the service account for Cloudrun will need permissions to this secret. 

You will need to update the `SERVICE_ACCOUNT` field in `config.json`. 

Run `goblet deploy -p PROJECT -l REGION` to deploy. 

## Cleanup 

Run `goblet destroy -p PROJECT -l REGION` to cleanup. 
