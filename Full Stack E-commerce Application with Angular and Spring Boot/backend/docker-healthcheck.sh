#!/bin/bash
set -eu
# Actuator's aggregate health includes the configured MySQL datasource.
exec 3<>/dev/tcp/127.0.0.1/8080
printf 'GET /actuator/health HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n' >&3
IFS= read -r status <&3
[[ "$status" == HTTP/*' 200 '* ]] || exit 1
response=$(cat <&3)
[[ "$response" == *'"status":"UP"'* ]]
