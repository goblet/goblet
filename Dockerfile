# https://hub.docker.com/_/python
FROM python:3.10-slim

# setup environment
ENV APP_HOME /app
WORKDIR $APP_HOME

# install keyring backend to handle artifact registry authentication
# RUN pip install keyrings.google-artifactregistry-auth==1.1.1

# Copy requirements
COPY requirements.txt .

# Mount google adc credentials for local docker builds requiring Artifact Registry access
# RUN --mount=type=secret,id=gcloud_creds,target=/app/google_adc.json export GOOGLE_APPLICATION_CREDENTIALS=/app/google_adc.json \  
#     && pip install -r requirements.txt

# Install dependencies
RUN pip install -r requirements.txt

# Copy local code to the container image.
COPY . .

# Run the web service on container startup.
CMD exec functions-framework --target=goblet_entrypoint
