FROM google/cloud-sdk:alpine
RUN gcloud components install pubsub-emulator

# Only copy what we need from the emulator
FROM openjdk:jre-alpine
COPY --from=0 /google-cloud-sdk/platform/pubsub-emulator /pubsub-emulator
RUN apk --update --no-cache add tini bash
ENTRYPOINT ["/sbin/tini", "--"]
CMD /pubsub-emulator/bin/cloud-pubsub-emulator --host=0.0.0.0 --port=8085
EXPOSE 8085
HEALTHCHECK --interval=2s --start-period=15s --retries=5 \
	CMD sh -c "netstat -tulpen | grep 0.0.0.0:8085 || exit 1"