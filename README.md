# 🌐 Republic AI Testnet Helper Bot

A powerful Telegram bot providing real-time statistics, monitoring, and alerts for the **Republic AI Testnet**

[![Republic AI](https://img.shields.io/badge/Republic%20AI-Testnet-blue)](https://republicai.io)
[![Python](https://img.shields.io/badge/Python-3.10+-green)](https://python.org)
[![Republicaihelperbot](https://img.shields.io/badge/Telegram-Bot-blue)](https://t.me/republicaihelperbot)
---

## 📊 Features

| Feature | Command | Description |
|---------|---------|-------------|
| 📦 Block Status | `/block` | Latest block height, time & sync status |
| 👥 Validators | `/validators` | Active validator count, top 5, min entry stake |
| 📊 Network Stats | `/stats` | TPS, avg block time (last 100 blocks) |
| 👛 Wallet Info | `/wallet <address>` | Balance, staking, rewards, validator details |
| 💾 Save Wallet | `/savewallet <address>` | Save your wallet for quick access |
| 🔍 My Wallet | `/mywallet` | View your saved wallet instantly |
| 🔎 Search | `/search <moniker>` | Search any validator by name |
| 📨 TX Lookup | `/tx <hash>` | Full transaction details |
| 🚨 Jail Monitor | `/monitor <val_address>` | Get alerted if validator gets jailed |
| 🔕 Stop Monitor | `/unmonitor <val_address>` | Stop monitoring a validator |
| 🔔 Delegation Alerts | `/alerts` | Get notified on delegation changes |
| 💧 Faucet Reminder | `/faucet` | Daily reminder to claim faucet at 09:00 UTC |

---

## 🚀 Quick Start

### 1. Clone the repo
```bash
git clone https://github.com/YOUR_USERNAME/republic-ai-stats-bot
cd republic-ai-stats-bot
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Get a Telegram Bot Token
- Message [@BotFather](https://t.me/BotFather) on Telegram
- Send `/newbot` and follow the steps
- Copy your bot token

### 4. Set your token
```bash
export BOT_TOKEN="your_token_here"
```

Or create a `.env` file:
```
BOT_TOKEN=your_token_here
```

### 5. Run the bot
```bash
python3 bot.py
```

---

## 🖥 Run as a Service (Linux VPS)

```bash
# Create service file
sudo nano /etc/systemd/system/republicbot.service
```

Paste this:
```ini
[Unit]
Description=Republic AI Stats Bot
After=network.target

[Service]
User=root
WorkingDirectory=/root/republic-ai-bot
EnvironmentFile=/root/republic-ai-bot/.env
ExecStart=/usr/bin/python3 /root/republic-ai-bot/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable republicbot
systemctl start republicbot
```

---

## 🔗 Network Info

| | |
|--|--|
| Network | Republic AI Testnet |
| Cosmos RPC | `https://rpc.republicai.io` |
| REST API | `https://rest.republicai.io` |
| Explorer | `https://explorer.republicai.io` |
| Faucet | `https://points.republicai.io` |

---

## 📁 Project Structure

```
republic-ai-stats-bot/
├── bot.py            # Main bot code
├── requirements.txt  # Python dependencies
├── .env              # Bot token (not committed)
├── data.json         # User data storage (auto-created)
└── README.md         # This file
```

---

## 🤖 Bot Commands

```
/start          — Show main menu
/block          — Latest block info
/validators     — Validator list & active set info
/stats          — Network statistics
/wallet <addr>  — Any wallet info
/savewallet     — Save your wallet address
/mywallet       — View your saved wallet
/search <name>  — Search validator by moniker
/tx <hash>      — Transaction details
/monitor <addr> — Monitor validator for jail alerts
/unmonitor      — Stop monitoring
/alerts         — Toggle delegation change alerts
/faucet         — Toggle daily faucet reminder
```

---

## 👤 Author

Built by **solscammer** as a community contribution to the Republic AI Developer ecosystem.

- 🐦 Republic AI X: [@republicfdn](https://x.com/republicfdn)
- 💬 Discord: [Join here](https://discord.com/invite/Fv33CVnC3R)
- 🌐 Explorer: [explorer.republicai.io](https://explorer.republicai.io)

---

*Open source. Free to use. Built for the Republic AI community.*
"# republic-ai-helper-bot" 
"# republic-ai-helper-bot" 
