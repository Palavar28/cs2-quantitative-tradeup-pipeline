Quantitative CS2 Trade-Up Arbitrage Pipeline
Overview
This project is a fully automated, asynchronous data pipeline designed to analyze real-time market data and calculate the Expected Value (EV) of Counter-Strike 2 trade-up contracts. It acts as an autonomous financial decision-support system, evaluating statistical profitability before any capital is deployed.

Core Architecture

Asynchronous Data Fetching: Utilizes aiohttp and asyncio to fetch live market listings from the CSFloat API, handling rate-limiting and connection stability.

Quantitative Float Engine: Calculates precise outcome float values based on input wear averages, accounting for absolute min/max restrictions.

Financial Business Logic: Dynamically categorizes items into 9 granular wear sub-tiers (e.g., "Good Field-Tested", "Bad Battle-Scarred") for high-precision pricing, automatically deducting platform taxes (15%) to calculate net ROI.

Optimization Algorithm: Scans live market data to find the absolute cheapest combination of 10 input assets that satisfy the mathematical threshold for a profitable outcome.

Tech Stack: Python, asyncio, aiohttp, OOP, API Integration, Secret Management (dotenv).
