============
Integrations
============

Github
^^^^^^

`Goblet Github Action <https://github.com/marketplace/actions/goblet-deploy>`_

Example

.. code:: yaml

    on:
        push:
            branches:
            - main
    name: Deploy Goblet App
    jobs:
        deploy:
            name: deploy
            runs-on: ubuntu-latest
            env:
            GCLOUD_PROJECT: GCLOUD_PROJECT
            steps:
            - name: checkout
            uses: actions/checkout@v2
            - name: Setup Cloud SDK
            uses: google-github-actions/setup-gcloud@v0.2.0
            with:
            project_id: ${{ env.GCLOUD_PROJECT }}
            service_account_key: ${{ secrets.GCP_SA_KEY }}
            export_default_credentials: true
            - name: goblet deploy
            uses: anovis/goblet-github-actions@v2.3
            with:
                project: ${{ env.GCLOUD_PROJECT }}
                location: us-central1
                goblet-path: test
                stage: dev
                envars:  |-
                SLACK_WEBHOOK:slack,BILLING_ORG:bill,BILLING_ID:bill_id

 