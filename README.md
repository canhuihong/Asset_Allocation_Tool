# Quantitative Finance Portfolio & Backtesting System

A full-stack Python framework for portfolio analysis, factor modeling, macroeconomic regime detection, and portfolio optimization using Black-Litterman models.

## Features

- **Macro Regime Detection**: Identify market regime shifts using FRED economic data (growth/inflation proxies).
- **Factor Engine**: Calculate SMB, HML, Momentum factors across a stock universe.
- **Portfolio Analyzer**: Analyze static portfolio metrics (Sharpe, Beta, correlation, decomposition).
- **Macro Sensitivity**: Analyze portfolio exposure to macroeconomic factors.
- **Momentum Backtest**: Run a simple top-N momentum strategy backtest.
- **Portfolio Optimization**: Black-Litterman optimization with optional views; fallback to minimum volatility.
- **Reporting**: Generate interactive HTML reports with plots, metrics, and data exports.
- **IBKR Integration**: Download historical price data directly from Interactive Brokers.

## Environment Setup

### Prerequisites

- Python 3.8+
- Interactive Brokers TWS/Gateway running on `127.0.0.1:4001` (paper trading) or `7496` (live)
- (Optional) Local HTTP proxy for network access (e.g., Clash, v2ray)

### Installation

1. **Clone and enter the directory**
   ```bash
   cd c:\PYL
   ```

2. **Create a Python virtual environment**
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   
   Create a `.env` file in the project root with:
   ```
   FMP_API_KEY=your_fmp_api_key_here
   PROXY_PORT=7897
   IB_HOST=127.0.0.1
   IB_PORT=4001
   IB_CLIENT_ID=1
   ```

   Or copy the template:
   ```bash
   cp .env.example .env
   ```

   Then edit `.env` with your actual values.

## File Structure

```
c:\PYL\
├── main.py                    # Entry point
├── requirements.txt           # Python dependencies
├── README.md                  # This file
├── .gitignore                 # Git exclusions
├── .env.example               # Environment variable template
├── src/
│   ├── config.py              # Configuration & env var loading
│   ├── universe.py            # SP500 / SP600 ticker retrieval
│   ├── data_downloader.py     # IBKR price data downloader
│   ├── factor_engine.py       # Factor computation (SMB, HML, MOM)
│   ├── fmp_data.py            # Fundamental data via Yahoo Finance
│   ├── portfolio_analyzer.py  # Static portfolio metrics
│   ├── macro_engine.py        # Portfolio macro sensitivity
│   ├── macro_regime.py        # Regime detection
│   ├── backtest_engine.py     # Momentum backtest
│   ├── optimizer.py           # Black-Litterman optimizer
│   └── reporting.py           # HTML report generation
├── data/
│   ├── sp500_tickers.csv      # S&P 500 symbols
│   ├── sp600_tickers.csv      # S&P 600 (Small Cap) symbols
│   ├── my_portfolio.csv       # Your portfolio holdings (symbol, weight)
│   ├── my_ff_factors.csv      # (Optional) Fama-French factors
│   ├── views.csv              # (Optional) Black-Litterman views (symbol, view)
│   ├── prices/                # Downloaded historical prices (symbol.csv)
│   └── fundamentals/          # Cached fundamental data
├── outputs/                   # Timestamped report folders
├── notebooks/                 # Jupyter notebooks for exploration
└── tests/                     # Unit tests
```

## Quick Start

1. **Ensure IBKR/TWS is running** and connected to `127.0.0.1:4001`.

2. **Prepare your portfolio CSV** at `data/my_portfolio.csv`:
   ```csv
   symbol,weight
   NVDA,0.5
   MSFT,0.3
   AAPL,0.2
   ```

3. **(Optional) Set manual views** at `data/views.csv`:
   ```csv
   symbol,view
   NVDA,0.15
   TSM,-0.10
   ```

4. **Run the system**
   ```bash
   python main.py
   ```

   The script will:
   - Detect macro regime (growth/inflation signals).
   - Load or download price data for target universe.
   - Compute factors and analyze your portfolio.
   - Run a momentum backtest.
   - Optimize the portfolio using Black-Litterman.
   - Generate an HTML report in `outputs/TIMESTAMP/`.

5. **Open the report** — a browser window should open automatically with the results.

## Configuration

All configuration is read from environment variables (see `.env` above). Key settings:

- **FMP_API_KEY**: Financial Modeling Prep API key (for fundamental data via Yahoo Finance fallback).
- **PROXY_PORT**: Local HTTP proxy port (if needed for network access).
- **IB_HOST**, **IB_PORT**, **IB_CLIENT_ID**: Interactive Brokers connection details.

Edit `.env` and restart to apply changes. **Never commit `.env` to version control.**

## Usage Examples

### Analyze Your Portfolio

Edit `data/my_portfolio.csv` with your holdings, then run `main.py`. The system will:
- Load your positions
- Compute static metrics (Sharpe, beta, correlation)
- Perform macro sensitivity analysis
- Generate visualizations and export results

### View-Based Optimization

Add views to `data/views.csv`:
```csv
symbol,view
NVDA,0.10
XOM,-0.05
AAPL,0.08
```

The Black-Litterman optimizer will incorporate these views into portfolio weights, blending them with market-implied returns.

### Momentum Strategy Backtest

The system runs a top-N momentum strategy out-of-the-box. Modify the backtest parameters in `src/backtest_engine.py`:
- `lookback`: Period for momentum calculation (default: 252 days / 1 year)
- `skip`: Skip period (default: 21 days / 1 month)
- `top_n`: Number of top momentum stocks to hold

## Logging

The system uses Python's `logging` module. Logs are printed to console with timestamps and severity levels. To adjust verbosity, edit the logger level in `src/config.py`:

```python
import logging
logging.getLogger("PYL").setLevel(logging.DEBUG)  # More verbose
```

## Troubleshooting

### "Connection refused" on port 4001
- Ensure Interactive Brokers TWS or Gateway is running.
- Check that it's listening on `127.0.0.1:4001` (paper) or `7496` (live).

### "FMP API Key missing"
- Set `FMP_API_KEY` in `.env` or as an environment variable.
- Obtain a free key from [Financial Modeling Prep](https://financialmodelingprep.com).

### Network errors downloading prices
- If behind a proxy, set `PROXY_PORT` in `.env` and ensure your proxy is running.
- Check firewall rules; some ISPs block Yahoo Finance requests.

### "No price data available"
- Ensure price CSVs are in `data/prices/`.
- Run `main.py` with IBKR enabled to auto-download missing tickers.

## Performance Notes

- **Large universes**: With 100+ stocks, data loading and optimization may take a few minutes. Consider reducing the universe or using a database backend.
- **Data consolidation**: Currently, each stock's prices are stored as a separate CSV. For faster loading, consider consolidating to a Parquet or HDF5 store (future enhancement).

## Testing

Run basic unit tests:
```bash
python -m pytest tests/ -v
```

(Currently in early stages; test coverage expanding.)

## Contributing

Feel free to submit issues and improvements. Key areas for enhancement:
- Distributed backtesting (vectorized calculations).
- Database backend for price storage.
- More advanced risk models (GARCH, CVaR).
- Support for multiple asset classes.

## License

[Your License Here]

## Support

For issues, questions, or suggestions, please file an issue or contact the author.

---

**Last Updated**: December 2025
