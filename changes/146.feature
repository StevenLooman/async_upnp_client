Provide a single method to retrieve commonly updated data. This contains:
* traffic counters:
   * bytes_received
   * bytes_sent
   * packets_received
   * packets_sent
* status_info:
   * connection_status
   * last_connection_error
   * uptime
* external_ip_address
* derived traffic counters:
   * kibibytes_per_sec_received (since last call)
   * kibibytes_per_sec_sent (since last call)
   * packets_per_sec_received (since last call)
   * packets_per_sec_sent (since last call)

Also let IgdDevice calculate derived traffic counters (value per second).
