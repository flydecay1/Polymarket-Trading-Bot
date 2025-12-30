"""Simple web dashboard for monitoring bot performance."""
from flask import Flask, jsonify, render_template_string
from typing import Optional
import structlog

logger = structlog.get_logger(__name__)


class Dashboard:
    """Web dashboard for bot monitoring."""

    def __init__(self, port: int = 5000):
        """Initialize dashboard.

        Args:
            port: Port to run dashboard on
        """
        self.app = Flask(__name__)
        self.port = port
        self.engine = None
        self.performance_tracker = None

        self._setup_routes()

    def set_engine(self, engine) -> None:
        """Set reference to arbitrage engine.

        Args:
            engine: ArbitrageEngine instance
        """
        self.engine = engine

    def set_performance_tracker(self, tracker) -> None:
        """Set reference to performance tracker.

        Args:
            tracker: PerformanceTracker instance
        """
        self.performance_tracker = tracker

    def _setup_routes(self) -> None:
        """Set up Flask routes."""

        @self.app.route('/')
        def index():
            """Main dashboard page."""
            html = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Polymarket Arbitrage Bot Dashboard</title>
                <meta http-equiv="refresh" content="5">
                <style>
                    body {
                        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                        background: #1a1a2e;
                        color: #eee;
                        margin: 0;
                        padding: 20px;
                    }
                    .container {
                        max-width: 1200px;
                        margin: 0 auto;
                    }
                    h1 {
                        color: #00ff88;
                        border-bottom: 2px solid #00ff88;
                        padding-bottom: 10px;
                    }
                    .metrics {
                        display: grid;
                        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                        gap: 20px;
                        margin: 20px 0;
                    }
                    .metric-card {
                        background: #16213e;
                        padding: 20px;
                        border-radius: 8px;
                        border-left: 4px solid #00ff88;
                    }
                    .metric-label {
                        color: #aaa;
                        font-size: 12px;
                        text-transform: uppercase;
                        margin-bottom: 5px;
                    }
                    .metric-value {
                        font-size: 28px;
                        font-weight: bold;
                        color: #00ff88;
                    }
                    .status-running { color: #00ff88; }
                    .status-stopped { color: #ff4444; }
                    .positive { color: #00ff88; }
                    .negative { color: #ff4444; }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>🚀 Polymarket Arbitrage Bot</h1>
                    <div id="status"></div>
                    <div id="metrics"></div>
                </div>
                <script>
                    async function updateDashboard() {
                        try {
                            const response = await fetch('/api/status');
                            const data = await response.json();

                            document.getElementById('status').innerHTML = `
                                <h2>Status: <span class="status-${data.status.running ? 'running' : 'stopped'}">
                                    ${data.status.running ? 'Running ✓' : 'Stopped ✗'}
                                </span></h2>
                            `;

                            const metrics = data.performance || {};
                            const pnlClass = metrics.total_pnl >= 0 ? 'positive' : 'negative';

                            document.getElementById('metrics').innerHTML = `
                                <div class="metrics">
                                    <div class="metric-card">
                                        <div class="metric-label">Total Trades</div>
                                        <div class="metric-value">${metrics.total_trades || 0}</div>
                                    </div>
                                    <div class="metric-card">
                                        <div class="metric-label">Win Rate</div>
                                        <div class="metric-value">${((metrics.win_rate || 0) * 100).toFixed(1)}%</div>
                                    </div>
                                    <div class="metric-card">
                                        <div class="metric-label">Total P&L</div>
                                        <div class="metric-value ${pnlClass}">$${(metrics.total_pnl || 0).toFixed(2)}</div>
                                    </div>
                                    <div class="metric-card">
                                        <div class="metric-label">Active Positions</div>
                                        <div class="metric-value">${data.status.active_positions || 0}</div>
                                    </div>
                                    <div class="metric-card">
                                        <div class="metric-label">Total Exposure</div>
                                        <div class="metric-value">$${(data.status.total_exposure || 0).toFixed(2)}</div>
                                    </div>
                                    <div class="metric-card">
                                        <div class="metric-label">Sharpe Ratio</div>
                                        <div class="metric-value">${(metrics.sharpe_ratio || 0).toFixed(2)}</div>
                                    </div>
                                    <div class="metric-card">
                                        <div class="metric-label">Profit Factor</div>
                                        <div class="metric-value">${(metrics.profit_factor || 0).toFixed(2)}</div>
                                    </div>
                                    <div class="metric-card">
                                        <div class="metric-label">Uptime (hours)</div>
                                        <div class="metric-value">${(metrics.uptime_hours || 0).toFixed(1)}</div>
                                    </div>
                                </div>
                            `;
                        } catch (error) {
                            console.error('Error updating dashboard:', error);
                        }
                    }

                    // Update every 5 seconds
                    updateDashboard();
                    setInterval(updateDashboard, 5000);
                </script>
            </body>
            </html>
            """
            return render_template_string(html)

        @self.app.route('/api/status')
        def api_status():
            """Get bot status and metrics."""
            status = {
                "status": {
                    "running": False,
                    "active_positions": 0,
                    "total_exposure": 0.0,
                    "max_exposure": 0.0
                },
                "performance": {}
            }

            if self.engine:
                status["status"] = self.engine.get_status()

            if self.performance_tracker:
                status["performance"] = self.performance_tracker.get_metrics()

            return jsonify(status)

        @self.app.route('/api/metrics')
        def api_metrics():
            """Get detailed performance metrics."""
            if not self.performance_tracker:
                return jsonify({"error": "Performance tracker not initialized"})

            metrics = self.performance_tracker.get_metrics()
            recent = self.performance_tracker.get_recent_performance(10)

            return jsonify({
                "overall": metrics,
                "recent": recent
            })

        @self.app.route('/api/trades')
        def api_trades():
            """Get recent trades."""
            if not self.performance_tracker:
                return jsonify({"error": "Performance tracker not initialized"})

            trades = []
            for trade in self.performance_tracker.trades[-20:]:
                trades.append({
                    "timestamp": trade.timestamp.isoformat(),
                    "match_id": trade.match_id,
                    "side": trade.side,
                    "pnl": trade.pnl,
                    "edge": trade.edge
                })

            return jsonify(trades)

    def run(self, debug: bool = False) -> None:
        """Run the dashboard server.

        Args:
            debug: Run in debug mode
        """
        logger.info("starting_dashboard", port=self.port)
        self.app.run(host='0.0.0.0', port=self.port, debug=debug, use_reloader=False)
