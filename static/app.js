document.addEventListener('DOMContentLoaded', () => {
    // Elements
    const statSent = document.getElementById('stat-sent');
    const statQueued = document.getElementById('stat-queued');
    const statFailed = document.getElementById('stat-failed');
    const statBlocked = document.getElementById('stat-blocked');
    
    const ruleForm = document.getElementById('rule-form');
    const rulesList = document.getElementById('rules-list');

    const setupForm = document.getElementById('setup-form');
    const simulateForm = document.getElementById('simulate-form');

    // Chart Setup
    const ctx = document.getElementById('throughputChart').getContext('2d');
    const chart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                { label: 'Sent', data: [], borderColor: '#10b981', backgroundColor: 'transparent', borderDash: [2, 2], tension: 0.1, borderWidth: 1, pointRadius: 2, pointBackgroundColor: '#10b981' },
                { label: 'Queued', data: [], borderColor: '#f59e0b', backgroundColor: 'transparent', borderDash: [2, 2], tension: 0.1, borderWidth: 1, pointRadius: 2, pointBackgroundColor: '#f59e0b' }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 0 },
            interaction: { mode: 'index', intersect: false },
            scales: {
                x: { display: false },
                y: { beginAtZero: true, grid: { color: '#282e3e' }, border: { display: false }, ticks: { color: '#9ca3af', font: { size: 10 } } }
            },
            plugins: {
                legend: { position: 'top', align: 'center', labels: { color: '#ffffff', boxWidth: 6, usePointStyle: true, pointStyle: 'circle', padding: 20 } }
            }
        }
    });

    // Fetch and display stats
    async function fetchStats() {
        try {
            const res = await fetch('/stats');
            if (res.ok) {
                const data = await res.json();
                
                // Animate numbers if they changed
                updateNumber(statSent, data.sent);
                updateNumber(statQueued, data.queued);
                updateNumber(statFailed, data.failed);
                updateNumber(statBlocked, data.duplicates_blocked);
                
                // Update chart
                const timeStr = new Date().toLocaleTimeString();
                chart.data.labels.push(timeStr);
                chart.data.datasets[0].data.push(data.sent);
                chart.data.datasets[1].data.push(data.queued);
                
                // Keep only last 20 data points
                if (chart.data.labels.length > 20) {
                    chart.data.labels.shift();
                    chart.data.datasets.forEach(d => d.data.shift());
                }
                chart.update();
            }
        } catch (error) {
            console.error('Failed to fetch stats', error);
        }
    }

    // Update number with a subtle bounce effect if changed
    function updateNumber(el, newValue) {
        if (el.innerText !== String(newValue)) {
            el.innerText = newValue;
            el.style.transform = 'scale(1.2)';
            setTimeout(() => {
                el.style.transform = 'scale(1)';
            }, 200);
        }
    }

    // Fetch and display rules
    async function fetchRules() {
        try {
            const res = await fetch('/rules');
            const rules = await res.json();
            
            if (rules.length === 0) {
                rulesList.innerHTML = '<div class="empty">No rules created yet.</div>';
                return;
            }

            rulesList.innerHTML = rules.map(rule => `
                <div class="rule-item">
                    <div class="rule-item-left">
                        <div class="rule-keyword">${escapeHTML(rule.keyword)}</div>
                        <div class="rule-msg">${escapeHTML(rule.dm_message)}</div>
                    </div>
                    <div class="rule-actions">
                        <i class="fa-solid fa-pen"></i>
                        <i class="fa-solid fa-trash"></i>
                    </div>
                </div>
            `).join('');
        } catch (error) {
            console.error('Failed to fetch rules', error);
            rulesList.innerHTML = '<div class="empty" style="color: var(--danger)">Failed to load rules.</div>';
        }
    }

    // Handle rule creation
    ruleForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const keyword = document.getElementById('keyword').value;
        const message = document.getElementById('message').value;
        const btn = ruleForm.querySelector('button');

        const originalText = btn.innerText;
        btn.innerText = 'Adding...';
        btn.disabled = true;

        try {
            const res = await fetch('/rules', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ keyword, dm_message: message })
            });

            if (res.ok) {
                document.getElementById('keyword').value = '';
                document.getElementById('message').value = '';
                fetchRules(); // refresh list
            } else {
                alert('Failed to add rule.');
            }
        } catch (error) {
            console.error(error);
            alert('Error adding rule.');
        } finally {
            btn.innerText = originalText;
            btn.disabled = false;
        }
    });

    // Handle Setup Form
    setupForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const btn = setupForm.querySelector('button');
        const originalText = btn.innerText;
        btn.innerText = 'Setting up...';
        btn.disabled = true;

        const payload = {
            name: document.getElementById('setup-name').value,
            email: document.getElementById('setup-email').value,
            phone: document.getElementById('setup-phone').value,
            linkedin_url: document.getElementById('setup-linkedin').value
        };

        try {
            const res = await fetch('/ui/setup', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                const data = await res.json();
                alert('Success! API Key acquired and saved: ' + data.api_key);
                btn.innerText = 'Key Configured!';
                btn.style.backgroundColor = 'var(--text-secondary)';
            } else {
                const err = await res.json();
                alert('Failed: ' + (err.detail || 'Unknown error'));
                btn.innerText = originalText;
                btn.disabled = false;
            }
        } catch (error) {
            console.error(error);
            alert('Error setting up API key.');
            btn.innerText = originalText;
            btn.disabled = false;
        }
    });

    // Handle Simulate Form
    simulateForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const btn = simulateForm.querySelector('button');
        const originalText = btn.innerText;
        btn.innerText = 'Starting...';
        btn.disabled = true;

        const webhook_url = document.getElementById('sim-url').value;

        try {
            const res = await fetch('/ui/simulate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ webhook_url })
            });

            if (res.ok) {
                const data = await res.json();
                alert('Simulation Started! Run ID: ' + data.run_id + '\nWatch your dashboard stats!');
                btn.innerText = 'Simulation Running...';
                setTimeout(() => {
                    btn.innerText = originalText;
                    btn.disabled = false;
                }, 10000); // Reset after 10s (the duration of the simulation)
            } else {
                const err = await res.json();
                alert('Failed: ' + (err.detail || 'Unknown error'));
                btn.innerText = originalText;
                btn.disabled = false;
            }
        } catch (error) {
            console.error(error);
            alert('Error starting simulation.');
            btn.innerText = originalText;
            btn.disabled = false;
        }
    });

    function escapeHTML(str) {
        return str.replace(/[&<>'"]/g, 
            tag => ({
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                "'": '&#39;',
                '"': '&quot;'
            }[tag] || tag)
        );
    }

    // WebSocket Connection
    let ws;
    function connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        ws = new WebSocket(`${protocol}//${window.location.host}/ws`);
        
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === "log") {
                appendLog(data.message, data.level);
            } else if (data.type === "update_stats") {
                fetchStats();
            }
        };

        ws.onclose = () => {
            setTimeout(connectWebSocket, 3000); // Reconnect
        };
    }

    const activityStream = document.getElementById('activity-stream');
    
    function appendLog(message, level) {
        const el = document.createElement('div');
        el.className = `log-entry ${level.toLowerCase()}`;
        const time = new Date().toLocaleTimeString();
        el.innerText = `[${time}] [${level}] ${message}`;
        activityStream.appendChild(el);
        
        // Auto-scroll to bottom
        activityStream.scrollTop = activityStream.scrollHeight;
        
        // Keep only last 100 logs
        if (activityStream.children.length > 100) {
            activityStream.removeChild(activityStream.firstChild);
        }
    }

    // Initial load
    fetchStats();
    fetchRules();
    connectWebSocket();

    // No need to poll every 2s anymore since we have WebSockets, but we keep a slow fallback just in case
    setInterval(fetchStats, 10000);
});
