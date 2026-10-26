# ADR 0006: bounded Redis diagnostic queue

Status: accepted for M01.

Use a Redis list and one worker. An atomic enqueue script checks a pending
capacity of 20, writes the typed job record, and queues its UUID. The worker
claims a UUID, records running and terminal state, and executes only known
diagnostic kinds. Results expire after 300 seconds. Network waits, individual
jobs, failure retries, and container crash restarts are bounded.

This proves producer → Redis → worker → result with no additional queue
framework or broker. M01 diagnostics use at-most-once consumption: a worker
crash after a claim can leave a running record until expiry. There is no claim
of durable simulation-job delivery, distributed scheduling, replay, or automatic
traffic simulation. Those need a separate design in a later milestone.
