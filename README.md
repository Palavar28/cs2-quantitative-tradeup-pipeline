# Quantitative CS2 Trade-Up Arbitrage Pipeline

## Overview
This project is a fully automated, asynchronous data pipeline designed to analyze real-time market data and calculate the Expected Value (EV) and Risk profiles of Counter-Strike 2 trade-up contracts. It acts as an autonomous financial decision-support system, evaluating statistical profitability and sustainability before any capital is deployed.

All active project files and scripts are located within the `cs2_takas/` directory.

## Core Architecture

- **Asynchronous Data Fetching**: Utilizes `aiohttp` and `asyncio` to fetch live market listings from the CSFloat API, handling rate-limiting and connection stability.
- **Quantitative Float Engine**: Calculates precise outcome float values based on Weighted Normalized Float math `(Actual - Min) / (Max - Min)`, accounting for absolute min/max restrictions. It dynamically fetches live prices for the mathematically correct outcome wear.
- **Financial Business Logic**: Evaluates trades based on a 2% CSFloat selling tax (rather than the default 15% Steam tax). 
- **Smart Gamble Risk Analytics**: Shifts away from impossible "guaranteed profit" logic toward asymmetric risk profiles. It calculates a *Sustainability Score* (how many times you can fail before losing one full trade-up cost in EV) and identifies *Positive EV Anomalies*.
- **Optimization Algorithm**: Scans live market data to find the absolute cheapest combination of 10 input assets that satisfy the mathematical threshold for a profitable jackpot payout.

## Tech Stack
Python, asyncio, aiohttp, OOP, API Integration.
