# Polymarket LoL Arbitrage Bot

An automated trading bot that detects arbitrage opportunities between live League of Legends game states and Polymarket betting odds.

## 🎯 Overview

This bot monitors professional League of Legends matches in real-time and compares the actual game state (gold, kills, objectives) against market odds on Polymarket. When it detects a significant mismatch (edge), it automatically executes trades to capture the spread.

## 🏗️ Architecture

The system consists of three main services running concurrently:

1. **Data Ingestion Service** - Fetches live match data from PandaScore API
2. **Probability Engine** - Calculates win probability using machine learning
3. **Trading Engine** - Monitors Polymarket and executes trades when edge detected

### Component Details

#### 1. Data Ingestion (`src/data_ingestion/`)
- **PandaScoreClient**: Connects to PandaScore API for live LoL match data
- **GameState**: Normalized data model for match state
- **LiveMatchFeed**: Event-driven feed that emits updates on material game changes

**Features:**
- Polls live matches every 1-2 seconds
- Extracts: gold, kills, towers, dragons, barons, inhibitors, game time
- Emits events only on material changes (configurable thresholds)

#### 2. Win Probability Model (`src/probability_model/`)
- **HistoricalDataCollector**: Fetches historical match data for training
- **WinProbabilityTrainer**: Trains ML model on historical data
- **WinProbabilityPredictor**: Predicts win probability from live game state

**Features:**
- Trained on historical pro match data (LCK, LPL, LEC, LCS, Worlds)
- Features: gold_diff, kill_diff, tower_diff, dragon_diff, baron_diff, game_time
- Supports Logistic Regression and Gradient Boosting models
- Real-time probability updates as game state changes

#### 3. Polymarket Integration (`src/polymarket/`)
- **PolymarketClient**: CLOB API client for trading
- **OrderBook**: Orderbook analysis and liquidity calculations
- **MarketMatcher**: Fuzzy matching between live games and markets

**Features:**
- Full CLOB API integration
- Market discovery and matching
- Orderbook analysis
- Position and balance tracking

#### 4. Arbitrage Engine (`src/arbitrage/`)
- **ArbitrageStrategy**: Signal generation based on edge detection
- **ArbitrageEngine**: Main orchestration loop

