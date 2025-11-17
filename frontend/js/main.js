const API_URL = window.APP_CONFIG.API_URL;

const socket = io(API_URL, {
    transports: ['polling', 'websocket'],
    upgrade: true,
    reconnection: true,
    reconnectionAttempts: 100,
    reconnectionDelay: 1000,
    timeout: 60000,
    autoConnect: true,
    withCredentials: true,
    path: '/socket.io/'
});

const statusDot = document.getElementById('statusDot');
const statusText = document.getElementById('statusText');
const removalForm = document.getElementById('removalForm');
const startBtn = document.getElementById('startBtn');
const btnText = document.getElementById('btnText');
const loader = document.getElementById('loader');
const progressCard = document.getElementById('progressCard');
const resultCard = document.getElementById('resultCard');
const log = document.getElementById('log');
const statTotal = document.getElementById('statTotal');
const statRemoved = document.getElementById('statRemoved');
const statFailed = document.getElementById('statFailed');
const progressFill = document.getElementById('progressFill');
const progressText = document.getElementById('progressText');

socket.on('connect', () => {
    statusDot.classList.add('online');
    statusText.textContent = 'Online';
});

socket.on('disconnect', () => {
    statusDot.classList.remove('online');
    statusText.textContent = 'Offline';
});

socket.on('reconnect_attempt', () => {
    statusDot.classList.remove('online');
    statusText.textContent = 'Reconnecting...';
});

socket.on('reconnect', () => {
    statusDot.classList.add('online');
    statusText.textContent = 'Online';
});

document.addEventListener('visibilitychange', () => {
    if (!document.hidden && !socket.connected) {
        socket.connect();
    }
});

removalForm.addEventListener('submit', (e) => {
    e.preventDefault();
    
    const cookies = document.getElementById('cookies').value.trim();
    const username = document.getElementById('username').value.trim();
    const voteType = document.querySelector('input[name="voteType"]:checked').value;
    const delay = parseFloat(document.getElementById('delay').value);

    if (!cookies || !username) {
        alert('Please fill in all required fields');
        return;
    }

    startBtn.disabled = true;
    btnText.textContent = 'Processing...';
    loader.style.display = 'inline-block';
    
    progressCard.style.display = 'block';
    resultCard.style.display = 'none';
    log.innerHTML = '';
    
    statTotal.textContent = '0';
    statRemoved.textContent = '0';
    statFailed.textContent = '0';
    progressFill.style.width = '0%';
    progressText.textContent = '0%';

    socket.emit('start_removal', {
        cookies,
        username,
        voteType,
        delay
    });
});

socket.on('progress', (data) => {
    if (data.url && data.post_id !== undefined && data.success !== undefined) {
        addPostLog(data.post_id, data.url, data.success, data.message);
    } else {
        addLog(data.message, data.status === 'success' ? 'success' : (data.status === 'error' ? 'error' : 'info'));
    }
    
    if (data.stats) {
        updateStats(data.stats);
    }
});

socket.on('complete', (data) => {
    startBtn.disabled = false;
    btnText.textContent = 'Start Removal';
    loader.style.display = 'none';
    
    addLog('✓ All done!', 'success');
    
    if (data.stats) {
        updateStats(data.stats);
    }
});

socket.on('error', (data) => {
    startBtn.disabled = false;
    btnText.textContent = 'Start Removal';
    loader.style.display = 'none';
    
    addLog(`Error: ${data.message}`, 'error');
    alert(`Error: ${data.message}`);
});

function addLog(message, type = 'info') {
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    const time = new Date().toLocaleTimeString();
    entry.textContent = `[${time}] ${message}`;
    log.appendChild(entry);
    log.scrollTop = log.scrollHeight;
}

function addPostLog(postId, url, success, message) {
    const entry = document.createElement('div');
    entry.className = `log-entry ${success ? 'success' : 'error'}`;
    const time = new Date().toLocaleTimeString();
    entry.innerHTML = `[${time}] <a href="${url}" target="_blank" rel="noopener noreferrer" style="color:inherit;text-decoration:underline;font-weight:bold;">${url}</a> - ${success ? '✓ REMOVED' : '✗ FAILED'}`;
    log.appendChild(entry);
    log.scrollTop = log.scrollHeight;
}

function updateStats(stats) {
    if (!stats) return;
    if ('total' in stats) statTotal.textContent = stats.total;
    if ('removed' in stats) statRemoved.textContent = stats.removed;
    if ('failed' in stats) statFailed.textContent = stats.failed;
    let percentage = stats.total > 0
        ? Math.round((stats.removed + stats.failed) / stats.total * 100)
        : 0;
    progressFill.style.width = percentage + '%';
    progressText.textContent = percentage + '%';
}

