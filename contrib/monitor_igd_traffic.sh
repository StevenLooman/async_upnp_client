#!/usr/bin/env bash

# Example script to monitor traffic count (bytes in/bytes out) on my IGD
# Requires:
#   - jq (install by: sudo apt-get install jq)
#   - async_upnp_client (install by: pip install async_pnp_client)

set -e

if [ "${1}" = "" ]; then
	echo "Usage: ${0} url-to-device-description"
	exit 1
fi

# we want thousands separator
export LC_NUMERIC=en_US.UTF-8

UPNP_DEVICE_DESC=${1}
UPNP_ACTION_RECEIVED=WANCIFC/GetTotalBytesReceived
UPNP_ACTION_SENT=WANCIFC/GetTotalBytesSent
JQ_QUERY_RECEIVED=.out_parameters.NewTotalBytesReceived
JQ_QUERY_SENT=.out_parameters.NewTotalBytesSent
SLEEP_TIME=1

function get_bytes_received {
	echo $(upnp-client --device ${UPNP_DEVICE_DESC} call-action ${UPNP_ACTION_RECEIVED} | jq "${JQ_QUERY_RECEIVED}")
}

function get_bytes_sent {
	echo $(upnp-client --device ${UPNP_DEVICE_DESC} call-action ${UPNP_ACTION_SENT} | jq "${JQ_QUERY_SENT}")
}

# print header
printf "%-*s %*s %*s\n" 24 "Timestamp" 16 "Received" 16 "Sent"

BYTES_RECEIVED=$(get_bytes_received)
BYTES_SENT=$(get_bytes_sent)
while [ true ]; do
	sleep ${SLEEP_TIME}

	PREV_BYTES_RECEIVED=${BYTES_RECEIVED}
	PREV_BYTES_SENT=${BYTES_SENT}

	BYTES_RECEIVED=$(get_bytes_received)
	BYTES_SENT=$(get_bytes_sent)

	DIFF_BYTES_RECEIVED=$((${BYTES_RECEIVED} - ${PREV_BYTES_RECEIVED}))
	DIFF_BYTES_SENT=$((${BYTES_SENT} - ${PREV_BYTES_SENT}))

	DATE=$(date "+%Y-%m-%d %H:%M:%S")
	printf "%-*s %'*.0f %'*.0f\n" 24 "${DATE}" 16 "${DIFF_BYTES_RECEIVED}" 16 "${DIFF_BYTES_SENT}"
done