**Features:**
- Configurable edge thresholds (default 5%)
- Risk management (position limits, exposure limits)
- Slippage protection
- Duplicate trade prevention

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- PandaScore API key (free tier available at [pandascore.co](https://pandascore.co))
- Polymarket account with API credentials
- Ethereum wallet with USDC on Polygon

### Installation

1. **Clone the repository**
```bash
git clone <repo-url>
cd Polymarket-Trading-Bot
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure environment**
```bash
cp config/.env.example config/.env
```

Edit `config/.env` and add your API keys:
```
PANDASCORE_API_KEY=your_key_here
POLYMARKET_API_KEY=your_key_here
POLYMARKET_SECRET=your_secret_here
POLYMARKET_PASSPHRASE=your_passphrase_here
WALLET_PRIVATE_KEY=your_private_key_here
```

4. **Test connections**
```bash
python scripts/test_connection.py
```

### Training the Model

Before running the bot, you need to train the win probability model:

1. **Collect historical data**
```bash
python scripts/collect_data.py
```
This fetches historical match data from PandaScore (may take 10-30 minutes).

2. **Train the model**
```bash
python scripts/train_model.py
```
This trains a machine learning model on the historical data.

### Running the Bot

```bash
python main.py
```

The bot will:
- Monitor live LoL matches
- Calculate win probabilities in real-time
- Match games to Polymarket markets
- Execute trades when profitable opportunities are detected
- Launch web dashboard at http://localhost:5000

Press `Ctrl+C` to stop gracefully.

### Running Backtests

Validate your strategy on historical data:

```bash
python scripts/run_backtest.py
```

Requirements:
- Trained model
- Historical data in `data/backtest/matches.csv` and `data/backtest/markets.csv`

The backtest will:
- Simulate trades on historical match data
- Calculate realistic P&L with slippage and fees
- Output performance metrics and save results

## ⚙️ Configuration

Main configuration is in `config/config.yaml`:

### Trading Parameters
```yaml
arbitrage:
  strategy:
    min_edge: 0.05           # Minimum 5% edge to trade
    max_position_size: 100.0 # Max $100 per position
    min_liquidity: 500.0     # Min $500 market liquidity
    max_spread: 0.02         # Max 2% bid-ask spread
    use_kelly_criterion: true  # Use Kelly Criterion sizing
    kelly_fraction: 0.25     # Quarter Kelly (conservative)

  risk_management:
    max_total_exposure: 1000.0  # Max $1000 total exposure
    max_positions_per_match: 1   # One position per match

alerts:
  telegram:
    enabled: false  # Set to true and add credentials to .env
  discord:
    enabled: false

dashboard:
  enabled: true
  port: 5000
```

### Data Ingestion
```yaml
data_ingestion:
  pandascore:
    poll_interval: 2  # Poll every 2 seconds

  game_state:
    material_change_threshold:
      gold_diff: 500      # Trigger on 500g swing
      kills: 1            # Trigger on each kill
      towers: 1           # Trigger on each tower
```

### Model Parameters
```yaml
probability_model:
  training:
    model_type: "logistic_regression"  # or "gradient_boosting"
    test_size: 0.2
```

## 📊 Project Structure

```
Polymarket-Trading-Bot/
├── src/
│   ├── data_ingestion/      # Live match data feed
│   ├── probability_model/   # ML model for win prediction
│   ├── polymarket/          # Polymarket API integration
│   ├── arbitrage/           # Trading strategy & engine
│   └── utils/               # Config & logging
├── scripts/
│   ├── collect_data.py      # Collect training data
│   ├── train_model.py       # Train ML model
│   └── test_connection.py   # Test API connections
├── config/
│   ├── config.yaml          # Main configuration
│   └── .env                 # API keys (not committed)
├── data/
│   └── historical/          # Training data
├── logs/                    # Application logs
├── main.py                  # Main entry point
└── requirements.txt         # Python dependencies
```

## 🔑 Key Features

### Real-time Edge Detection
The bot calculates the "edge" between the model's probability and the market's implied probability:
```
Edge = Model_Probability - Market_Probability

If Edge > min_edge_threshold → BUY signal
If Edge < -min_edge_threshold → SELL signal
```

### Kelly Criterion Position Sizing
- **Optimal bet sizing** based on edge and win probability
- **Fractional Kelly** (quarter Kelly by default) for safety
- **Dynamic sizing** scales with confidence
- Falls back to fixed sizing if Kelly disabled

### Risk Management
- **Position Limits**: Max position size per trade
- **Exposure Limits**: Max total capital at risk
- **Liquidity Checks**: Only trade markets with sufficient depth
- **Slippage Protection**: Calculate expected slippage before trading
- **Duplicate Prevention**: One position per match
- **Data Validation**: Sanity checks on game state data

### Market Matching
Intelligent fuzzy matching between live game teams and Polymarket markets:
- Handles team name variations (T1, SKT, SK Telecom)
- Configurable team aliases
- Similarity threshold tuning

### Backtesting Framework
- Test strategies on historical data
- Realistic simulation with slippage and commissions
- Comprehensive metrics: Sharpe ratio, max drawdown, edge realization
- Export results to CSV for analysis

### Monitoring & Alerts
- **Web Dashboard**: Real-time performance monitoring at http://localhost:5000
- **Telegram Alerts**: Trade execution, P&L updates, errors
- **Discord Webhooks**: Team notifications
- **Performance Tracking**: Win rate, profit factor, edge realization

### Web Dashboard
Access at `http://localhost:5000` when bot is running:
- Live bot status and uptime
- Active positions and exposure
- Total P&L and win rate
- Sharpe ratio and profit factor
- Auto-refreshes every 5 seconds

## 📈 Model Performance

The win probability model is trained on historical pro match data:
- **Features**: Gold diff, kills, towers, dragons, barons, inhibitors, game time
- **Target**: Binary outcome (team1 win/loss)
- **Typical Accuracy**: 70-80% (varies by data quality)
- **ROC AUC**: 0.75-0.85

Key insight: Major objective captures (Baron, Elder Dragon) create temporary mispricings as the market lags the game state.

## 🛡️ Safety Features

- Graceful shutdown on Ctrl+C
- Comprehensive logging (file + console)
- Error handling and retry logic
- API rate limit respect
- Position tracking and reconciliation

## 🧪 Testing

Run connection tests:
```bash
python scripts/test_connection.py
```

Run unit tests:
```bash
pytest tests/
```

Run backtest:
```bash
python scripts/run_backtest.py
```

## 📝 Logs

Logs are written to:
- Console: Color-coded structured logs
- File: `logs/arbitrage_bot.log`

Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL

## 🔧 Development

### Adding New Features

1. **New data sources**: Extend `src/data_ingestion/`
2. **Better models**: Modify `src/probability_model/model_trainer.py`
3. **Trading strategies**: Create new strategies in `src/arbitrage/strategy.py`
4. **Team aliases**: Update `config/config.yaml` → `polymarket.market_matching.team_aliases`
5. **Custom alerts**: Extend `src/utils/alerts.py`

### Model Retraining

Retrain periodically with fresh data:
```bash
python scripts/collect_data.py
python scripts/train_model.py
```

### Monitoring & Alerts

**Web Dashboard:**
- Access at http://localhost:5000 when bot is running
- Shows real-time metrics, positions, P&L
- Auto-refreshes every 5 seconds

**Telegram Alerts:**
1. Create bot via @BotFather on Telegram
2. Get bot token
3. Get your chat ID (use @userinfobot)
4. Add to config/.env:
   ```
   TELEGRAM_BOT_TOKEN=your_token
   TELEGRAM_CHAT_ID=your_chat_id
   ```
5. Enable in config/config.yaml: `alerts.telegram.enabled: true`

**Discord Alerts:**
1. Create webhook in Discord channel settings
2. Add to config/.env: `DISCORD_WEBHOOK_URL=your_webhook_url`
3. Enable in config/config.yaml: `alerts.discord.enabled: true`

## ⚠️ Disclaimers

- **Financial Risk**: This bot trades real money. Use at your own risk.
- **No Guarantees**: Past performance doesn't guarantee future results.
- **Test First**: Always test with small amounts before scaling.
- **API Limits**: Respect PandaScore and Polymarket rate limits.
- **Regulatory**: Ensure compliance with local gambling/trading regulations.

## 🤝 Contributing

Contributions welcome! Areas for improvement:
- Better ML models (LSTM, Transformer)
- More data sources (Riot API, stream parsing)
- Advanced strategies (Kelly Criterion sizing)
- Backtesting framework
- Web dashboard

## 📄 License

MIT License - See LICENSE file for details

## 🔗 Resources

- [PandaScore API Docs](https://developers.pandascore.co/)
- [Polymarket CLOB API](https://docs.polymarket.com/)
- [League of Legends Data](https://oracleselixir.com/)

## 📧 Support

For issues and questions:
- Open an issue on GitHub
- Check logs in `logs/arbitrage_bot.log`
- Test connections with `scripts/test_connection.py`

---

**Built with ❤️ for esports and DeFi**
