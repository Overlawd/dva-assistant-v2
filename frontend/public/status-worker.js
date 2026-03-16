// Status Web Worker - uses separate port 8503 for independent connection pool
var STATUS_API = 'http://localhost:8503/api';

function poll() {
    fetch(STATUS_API + '/system-status?_=' + Date.now(), { 
        cache: 'no-store'
    })
    .then(function(response) {
        return response.json();
    })
    .then(function(data) {
        self.postMessage({ type: 'status', data: data });
    })
    .catch(function(err) {
        // Silent fail - will retry
    });
    
    // Schedule next poll
    setTimeout(poll, 2000);
}

// Start polling immediately
poll();
