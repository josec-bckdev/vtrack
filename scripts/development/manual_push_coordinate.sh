#!/bin/bash

# Configuration
REDIS_CONTAINER="redis_queue"
REDIS_QUEUE="coordinate_queue"

# Message Data - Easily modifiable variables
ROUTE_ID="101"

#Prado
#LATITUDE="4.71629"
#LONGITUDE="-74.060712"

#Sale de Prado antes de batan
LATITUDE="4.710782"
LONGITUDE="-74.053842"


POSITION_TIMESTAMP="2026-02-10T14:30:45-05:00"

ROUTE_STATUS="En Servicio"
STUDENT_STATUS="Activo"
QUEUED_AT="2026-02-10T14:30:45-05:00"

# Construct JSON message
JSON_MESSAGE="{\"ruta\":${ROUTE_ID},\"latitude\":${LATITUDE},\"longitude\":${LONGITUDE},\"position_ts\":\"${POSITION_TIMESTAMP}\",\"route_status\":\"${ROUTE_STATUS}\",\"student_status\":\"${STUDENT_STATUS}\",\"queued_at\":\"${QUEUED_AT}\"}"

# Execute command
docker exec ${REDIS_CONTAINER} redis-cli LPUSH ${REDIS_QUEUE} '${JSON_MESSAGE}'
