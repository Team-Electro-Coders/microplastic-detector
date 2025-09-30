/**
 * ESP32 Microplastic Detector - Dashboard JavaScript
 * Enhanced with real-time updates and interactive features
 */

class MicroplasticDashboard {
    constructor() {
        this.isPlaying = true;
        this.sessionStartTime = Date.now();
        this.currentStats = {};
        this.historicalData = [];
        this.charts = {};
        this.calibrationPoints = [];
        
        // Update intervals
        this.statsUpdateInterval = 1000; // 1 second
        this.chartUpdateInterval = 5000; // 5 seconds
        
        this.init();
    }

    init() {
        console.log('Initializing Microplastic Dashboard...');
        
        // Initialize event listeners
        this.setupEventListeners();
        
        // Initialize charts
        this.initializeCharts();
        
        // Start update loops
        this.startUpdateLoops();
        
        // Setup WebSocket connection
        this.setupWebSocket();

        // Theme toggle state
        this.initTheme();
        
        console.log('Dashboard initialized successfully');
    }

    setupEventListeners() {
        // Video controls
        document.getElementById('play-pause-btn').addEventListener('click', () => this.togglePlayPause());
        document.getElementById('snapshot-btn').addEventListener('click', () => this.takeSnapshot());
        document.getElementById('calibrate-btn').addEventListener('click', () => this.openCalibrationModal());
        
        // Settings and modals
        document.getElementById('settings-btn').addEventListener('click', () => this.openSettingsModal());
        document.getElementById('fullscreen-btn').addEventListener('click', () => this.toggleFullscreen());
        const themeToggle = document.getElementById('theme-toggle');
        if (themeToggle) themeToggle.addEventListener('click', () => this.toggleTheme());
        
        // Detection mode control
        document.getElementById('detection-mode').addEventListener('change', (e) => this.changeDetectionMode(e.target.value));
        
        // Parameter sliders
        this.setupParameterSliders();
        
        // Export controls
        document.getElementById('export-current-btn').addEventListener('click', () => this.exportCurrent());
        document.getElementById('export-range-btn').addEventListener('click', () => this.exportRange());
        document.getElementById('generate-report-btn').addEventListener('click', () => this.generateReport());
        
        // Modal controls
        this.setupModalControls();
        
        // Chart range selectors
        document.getElementById('size-chart-range').addEventListener('change', () => this.updateSizeChart());
        document.getElementById('count-chart-range').addEventListener('change', () => this.updateCountChart());
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => this.handleKeyboardShortcuts(e));
    }

    setupParameterSliders() {
        const sliders = [
            { id: 'threshold-slider', valueId: 'threshold-value' },
            { id: 'min-area-slider', valueId: 'min-area-value' },
            { id: 'max-area-slider', valueId: 'max-area-value' }
        ];

        sliders.forEach(slider => {
            const sliderEl = document.getElementById(slider.id);
            const valueEl = document.getElementById(slider.valueId);
            
            sliderEl.addEventListener('input', (e) => {
                valueEl.textContent = e.target.value;
                this.updateDetectionParameter(slider.id.replace('-slider', ''), e.target.value);
            });
        });

        // Reset and save buttons
        document.getElementById('reset-params-btn').addEventListener('click', () => this.resetParameters());
        document.getElementById('save-params-btn').addEventListener('click', () => this.saveParameters());
    }

    setupModalControls() {
        // Close modal buttons
        document.querySelectorAll('.close-modal').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.target.closest('.modal').style.display = 'none';
            });
        });

        // Close modals when clicking outside
        window.addEventListener('click', (e) => {
            if (e.target.classList.contains('modal')) {
                e.target.style.display = 'none';
            }
        });

        // Settings modal tabs
        document.querySelectorAll('.tab-button').forEach(btn => {
            btn.addEventListener('click', (e) => this.switchSettingsTab(e.target.dataset.tab));
        });

        // Calibration
        document.getElementById('calculate-scale').addEventListener('click', () => this.calculateScale());
        
        // Settings save/cancel
        document.getElementById('save-settings').addEventListener('click', () => this.saveSettings());
        document.getElementById('cancel-settings').addEventListener('click', () => this.cancelSettings());
    }

    initializeCharts() {
        // Size distribution histogram
        const sizeCtx = document.getElementById('size-distribution-chart').getContext('2d');
        this.charts.sizeDistribution = new Chart(sizeCtx, {
            type: 'bar',
            data: {
                labels: [],
                datasets: [{
                    label: 'Particle Count',
                    data: [],
                    backgroundColor: 'rgba(54, 162, 235, 0.6)',
                    borderColor: 'rgba(54, 162, 235, 1)',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        title: { display: true, text: 'Count' }
                    },
                    x: {
                        title: { display: true, text: 'Size Range (mm)' }
                    }
                },
                plugins: {
                    title: {
                        display: true,
                        text: 'Particle Size Distribution'
                    }
                }
            }
        });

        // Count over time line chart
        const countCtx = document.getElementById('count-over-time-chart').getContext('2d');
        this.charts.countOverTime = new Chart(countCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    {
                        label: 'Particle Count',
                        data: [],
                        borderColor: 'rgba(255, 99, 132, 1)',
                        backgroundColor: 'rgba(255, 99, 132, 0.2)',
                        fill: true,
                        tension: 0.1
                    },
                    {
                        label: 'Concentration (particles/mL)',
                        data: [],
                        borderColor: 'rgba(75, 192, 192, 1)',
                        backgroundColor: 'rgba(75, 192, 192, 0.2)',
                        fill: false,
                        yAxisID: 'y1'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                scales: {
                    x: {
                        display: true,
                        title: { display: true, text: 'Time' }
                    },
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        title: { display: true, text: 'Count' }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        title: { display: true, text: 'Concentration (particles/mL)' },
                        grid: { drawOnChartArea: false },
                    }
                }
            }
        });
    }

    startUpdateLoops() {
        // Stats update loop
        this.statsInterval = setInterval(() => {
            this.updateStats();
            this.updateSessionTime();
        }, this.statsUpdateInterval);

        // Charts update loop
        this.chartsInterval = setInterval(() => {
            this.updateCharts();
        }, this.chartUpdateInterval);

        // Status check loop
        this.statusInterval = setInterval(() => {
            this.checkSystemStatus();
            this.updateFooterUptime();
        }, 5000);

        // History refresh loop
        this.historyInterval = setInterval(() => {
            this.populateHistoryTable(60);
        }, 10000);

        // Initial population
        this.populateHistoryTable(60);
    }

    initTheme() {
        const saved = localStorage.getItem('mp_theme') || 'dark';
        document.documentElement.dataset.theme = saved;
        const icon = document.querySelector('#theme-toggle i');
        if (icon) icon.className = saved === 'dark' ? 'fas fa-moon' : 'fas fa-sun';
    }

    toggleTheme() {
        const current = document.documentElement.dataset.theme || 'dark';
        const next = current === 'dark' ? 'light' : 'dark';
        document.documentElement.dataset.theme = next;
        localStorage.setItem('mp_theme', next);
        const icon = document.querySelector('#theme-toggle i');
        if (icon) icon.className = next === 'dark' ? 'fas fa-moon' : 'fas fa-sun';
    }

    setupWebSocket() {
        // WebSocket for real-time updates (if available)
        try {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws`;
            this.ws = new WebSocket(wsUrl);
            
            this.ws.onopen = () => {
                console.log('WebSocket connected');
                this.updateConnectionStatus('websocket', true);
            };
            
            this.ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleWebSocketMessage(data);
            };
            
            this.ws.onclose = () => {
                console.log('WebSocket disconnected, falling back to polling');
                this.updateConnectionStatus('websocket', false);
            };
            
            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.updateConnectionStatus('websocket', false);
            };
        } catch (error) {
            console.log('WebSocket not available, using polling only');
        }
    }

    async updateStats() {
        try {
            const response = await fetch(`/api/stats?_=${Date.now()}`);
            const data = await response.json();
            
            if (response.ok) {
                this.currentStats = data;
                this.updateStatsDisplay(data);
                this.historicalData.push({
                    timestamp: new Date(),
                    ...data
                });
                
                // Keep only last 1000 data points
                if (this.historicalData.length > 1000) {
                    this.historicalData.shift();
                }
            }
        } catch (error) {
            console.error('Error updating stats:', error);
            this.updateConnectionStatus('api', false);
        }
    }

    updateStatsDisplay(data) {
        document.getElementById('particle-count').textContent = data.particle_count || 0;
        document.getElementById('average-size').textContent = (data.mean_size_mm || 0).toFixed(2);
        document.getElementById('concentration').textContent = Math.round(data.concentration_per_ml || 0);
        document.getElementById('fps-display').textContent = `${(data.fps || 0).toFixed(1)} FPS`;
        const kpiFps = document.getElementById('kpi-fps');
        if (kpiFps) kpiFps.textContent = (data.fps || 0).toFixed(1);
        const kpiCount = document.getElementById('kpi-count');
        if (kpiCount) kpiCount.textContent = data.particle_count || 0;
        
        // Update connection status
        this.updateConnectionStatus('camera', data.fps > 0);
    }

    updateSessionTime() {
        const elapsed = Date.now() - this.sessionStartTime;
        const hours = Math.floor(elapsed / 3600000);
        const minutes = Math.floor((elapsed % 3600000) / 60000);
        const seconds = Math.floor((elapsed % 60000) / 1000);
        
        document.getElementById('session-time').textContent = 
            `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    }

    async updateCharts() {
        this.updateSizeChart();
        this.updateCountChart();
    }

    updateSizeChart() {
        if (!this.currentStats.particles_sizes) return;
        
        const sizes = this.currentStats.particles_sizes;
        const range = document.getElementById('size-chart-range').value;
        
        // Create size bins
        const bins = this.createSizeBins(sizes, 0, 2.0, 0.2); // 0-2mm in 0.2mm bins
        
        this.charts.sizeDistribution.data.labels = bins.labels;
        this.charts.sizeDistribution.data.datasets[0].data = bins.data;
        this.charts.sizeDistribution.update('none');
    }

    updateCountChart() {
        const range = document.getElementById('count-chart-range').value;
        const data = this.getDataForTimeRange(range);
        
        if (data.length === 0) return;
        
        const labels = data.map(d => d.timestamp.toLocaleTimeString());
        const counts = data.map(d => d.particle_count || 0);
        const concentrations = data.map(d => d.concentration_per_ml || 0);
        
        this.charts.countOverTime.data.labels = labels;
        this.charts.countOverTime.data.datasets[0].data = counts;
        this.charts.countOverTime.data.datasets[1].data = concentrations;
        this.charts.countOverTime.update('none');
    }

    // Populate a history table from server logs
    async populateHistoryTable(minutes = 60) {
        try {
            const res = await fetch(`/api/history?minutes=${minutes}`);
            const rows = await res.json();
            const container = document.getElementById('history-table');
            if (!container) return;
            const header = `
                <div class="table-row table-header">
                    <div>Timestamp</div>
                    <div>Count</div>
                    <div>Mean Size (mm)</div>
                    <div>Std (mm)</div>
                    <div>Concentration (/mL)</div>
                    <div>Status</div>
                </div>`;
            const body = (rows || []).map(r => `
                <div class="table-row">
                    <div>${r.timestamp || ''}</div>
                    <div>${r.particle_count ?? 0}</div>
                    <div>${(r.mean_size_mm ?? 0).toFixed(3)}</div>
                    <div>${(r.std_size_mm ?? 0).toFixed(3)}</div>
                    <div>${(r.concentration_per_ml ?? 0).toFixed(1)}</div>
                    <div>${r.status || '-'}</div>
                </div>`).join('');
            container.innerHTML = header + body;
        } catch (e) {
            console.error('Failed to load history:', e);
        }
    }

    createSizeBins(sizes, min, max, binSize) {
        const numBins = Math.ceil((max - min) / binSize);
        const bins = new Array(numBins).fill(0);
        const labels = [];
        
        for (let i = 0; i < numBins; i++) {
            const start = min + i * binSize;
            const end = start + binSize;
            labels.push(`${start.toFixed(1)}-${end.toFixed(1)}`);
        }
        
        sizes.forEach(size => {
            const binIndex = Math.floor((size - min) / binSize);
            if (binIndex >= 0 && binIndex < numBins) {
                bins[binIndex]++;
            }
        });
        
        return { labels, data: bins };
    }

    getDataForTimeRange(range) {
        const now = new Date();
        let startTime;
        
        switch (range) {
            case '1min': startTime = new Date(now - 60000); break;
            case '5min': startTime = new Date(now - 300000); break;
            case '30min': startTime = new Date(now - 1800000); break;
            case 'session': startTime = new Date(this.sessionStartTime); break;
            default: startTime = new Date(now - 300000);
        }
        
        return this.historicalData.filter(d => d.timestamp >= startTime);
    }

    async checkSystemStatus() {
        try {
            // Check ESP32 status
            const esp32Response = await fetch(`http://${window.esp32_ip || '192.168.4.1'}/status`);
            this.updateConnectionStatus('esp32', esp32Response.ok);
            const badge = document.getElementById('badge-esp');
            if (badge) {
                badge.textContent = esp32Response.ok ? 'Connected' : 'Disconnected';
                badge.style.background = esp32Response.ok ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)';
                badge.style.color = esp32Response.ok ? '#10b981' : '#ef4444';
            }
        } catch (error) {
            this.updateConnectionStatus('esp32', false);
            const badge = document.getElementById('badge-esp');
            if (badge) {
                badge.textContent = 'Disconnected';
                badge.style.background = 'rgba(239,68,68,0.15)';
                badge.style.color = '#ef4444';
            }
        }
    }

    updateFooterUptime() {
        fetch('/api/health')
            .then(r => r.json())
            .then(h => {
                const el = document.getElementById('footer-uptime');
                if (!el || !h.uptime_seconds) return;
                const secs = Math.floor(h.uptime_seconds);
                const hh = Math.floor(secs / 3600).toString().padStart(2, '0');
                const mm = Math.floor((secs % 3600) / 60).toString().padStart(2, '0');
                const ss = Math.floor(secs % 60).toString().padStart(2, '0');
                el.textContent = `Uptime: ${hh}:${mm}:${ss}`;
            })
            .catch(() => {});
    }

    updateConnectionStatus(component, isConnected) {
        const statusEl = document.getElementById(`${component}-status`);
        const textEl = document.getElementById(`${component}-text`);
        
        if (statusEl) {
            statusEl.classList.toggle('connected', isConnected);
            statusEl.classList.toggle('disconnected', !isConnected);
        }
        
        if (textEl) {
            const statusText = {
                esp32: isConnected ? 'Connected' : 'Disconnected',
                camera: isConnected ? 'Active' : 'No Signal',
                api: isConnected ? 'Online' : 'Error',
                websocket: isConnected ? 'Real-time' : 'Polling'
            };
            textEl.textContent = statusText[component] || (isConnected ? 'OK' : 'Error');
        }
    }

    togglePlayPause() {
        this.isPlaying = !this.isPlaying;
        const btn = document.getElementById('play-pause-btn');
        const icon = btn.querySelector('i');
        
        if (this.isPlaying) {
            icon.className = 'fas fa-pause';
            document.getElementById('video-feed').style.display = 'block';
        } else {
            icon.className = 'fas fa-play';
            document.getElementById('video-feed').style.display = 'none';
        }
    }

    async takeSnapshot() {
        try {
            const response = await fetch('/api/snapshot', { method: 'POST' });
            const result = await response.json();
            
            if (result.success) {
                this.showNotification('Snapshot saved successfully', 'success');
            } else {
                this.showNotification('Failed to save snapshot', 'error');
            }
        } catch (error) {
            this.showNotification('Error taking snapshot', 'error');
        }
    }

    openCalibrationModal() {
        const modal = document.getElementById('calibration-modal');
        modal.style.display = 'flex';
        this.setupCalibrationCanvas();
    }

    setupCalibrationCanvas() {
        const canvas = document.getElementById('calibration-canvas');
        const ctx = canvas.getContext('2d');
        
        // Get current frame for calibration
        const img = document.getElementById('video-feed');
        canvas.width = img.naturalWidth || 640;
        canvas.height = img.naturalHeight || 480;
        
        ctx.drawImage(img, 0, 0);
        
        this.calibrationPoints = [];
        
        canvas.addEventListener('click', (e) => {
            const rect = canvas.getBoundingClientRect();
            const x = (e.clientX - rect.left) * (canvas.width / rect.width);
            const y = (e.clientY - rect.top) * (canvas.height / rect.height);
            
            this.calibrationPoints.push({ x, y });
            
            // Draw point
            ctx.fillStyle = 'red';
            ctx.beginPath();
            ctx.arc(x, y, 5, 0, 2 * Math.PI);
            ctx.fill();
            
            // Draw line if we have 2 points
            if (this.calibrationPoints.length === 2) {
                ctx.strokeStyle = 'red';
                ctx.lineWidth = 2;
                ctx.beginPath();
                ctx.moveTo(this.calibrationPoints[0].x, this.calibrationPoints[0].y);
                ctx.lineTo(this.calibrationPoints[1].x, this.calibrationPoints[1].y);
                ctx.stroke();
                
                // Calculate pixel distance
                const dx = this.calibrationPoints[1].x - this.calibrationPoints[0].x;
                const dy = this.calibrationPoints[1].y - this.calibrationPoints[0].y;
                const pixelDistance = Math.sqrt(dx * dx + dy * dy);
                
                // Show distance info
                ctx.fillStyle = 'black';
                ctx.font = '16px Arial';
                ctx.fillText(`${pixelDistance.toFixed(1)} pixels`, 10, 30);
                
                document.getElementById('calculate-scale').disabled = false;
            }
            
            if (this.calibrationPoints.length > 2) {
                // Reset if more than 2 points
                this.calibrationPoints = [];
                this.setupCalibrationCanvas();
            }
        });
    }

    async calculateScale() {
        if (this.calibrationPoints.length !== 2) {
            this.showNotification('Please click exactly 2 points', 'error');
            return;
        }
        
        const actualDistance = parseFloat(document.getElementById('actual-distance').value);
        if (isNaN(actualDistance) || actualDistance <= 0) {
            this.showNotification('Please enter a valid distance', 'error');
            return;
        }
        
        const dx = this.calibrationPoints[1].x - this.calibrationPoints[0].x;
        const dy = this.calibrationPoints[1].y - this.calibrationPoints[0].y;
        const pixelDistance = Math.sqrt(dx * dx + dy * dy);
        
        const scale = actualDistance / pixelDistance;
        
        try {
            const response = await fetch('/api/calibrate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    scale_mm_per_pixel: scale,
                    pixel_distance: pixelDistance,
                    actual_distance_mm: actualDistance
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showNotification(`Calibration updated: ${scale.toFixed(6)} mm/pixel`, 'success');
                document.getElementById('calibration-modal').style.display = 'none';
            } else {
                this.showNotification('Calibration failed', 'error');
            }
        } catch (error) {
            this.showNotification('Error updating calibration', 'error');
        }
    }

    openSettingsModal() {
        const modal = document.getElementById('settings-modal');
        modal.style.display = 'flex';
        this.loadSettingsContent('detection');
    }

    async loadSettingsContent(tab) {
        try {
            const response = await fetch(`/api/settings/${tab}`);
            const settings = await response.json();
            
            const content = document.getElementById('settings-content');
            content.innerHTML = this.generateSettingsHTML(tab, settings);
            
            // Activate tab
            document.querySelectorAll('.tab-button').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.tab === tab);
            });
        } catch (error) {
            console.error('Error loading settings:', error);
        }
    }

    generateSettingsHTML(tab, settings) {
        switch (tab) {
            case 'detection':
                return `
                    <div class="settings-group">
                        <h4>Detection Parameters</h4>
                        <div class="setting-item">
                            <label>Scale (mm/pixel):</label>
                            <input type="number" id="setting-scale" value="${settings.scale_mm_per_pixel || 0.01}" step="0.000001">
                        </div>
                        <div class="setting-item">
                            <label>Threshold Value:</label>
                            <input type="range" id="setting-threshold" min="10" max="200" value="${settings.threshold_value || 60}">
                            <span class="range-value">${settings.threshold_value || 60}</span>
                        </div>
                        <div class="setting-item">
                            <label>Min Particle Area (px²):</label>
                            <input type="number" id="setting-min-area" value="${settings.min_particle_area || 50}">
                        </div>
                        <div class="setting-item">
                            <label>Max Particle Area (px²):</label>
                            <input type="number" id="setting-max-area" value="${settings.max_particle_area || 5000}">
                        </div>
                        <div class="setting-item">
                            <label>Gaussian Blur Kernel:</label>
                            <select id="setting-blur-kernel">
                                <option value="3" ${settings.gaussian_blur === 3 ? 'selected' : ''}>3x3</option>
                                <option value="5" ${settings.gaussian_blur === 5 ? 'selected' : ''}>5x5</option>
                                <option value="7" ${settings.gaussian_blur === 7 ? 'selected' : ''}>7x7</option>
                            </select>
                        </div>
                    </div>
                `;
            case 'camera':
                return `
                    <div class="settings-group">
                        <h4>Camera Settings</h4>
                        <div class="setting-item">
                            <label>Resolution:</label>
                            <select id="setting-resolution">
                                <option value="320x240">320x240</option>
                                <option value="640x480" selected>640x480</option>
                                <option value="1280x720">1280x720</option>
                                <option value="1920x1080">1920x1080</option>
                            </select>
                        </div>
                        <div class="setting-item">
                            <label>Frame Rate (FPS):</label>
                            <input type="number" id="setting-fps" value="${settings.fps || 30}" min="5" max="60">
                        </div>
                        <div class="setting-item">
                            <label>Brightness:</label>
                            <input type="range" id="setting-brightness" min="-100" max="100" value="${settings.brightness || 0}">
                            <span class="range-value">${settings.brightness || 0}</span>
                        </div>
                        <div class="setting-item">
                            <label>Contrast:</label>
                            <input type="range" id="setting-contrast" min="0" max="100" value="${settings.contrast || 32}">
                            <span class="range-value">${settings.contrast || 32}</span>
                        </div>
                    </div>
                `;
            case 'system':
                return `
                    <div class="settings-group">
                        <h4>System Configuration</h4>
                        <div class="setting-item">
                            <label>ESP32 IP Address:</label>
                            <input type="text" id="setting-esp32-ip" value="${settings.esp32_ip || '192.168.4.1'}">
                        </div>
                        <div class="setting-item">
                            <label>ESP32 Port:</label>
                            <input type="number" id="setting-esp32-port" value="${settings.esp32_port || 80}">
                        </div>
                        <div class="setting-item">
                            <label>Sample Volume (mL):</label>
                            <input type="number" id="setting-sample-volume" value="${settings.sample_volume_ml || 0.05}" step="0.001">
                        </div>
                        <div class="setting-item">
                            <label>Auto-log Interval (seconds):</label>
                            <input type="number" id="setting-log-interval" value="${settings.auto_log_interval || 30}">
                        </div>
                        <div class="setting-item">
                            <label>Enable Debug Mode:</label>
                            <input type="checkbox" id="setting-debug-mode" ${settings.debug ? 'checked' : ''}>
                        </div>
                    </div>
                `;
            default:
                return '<p>Settings not available</p>';
        }
    }

    switchSettingsTab(tab) {
        this.loadSettingsContent(tab);
    }

    async saveSettings() {
        const settings = this.collectSettingsFromForm();
        
        try {
            const response = await fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings)
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showNotification('Settings saved successfully', 'success');
                document.getElementById('settings-modal').style.display = 'none';
            } else {
                this.showNotification('Failed to save settings', 'error');
            }
        } catch (error) {
            this.showNotification('Error saving settings', 'error');
        }
    }

    collectSettingsFromForm() {
        const settings = {};
        
        // Collect all input values
        document.querySelectorAll('#settings-content input, #settings-content select').forEach(input => {
            const key = input.id.replace('setting-', '');
            
            if (input.type === 'checkbox') {
                settings[key] = input.checked;
            } else if (input.type === 'number') {
                settings[key] = parseFloat(input.value);
            } else {
                settings[key] = input.value;
            }
        });
        // Normalize keys to backend expectations
        if (settings['esp32-ip']) {
            settings['esp32_ip'] = settings['esp32-ip'];
            delete settings['esp32-ip'];
        }
        if (settings['esp32-port'] !== undefined) {
            settings['esp32_port'] = settings['esp32-port'];
            delete settings['esp32-port'];
        }
        
        return settings;
    }

    cancelSettings() {
        document.getElementById('settings-modal').style.display = 'none';
    }

    async changeDetectionMode(mode) {
        try {
            const response = await fetch(`/api/mode/${mode}`, { method: 'POST' });
            
            if (response.ok) {
                this.showNotification(`Mode changed to ${mode}`, 'success');
            } else {
                this.showNotification('Failed to change mode', 'error');
            }
        } catch (error) {
            this.showNotification('Error changing mode', 'error');
        }
    }

    async updateDetectionParameter(param, value) {
        try {
            const response = await fetch('/api/parameter', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ [param]: parseFloat(value) })
            });
            
            if (!response.ok) {
                console.error('Failed to update parameter:', param);
            }
        } catch (error) {
            console.error('Error updating parameter:', error);
        }
    }

    async resetParameters() {
        try {
            const response = await fetch('/api/reset-parameters', { method: 'POST' });
            
            if (response.ok) {
                // Reset UI sliders to defaults
                document.getElementById('threshold-slider').value = 60;
                document.getElementById('threshold-value').textContent = '60';
                document.getElementById('min-area-slider').value = 50;
                document.getElementById('min-area-value').textContent = '50';
                document.getElementById('max-area-slider').value = 5000;
                document.getElementById('max-area-value').textContent = '5000';
                
                this.showNotification('Parameters reset to defaults', 'success');
            }
        } catch (error) {
            this.showNotification('Error resetting parameters', 'error');
        }
    }

    async saveParameters() {
        const params = {
            threshold: document.getElementById('threshold-slider').value,
            min_area: document.getElementById('min-area-slider').value,
            max_area: document.getElementById('max-area-slider').value
        };
        
        try {
            const response = await fetch('/api/save-parameters', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(params)
            });
            
            if (response.ok) {
                this.showNotification('Parameters saved successfully', 'success');
            }
        } catch (error) {
            this.showNotification('Error saving parameters', 'error');
        }
    }

    async exportCurrent() {
        try {
            const response = await fetch('/api/export/current');
            const blob = await response.blob();
            
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `microplastic_current_${new Date().toISOString().split('T')[0]}.csv`;
            a.click();
            
            window.URL.revokeObjectURL(url);
            this.showNotification('Current data exported', 'success');
        } catch (error) {
            this.showNotification('Error exporting data', 'error');
        }
    }

    async exportRange() {
        const startDate = document.getElementById('export-start').value;
        const endDate = document.getElementById('export-end').value;
        const format = document.getElementById('export-format-select').value;
        
        if (!startDate || !endDate) {
            this.showNotification('Please select date range', 'error');
            return;
        }
        
        try {
            const response = await fetch(`/api/export/range?start=${startDate}&end=${endDate}&format=${format}`);
            const blob = await response.blob();
            
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `microplastic_range_${startDate}_${endDate}.${format}`;
            a.click();
            
            window.URL.revokeObjectURL(url);
            this.showNotification('Range data exported', 'success');
        } catch (error) {
            this.showNotification('Error exporting range data', 'error');
        }
    }

    async generateReport() {
        try {
            const response = await fetch('/api/report/generate', { method: 'POST' });
            const result = await response.json();
            
            if (result.success) {
                // Open report in new tab
                window.open(result.report_url, '_blank');
                this.showNotification('Report generated successfully', 'success');
            }
        } catch (error) {
            this.showNotification('Error generating report', 'error');
        }
    }

    toggleFullscreen() {
        if (!document.fullscreenElement) {
            document.documentElement.requestFullscreen();
        } else {
            document.exitFullscreen();
        }
    }

    handleKeyboardShortcuts(e) {
        // Ctrl/Cmd shortcuts
        if (e.ctrlKey || e.metaKey) {
            switch (e.key) {
                case 's': // Save snapshot
                    e.preventDefault();
                    this.takeSnapshot();
                    break;
                case 'c': // Calibrate
                    e.preventDefault();
                    this.openCalibrationModal();
                    break;
                case 'e': // Export
                    e.preventDefault();
                    this.exportCurrent();
                    break;
            }
        }
        
        // Function keys
        switch (e.key) {
            case 'F11': // Fullscreen
                e.preventDefault();
                this.toggleFullscreen();
                break;
            case ' ': // Space - Play/Pause
                e.preventDefault();
                this.togglePlayPause();
                break;
            case 'Escape': // Close modals
                document.querySelectorAll('.modal').forEach(modal => {
                    modal.style.display = 'none';
                });
                break;
        }
    }

    showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.innerHTML = `
            <i class="fas fa-${type === 'success' ? 'check' : type === 'error' ? 'times' : 'info'}-circle"></i>
            <span>${message}</span>
        `;
        
        // Add to page
        document.body.appendChild(notification);
        
        // Show with animation
        setTimeout(() => notification.classList.add('show'), 100);
        
        // Remove after 3 seconds
        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => document.body.removeChild(notification), 300);
        }, 3000);
    }

    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'stats_update':
                this.currentStats = data.payload;
                this.updateStatsDisplay(data.payload);
                break;
            case 'system_status':
                this.updateConnectionStatus('esp32', data.payload.esp32_connected);
                break;
            case 'notification':
                this.showNotification(data.payload.message, data.payload.type);
                break;
        }
    }

    destroy() {
        // Clean up intervals and connections
        if (this.statsInterval) clearInterval(this.statsInterval);
        if (this.chartsInterval) clearInterval(this.chartsInterval);
        if (this.statusInterval) clearInterval(this.statusInterval);
        
        if (this.ws) {
            this.ws.close();
        }
        
        // Destroy charts
        Object.values(this.charts).forEach(chart => chart.destroy());
    }
}

// Initialize dashboard when page loads
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new MicroplasticDashboard();
});

// Clean up when page unloads
window.addEventListener('beforeunload', () => {
    if (window.dashboard) {
        window.dashboard.destroy();
    }
});