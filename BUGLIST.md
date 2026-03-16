# System Status Real-Time Update - Bug Investigation

## Problem
System Status must update every 2 seconds even during LLM response generation (while "Thinking..." is displayed).

## Root Cause
JavaScript is single-threaded. When `await fetch()` is called for the chat endpoint, the main thread blocks waiting for the response. During this time, `setTimeout`/`setInterval` callbacks cannot execute because the event loop is blocked.

## Approaches Tried (FAILED)

1. **Web Worker** - Created `status-worker.js` but initialization failed due to path/scope issues
2. **Hidden iframe** - Created `status-iframe.html` with separate polling - same blocking issue (browser limits concurrent connections to same host)
3. **SSE (Server-Sent Events)** - Added `/api/system-status-stream` endpoint but nginx proxy issues prevented it from working
4. **XMLHttpRequest (sync)** - Tried synchronous XHR in iframe - didn't help
5. **Non-blocking .then()** - Converted `await fetch()` to `.then()` chaining - didn't solve the core issue
6. **fetch with keepalive** - Browser still limits to same connection pool
7. **Recursive setTimeout** - Same issue, can't run during main thread block
8. **HTTP/2 nginx** - Tried enabling HTTP/2 - no improvement
9. **Multiple nginx configs** - worker_connections, proxy_buffering off - no improvement

## What Works
- Status updates every 2 seconds when NOT in "Thinking..." state
- Chat works perfectly
- All other functionality works

## Final Attempt (Pending)
Use Web Worker with its OWN fetch call - Web Workers have separate threads and should not be blocked by main thread fetch.

## Alternative Solutions (Not Implemented)
1. **Separate port for status** - Run status API on port 8503, completely different connection pool
2. **Service Worker** - More powerful than Web Worker, could intercept requests
3. **Backend push** - Have the chat endpoint itself return status updates along with the response
