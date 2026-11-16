let config = { shots_required: 0 };
let currentShot = 0;
let capturedFiles = [];
let countdownInterval;
let selectedFrame = 'frame.png';

// Fetch config on load with cache busting
async function fetchConfig(frameFilename) {
    try {
        const response = await fetch(`/api/config?frame=${frameFilename}&t=` + new Date().getTime());
        const data = await response.json();
        config.shots_required = data.shots_required;
        console.log("Config loaded:", config);
    } catch (error) {
        console.error("Failed to fetch config:", error);
    }
}

async function selectFrame(frameFilename) {
    selectedFrame = frameFilename;
    await fetchConfig(frameFilename);
    transitionTo('instructions');
}

let liveViewInterval;

function startLiveView() {
    const img = document.getElementById('live-view');
    img.style.display = 'block';
    if (!liveViewInterval) {
        liveViewInterval = setInterval(() => {
            // Update the image source with a timestamp to fetch fresh snapshots
            img.src = "http://127.0.0.1:5513/liveview.jpg?t=" + new Date().getTime();
        }, 100); // 10 frames per second
    }
}

function stopLiveView() {
    const img = document.getElementById('live-view');
    img.style.display = 'none';
    if (liveViewInterval) {
        clearInterval(liveViewInterval);
        liveViewInterval = null;
    }
    img.src = "";
}

function transitionTo(stateId) {
    document.querySelectorAll('.state').forEach(el => el.classList.remove('active'));
    document.getElementById(`state-${stateId}`).classList.add('active');

    if (stateId === 'capture') {
        startLiveView();
    } else {
        stopLiveView();
    }

    if (stateId === 'idle') {
        // Reset states
        currentShot = 0;
        capturedFiles = [];
        document.getElementById('final-image').src = '';
        document.getElementById('qr-code').src = '';
    }
}

async function startCaptureLoop() {
    if (config.shots_required === 0) {
        alert("No valid cutouts detected in frame. Please check server logs.");
        transitionTo('idle');
        return;
    }
    transitionTo('capture');
    currentShot = 1;
    runShot();
}

function runShot() {
    startLiveView(); // Ensure live view is running for the countdown

    document.getElementById('shot-counter').innerText = `Shot ${currentShot} of ${config.shots_required}`;
    document.getElementById('spinner').style.display = 'none';
    const countdownEl = document.getElementById('countdown');
    countdownEl.style.display = 'block';
    
    // Set timer to 10 seconds, but fire the capture command early at 5 seconds
    let timeLeft = 10;
    countdownEl.innerText = timeLeft;
    
    let fetchPromise = null;

    countdownInterval = setInterval(async () => {
        timeLeft -= 1;
        countdownEl.innerText = timeLeft;

        // When visual timer hits 0, take photo and flash
        if (timeLeft <= 0) {
            clearInterval(countdownInterval);
            countdownEl.style.display = 'none';
            
            // Trigger flash immediately at 0 seconds
            triggerFlash();
            
            document.getElementById('spinner').style.display = 'block';
            
            // Stop polling Live View to free up USB bandwidth for the high-res photo transfer!
            stopLiveView();
            
            // Because RemoteCmd is instant, we capture exactly at 0s!
            fetchPromise = fetch('/api/capture', { method: 'POST' })
                .then(res => res.json())
                .catch(err => ({ status: 'error', message: err.toString() }));
            
            const data = await fetchPromise;
            handleCaptureResult(data);
        }
    }, 1000);
}

function handleCaptureResult(data) {
    if (data && data.status === 'success') {
        capturedFiles.push(data.filename);

        if (currentShot < config.shots_required) {
            currentShot++;
            // Slight delay before next countdown
            setTimeout(runShot, 1000);
        } else {
            processPhotos();
        }
    } else {
        console.error("Capture failed:", data ? data.message : "Unknown error");
        alert("Capture failed! Retrying this shot...");
        runShot(); // Retry
    }
}

function triggerFlash() {
    const flash = document.getElementById('flash');
    flash.classList.remove('flash-anim');
    void flash.offsetWidth; // trigger reflow
    flash.classList.add('flash-anim');
}

async function processPhotos() {
    transitionTo('processing');

    try {
        const response = await fetch('/api/process', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filenames: capturedFiles, frame: selectedFrame })
        });
        const data = await response.json();

        if (data.status === 'success') {
            document.getElementById('final-image').src = data.image_url;
            document.getElementById('qr-code').src = `data:image/png;base64,${data.qr_base64}`;
            transitionTo('result');
        } else {
            console.error("Processing failed:", data.message);
            alert("Processing failed. Please try again.");
            transitionTo('idle');
        }
    } catch (error) {
        console.error("Process API error:", error);
        alert("Process API error. Returning to idle.");
        transitionTo('idle');
    }
}
