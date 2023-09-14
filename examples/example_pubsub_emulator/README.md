# PubSub Emulator Example
In the dynamic landscape of contemporary software development, the efficacy of Google Cloud Pub/Sub service is undeniable; however, its seamless integration into development workflows poses challenges in terms of speed, cost, and potential live system disruptions. Addressing these issues, the incorporation of a Pub/Sub emulator in local development emerges as a pivotal practice. By replicating the functions of this service on developers' machines, emulators enable offline work, eliminate financial constraints, expedite testing iterations, and enhance data security, collectively fostering a more efficient and confident development process.

## Running Emulator
```bash
docker compose up -d
export PUBSUB_EMULATOR_HOST="localhost:8085"
export GOBLET_LOCAL_URL="http://host.docker.internal:8080"
```
Make sure to have docker running on your machine. And port `8085` open.

## Running Example
```bash
# Run the example. This will create a topic and a subscription on the emulator.
goblet local --extras
# Publish a message to the topic. On a separate terminal.
curl http://localhost:8080/send
```