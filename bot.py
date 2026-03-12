import os
import json
import httpx
import asyncio
from datetime import datetime, time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# ─── CONFIG ───────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
RPC_URL = "https://rpc.republicai.io"
REST_URL = "https://rest.republicai.io"
MAX_VALIDATORS = 100
MIN_STAKE = 1000
CHECK_INTERVAL = 300  # 5 dakika
DATA_FILE = "/root/republic-ai-bot/data.json"
# ──────────────────────────────────────────────────────────

# ─── PERSISTENT DATA ──────────────────────────────────────
def load_data():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_user_data(chat_id: str):
    data = load_data()
    return data.get(str(chat_id), {})

def set_user_data(chat_id: str, user_data: dict):
    data = load_data()
    data[str(chat_id)] = user_data
    save_data(data)

# ──────────────────────────────────────────────────────────

async def get_block_info():
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(f"{RPC_URL}/status")
            data = r.json()["result"]
            return {
                "block_height": data["sync_info"]["latest_block_height"],
                "block_time": data["sync_info"]["latest_block_time"][:19].replace("T", " "),
                "catching_up": data["sync_info"]["catching_up"],
                "network": data["node_info"]["network"],
            }
    except Exception as e:
        return {"error": str(e)}


async def get_validators():
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{REST_URL}/cosmos/staking/v1beta1/validators?status=BOND_STATUS_BONDED&pagination.limit=200")
            validators = r.json().get("validators", [])
            validators.sort(key=lambda v: int(v["tokens"]), reverse=True)
            total = len(validators)
            top5 = []
            for v in validators[:5]:
                moniker = v["description"]["moniker"]
                tokens = int(v["tokens"]) // 10**18
                top5.append(f"• {moniker} — {tokens:,} RAI")
            is_full = total >= MAX_VALIDATORS
            if is_full and len(validators) >= MAX_VALIDATORS:
                min_entry = int(validators[MAX_VALIDATORS - 1]["tokens"]) // 10**18
            elif total > 0:
                min_entry = int(validators[-1]["tokens"]) // 10**18
            else:
                min_entry = MIN_STAKE
            return {"total": total, "top5": top5, "min_entry_stake": min_entry, "is_full": is_full}
    except Exception as e:
        return {"error": str(e)}


async def get_network_stats():
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{RPC_URL}/status")
            height = int(r.json()["result"]["sync_info"]["latest_block_height"])
            r2 = await client.get(f"{RPC_URL}/block?height={height}")
            block_data = r2.json()["result"]["block"]
            tx_count = len(block_data["data"]["txs"])
            r3 = await client.get(f"{RPC_URL}/block?height={height - 100}")
            old_time = r3.json()["result"]["block"]["header"]["time"]
            new_time = block_data["header"]["time"]
            fmt = "%Y-%m-%dT%H:%M:%S"
            avg_block_time = (datetime.strptime(new_time[:19], fmt) - datetime.strptime(old_time[:19], fmt)).total_seconds() / 100
            return {"height": height, "tx_in_last_block": tx_count, "avg_block_time": round(avg_block_time, 2)}
    except Exception as e:
        return {"error": str(e)}


async def get_wallet_info(address: str):
    try:
        result = {"address": address}
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{REST_URL}/cosmos/bank/v1beta1/balances/{address}")
            balances = r.json().get("balances", [])
            rai_balance = 0
            for b in balances:
                if b["denom"] in ("arai", "aRAI", "uRAI", "urai"):
                    rai_balance = round(int(b["amount"]) / 10**18, 4)
                    break
                elif b["denom"] == "RAI":
                    rai_balance = int(b["amount"])
                    break
            result["balance"] = rai_balance

            r2 = await client.get(f"{REST_URL}/cosmos/staking/v1beta1/delegations/{address}")
            delegations = r2.json().get("delegation_responses", [])
            total_staked = 0
            staking_list = []
            for d in delegations[:3]:
                val_addr = d["delegation"]["validator_address"]
                amount = int(d["balance"]["amount"]) // 10**18
                total_staked += amount
                try:
                    rv = await client.get(f"{REST_URL}/cosmos/staking/v1beta1/validators/{val_addr}")
                    moniker = rv.json()["validator"]["description"]["moniker"]
                except:
                    moniker = val_addr[:20] + "..."
                staking_list.append(f"  • {moniker}: {amount:,} RAI")
            result["total_staked"] = total_staked
            result["staking_list"] = staking_list

            r3 = await client.get(f"{REST_URL}/cosmos/distribution/v1beta1/delegators/{address}/rewards")
            rewards_data = r3.json().get("total", [])
            total_rewards = 0.0
            for rw in rewards_data:
                if rw["denom"] in ("arai", "aRAI", "uRAI", "urai"):
                    total_rewards = float(rw["amount"]) / 10**18
                    break
            result["pending_rewards"] = round(total_rewards, 4)

            result["is_validator"] = False
            result["validator_info"] = None
            try:
                r4 = await client.get(f"{REST_URL}/cosmos/staking/v1beta1/validators?pagination.limit=200")
                all_validators = r4.json().get("validators", [])
                for v in all_validators:
                    for d in delegations:
                        if d["delegation"]["validator_address"] == v["operator_address"]:
                            self_stake = int(d["balance"]["amount"]) // 10**18
                            if self_stake > 0:
                                status_raw = v["status"]
                                val_status = "🟢 Active" if status_raw == "BOND_STATUS_BONDED" else ("🟡 Unbonding" if status_raw == "BOND_STATUS_UNBONDING" else "🔴 Inactive")
                                result["is_validator"] = True
                                result["validator_info"] = {
                                    "moniker": v["description"]["moniker"],
                                    "status": val_status,
                                    "jail": "🔴 JAILED" if v["jailed"] else "✅ Not Jailed",
                                    "tokens": int(v["tokens"]) // 10**18,
                                    "commission": round(float(v["commission"]["commission_rates"]["rate"]) * 100, 2),
                                    "operator_address": v["operator_address"],
                                }
                                break
            except:
                pass

            r5 = await client.get(f"{REST_URL}/cosmos/staking/v1beta1/delegators/{address}/unbonding_delegations")
            unbonding = r5.json().get("unbonding_responses", [])
            result["unbonding"] = sum(int(e["balance"]) // 10**18 for u in unbonding for e in u.get("entries", []))

        return result
    except Exception as e:
        return {"error": str(e)}


async def get_validator_by_address(val_address: str):
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{REST_URL}/cosmos/staking/v1beta1/validators/{val_address}")
            v = r.json().get("validator", {})
            if not v:
                return None
            return {
                "moniker": v["description"]["moniker"],
                "jailed": v["jailed"],
                "status": v["status"],
                "tokens": int(v["tokens"]) // 10**18,
            }
    except:
        return None


async def get_delegations(address: str):
    """Cüzdanın tüm delegasyonlarını çek"""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{REST_URL}/cosmos/staking/v1beta1/delegations/{address}")
            delegations = r.json().get("delegation_responses", [])
            result = []
            for d in delegations:
                result.append({
                    "validator": d["delegation"]["validator_address"],
                    "amount": int(d["balance"]["amount"]) // 10**18,
                })
            return result
    except:
        return []


# ─── BACKGROUND TASKS ─────────────────────────────────────

async def monitor_loop(app):
    """Her 5 dakikada validator jail ve delege kontrolü"""
    await asyncio.sleep(15)
    while True:
        try:
            all_data = load_data()
            for chat_id, user in all_data.items():

                # ── Validator jail kontrolü ──
                monitored = user.get("monitored_validators", {})
                for val_address, prev in list(monitored.items()):
                    current = await get_validator_by_address(val_address)
                    if not current:
                        continue
                    moniker = current["moniker"]

                    if current["jailed"] and not prev.get("jailed", False):
                        await app.bot.send_message(int(chat_id),
                            f"🚨 *JAIL ALERT!*\n\n"
                            f"📛 `{moniker}`\n"
                            f"🔴 Your validator has been JAILED!\n"
                            f"💎 Bonded: `{current['tokens']:,} RAI`\n\n"
                            f"⚠️ Take action immediately!",
                            parse_mode="Markdown"
                        )
                    elif not current["jailed"] and prev.get("jailed", False):
                        await app.bot.send_message(int(chat_id),
                            f"✅ *UNJAILED*\n\n"
                            f"📛 `{moniker}` is back in active set!",
                            parse_mode="Markdown"
                        )
                    elif current["status"] != "BOND_STATUS_BONDED" and prev.get("status") == "BOND_STATUS_BONDED":
                        await app.bot.send_message(int(chat_id),
                            f"⚠️ *VALIDATOR INACTIVE!*\n\n"
                            f"📛 `{moniker}` left the active set!\n"
                            f"Check your node immediately.",
                            parse_mode="Markdown"
                        )

                    all_data[chat_id]["monitored_validators"][val_address] = {
                        "jailed": current["jailed"],
                        "status": current["status"],
                    }

                # ── Delege değişimi kontrolü ──
                wallet = user.get("saved_wallet")
                if wallet and user.get("delegation_alerts", False):
                    current_delegations = await get_delegations(wallet)
                    prev_delegations = user.get("last_delegations", [])

                    prev_map = {d["validator"]: d["amount"] for d in prev_delegations}
                    curr_map = {d["validator"]: d["amount"] for d in current_delegations}

                    for val_addr, amount in curr_map.items():
                        if val_addr not in prev_map:
                            await app.bot.send_message(int(chat_id),
                                f"📥 *New Delegation!*\n\n"
                                f"💎 `{amount:,} RAI` delegated to a validator\n"
                                f"📍 Wallet: `{wallet[:12]}...{wallet[-6:]}`",
                                parse_mode="Markdown"
                            )
                        elif amount != prev_map[val_addr]:
                            diff = amount - prev_map[val_addr]
                            emoji = "📈" if diff > 0 else "📉"
                            await app.bot.send_message(int(chat_id),
                                f"{emoji} *Delegation Changed!*\n\n"
                                f"💎 Change: `{diff:+,} RAI`\n"
                                f"📍 Wallet: `{wallet[:12]}...{wallet[-6:]}`",
                                parse_mode="Markdown"
                            )

                    all_data[chat_id]["last_delegations"] = current_delegations

            save_data(all_data)

        except Exception as e:
            print(f"Monitor error: {e}")

        await asyncio.sleep(CHECK_INTERVAL)


async def faucet_reminder_loop(app):
    """Her gün UTC 09:00'da faucet hatırlatması"""
    while True:
        now = datetime.utcnow()
        target = now.replace(hour=9, minute=0, second=0, microsecond=0)
        if now >= target:
            wait = (24 * 3600) - (now - target).seconds
        else:
            wait = (target - now).seconds
        await asyncio.sleep(wait)

        all_data = load_data()
        for chat_id, user in all_data.items():
            if user.get("faucet_reminder", False):
                wallet = user.get("saved_wallet", "")
                wallet_text = f"\n📍 Your wallet: `{wallet[:12]}...{wallet[-6:]}`" if wallet else ""
                try:
                    await app.bot.send_message(int(chat_id),
                        f"💧 *Daily Faucet Reminder!*\n\n"
                        f"Don't forget to claim your daily faucet!\n"
                        f"🔗 https://points.republicai.io"
                        f"{wallet_text}",
                        parse_mode="Markdown"
                    )
                except:
                    pass


# ─── HELPERS ──────────────────────────────────────────────

def format_validators(info):
    top_list = "\n".join(info["top5"])
    set_status = f"{info['total']}/{MAX_VALIDATORS}"
    if info["is_full"]:
        entry_text = f"⚠️ Active set is FULL ({MAX_VALIDATORS}/{MAX_VALIDATORS})\n🎯 Min stake to enter: `{info['min_entry_stake']:,} RAI`"
    else:
        spots_left = MAX_VALIDATORS - info["total"]
        entry_text = f"✅ {spots_left} spot(s) available\n📌 Min self-delegation: `{MIN_STAKE:,} RAI`"
    return (
        f"👥 *Validator Info*\n\n"
        f"🟢 Active Validators: `{set_status}`\n"
        f"{entry_text}\n\n"
        f"🏆 *Top 5 Validators:*\n{top_list}"
    )


def format_wallet(info):
    short_addr = info["address"][:12] + "..." + info["address"][-6:]
    staking_text = "\n".join(info["staking_list"]) if info["staking_list"] else "  • No active delegations"
    val_section = ""
    if info["is_validator"] and info["validator_info"]:
        v = info["validator_info"]
        op_addr = v.get('operator_address', '')
        short_op = op_addr[:16] + "..." + op_addr[-6:] if op_addr else "—"
        val_section = (
            f"\n\n🏛 *Validator Details*\n"
            f"📛 Moniker: `{v['moniker']}`\n"
            f"🔑 Val Address: `{short_op}`\n"
            f"📡 Status: {v['status']}\n"
            f"🔒 Jail: {v['jail']}\n"
            f"💎 Total Bonded: `{v['tokens']:,} RAI`\n"
            f"💸 Commission: `{v['commission']}%`"
        )
    unbonding_text = f"\n⏳ Unbonding: `{info['unbonding']:,} RAI`" if info["unbonding"] > 0 else ""
    return (
        f"👛 *Wallet Info*\n\n"
        f"📍 Address: `{short_addr}`\n"
        f"💰 Balance: `{info['balance']} RAI`\n"
        f"🏆 Total Staked: `{info['total_staked']:,} RAI`\n"
        f"🎁 Pending Rewards: `{info['pending_rewards']} RAI`"
        f"{unbonding_text}\n\n"
        f"📊 *Delegations:*\n{staking_text}"
        f"{val_section}"
    )


# ─── TELEGRAM HANDLERS ────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📦 Block Status", callback_data="block"),
         InlineKeyboardButton("👥 Validators", callback_data="validators")],
        [InlineKeyboardButton("📊 Network Stats", callback_data="stats"),
         InlineKeyboardButton("👛 My Wallet", callback_data="mywallet")],
    ]
    await update.message.reply_text(
        "🌐 *Republic AI Testnet Stats Bot*\n\n"
        "Select the information you want to see:\n\n"
        "💡 Commands:\n"
        "`/savewallet <address>` — Save your wallet\n"
        "`/mywallet` — View saved wallet info\n"
        "`/wallet <address>` — Any wallet info\n"
        "`/monitor <val_address>` — Monitor validator\n"
        "`/unmonitor <val_address>` — Stop monitoring\n"
        "`/faucet` — Toggle faucet reminder\n"
        "`/alerts` — Toggle delegation alerts\n"
        "`/search <moniker>` — Search validator\n"
        "`/tx <hash>` — Transaction details",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def cmd_savewallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if not context.args:
        await update.message.reply_text("⚠️ Usage: `/savewallet rai1...`", parse_mode="Markdown")
        return
    address = context.args[0]
    if not address.startswith("rai1"):
        await update.message.reply_text("❌ Invalid address. Must start with `rai1`", parse_mode="Markdown")
        return
    user = get_user_data(chat_id)
    user["saved_wallet"] = address
    set_user_data(chat_id, user)
    short = address[:12] + "..." + address[-6:]
    await update.message.reply_text(
        f"✅ *Wallet saved!*\n\n📍 `{short}`\n\nUse /mywallet to view your info anytime.",
        parse_mode="Markdown"
    )


async def cmd_mywallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    user = get_user_data(chat_id)
    wallet = user.get("saved_wallet")
    if not wallet:
        await update.message.reply_text(
            "❌ No wallet saved.\n\nUse `/savewallet rai1...` to save your wallet.",
            parse_mode="Markdown"
        )
        return
    await update.message.reply_text("🔍 Fetching your wallet info...")
    info = await get_wallet_info(wallet)
    if "error" in info:
        await update.message.reply_text(f"❌ Error: {info['error']}")
        return
    await update.message.reply_text(format_wallet(info), parse_mode="Markdown")


async def cmd_block(update: Update, context: ContextTypes.DEFAULT_TYPE):
    info = await get_block_info()
    if "error" in info:
        await update.message.reply_text(f"❌ Error: {info['error']}")
        return
    sync_status = "✅ Synced" if not info["catching_up"] else "🔄 Syncing..."
    await update.message.reply_text(
        f"📦 *Block Info*\n\n"
        f"🔗 Network: `{info['network']}`\n"
        f"📏 Block Height: `{int(info['block_height']):,}`\n"
        f"🕐 Latest Block: `{info['block_time']} UTC`\n"
        f"📡 Sync: {sync_status}",
        parse_mode="Markdown"
    )


async def cmd_validators(update: Update, context: ContextTypes.DEFAULT_TYPE):
    info = await get_validators()
    if "error" in info:
        await update.message.reply_text(f"❌ Error: {info['error']}")
        return
    await update.message.reply_text(format_validators(info), parse_mode="Markdown")


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    info = await get_network_stats()
    if "error" in info:
        await update.message.reply_text(f"❌ Error: {info['error']}")
        return
    await update.message.reply_text(
        f"📊 *Network Stats*\n\n"
        f"📏 Current Block: `{int(info['height']):,}`\n"
        f"📨 TXs in Last Block: `{info['tx_in_last_block']}`\n"
        f"⏱ Avg Block Time: `{info['avg_block_time']}s` (last 100 blocks)",
        parse_mode="Markdown"
    )


async def cmd_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Usage: `/wallet rai1...`", parse_mode="Markdown")
        return
    await update.message.reply_text("🔍 Fetching wallet info, please wait...")
    info = await get_wallet_info(context.args[0])
    if "error" in info:
        await update.message.reply_text(f"❌ Error: {info['error']}")
        return
    await update.message.reply_text(format_wallet(info), parse_mode="Markdown")


async def cmd_monitor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if not context.args:
        await update.message.reply_text(
            "⚠️ Usage: `/monitor <validator_address>`\n\nExample: `/monitor raivaloper1...`",
            parse_mode="Markdown"
        )
        return
    val_address = context.args[0]
    await update.message.reply_text("🔍 Checking validator...")
    current = await get_validator_by_address(val_address)
    if not current:
        await update.message.reply_text("❌ Validator not found. Check the address.")
        return
    user = get_user_data(chat_id)
    if "monitored_validators" not in user:
        user["monitored_validators"] = {}
    user["monitored_validators"][val_address] = {
        "jailed": current["jailed"],
        "status": current["status"],
    }
    set_user_data(chat_id, user)
    status_icon = "🟢 Active" if current["status"] == "BOND_STATUS_BONDED" else "🔴 Inactive"
    await update.message.reply_text(
        f"✅ *Now monitoring!*\n\n"
        f"📛 `{current['moniker']}`\n"
        f"📡 Status: {status_icon}\n"
        f"🔒 Jailed: {'Yes' if current['jailed'] else 'No'}\n\n"
        f"You'll be notified if this validator gets jailed or goes inactive.",
        parse_mode="Markdown"
    )


async def cmd_unmonitor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if not context.args:
        await update.message.reply_text("⚠️ Usage: `/unmonitor <validator_address>`", parse_mode="Markdown")
        return
    val_address = context.args[0]
    user = get_user_data(chat_id)
    monitored = user.get("monitored_validators", {})
    if val_address in monitored:
        del monitored[val_address]
        user["monitored_validators"] = monitored
        set_user_data(chat_id, user)
        await update.message.reply_text("✅ Validator removed from monitoring.")
    else:
        await update.message.reply_text("❌ This validator is not being monitored.")


async def cmd_faucet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    user = get_user_data(chat_id)
    current = user.get("faucet_reminder", False)
    user["faucet_reminder"] = not current
    set_user_data(chat_id, user)
    if not current:
        await update.message.reply_text(
            "💧 *Faucet reminder enabled!*\n\n"
            "You'll receive a daily reminder at 09:00 UTC to claim your faucet.\n"
            "🔗 https://points.republicai.io",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("🔕 Faucet reminder disabled.")


async def cmd_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    user = get_user_data(chat_id)
    if not user.get("saved_wallet"):
        await update.message.reply_text(
            "❌ No wallet saved. Use `/savewallet rai1...` first.",
            parse_mode="Markdown"
        )
        return
    current = user.get("delegation_alerts", False)
    user["delegation_alerts"] = not current
    set_user_data(chat_id, user)
    if not current:
        await update.message.reply_text(
            "🔔 *Delegation alerts enabled!*\n\n"
            "You'll be notified when delegations change on your saved wallet.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("🔕 Delegation alerts disabled.")


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Usage: `/search <moniker>`", parse_mode="Markdown")
        return
    query_str = " ".join(context.args).lower()
    await update.message.reply_text(f"🔍 Searching for `{query_str}`...", parse_mode="Markdown")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            all_validators = []
            next_key = None
            while True:
                import urllib.parse
                url = f"{REST_URL}/cosmos/staking/v1beta1/validators?pagination.limit=200"
                if next_key:
                    url += f"&pagination.key={urllib.parse.quote(next_key)}"
                r = await client.get(url)
                data = r.json()
                all_validators.extend(data.get("validators", []))
                next_key = data.get("pagination", {}).get("next_key")
                if not next_key:
                    break

        matches = [v for v in all_validators if query_str in v["description"]["moniker"].lower()]
        if not matches:
            await update.message.reply_text(f"❌ No validator found matching `{query_str}`", parse_mode="Markdown")
            return
        lines = []
        for v in matches[:5]:
            moniker = v["description"]["moniker"]
            tokens = int(v["tokens"]) // 10**18
            status_raw = v["status"]
            jailed = v["jailed"]
            commission = round(float(v["commission"]["commission_rates"]["rate"]) * 100, 2)
            website = v["description"].get("website", "") or "—"
            details = v["description"].get("details", "") or "—"
            status_icon = "🟢 Active" if status_raw == "BOND_STATUS_BONDED" else ("🟡 Unbonding" if status_raw == "BOND_STATUS_UNBONDING" else "🔴 Inactive")
            jail_icon = "🔴 JAILED" if jailed else "✅ Not Jailed"
            lines.append(
                f"📛 *{moniker}*\n"
                f"📡 Status: {status_icon}\n"
                f"🔒 Jail: {jail_icon}\n"
                f"💎 Bonded: `{tokens:,} RAI`\n"
                f"💸 Commission: `{commission}%`\n"
                f"🌐 Website: {website}\n"
                f"📝 Details: {details}"
            )
        text = f"🔎 *Search results for* `{query_str}`\n\n" + "\n\n─────────────\n\n".join(lines)
        await update.message.reply_text(text, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def cmd_tx(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Usage: `/tx <hash>`", parse_mode="Markdown")
        return
    tx_hash = context.args[0]
    await update.message.reply_text(f"🔍 Looking up TX `{tx_hash[:16]}...`", parse_mode="Markdown")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{REST_URL}/cosmos/tx/v1beta1/txs/{tx_hash}")
            data = r.json()
        tx_response = data.get("tx_response", {})
        if not tx_response:
            await update.message.reply_text("❌ Transaction not found.")
            return
        tx = data.get("tx", {})
        height = tx_response.get("height", "—")
        timestamp = tx_response.get("timestamp", "")[:19].replace("T", " ") or "—"
        code = tx_response.get("code", 0)
        gas_used = tx_response.get("gas_used", "—")
        gas_wanted = tx_response.get("gas_wanted", "—")
        tx_status = "✅ Success" if code == 0 else f"❌ Failed (code: {code})"
        messages = tx.get("body", {}).get("messages", [])
        msg_types = [f"  • `{msg.get('@type', '').split('.')[-1]}`" for msg in messages[:3]]
        msg_text = "\n".join(msg_types) if msg_types else "  • Unknown"
        fee_amounts = tx.get("auth_info", {}).get("fee", {}).get("amount", [])
        fee_text = "—"
        for f in fee_amounts:
            if f["denom"] in ("arai", "aRAI"):
                fee_text = f"{round(int(f['amount']) / 10**18, 6)} RAI"
                break
        await update.message.reply_text(
            f"📨 *Transaction Info*\n\n"
            f"🔑 Hash: `{tx_hash[:20]}...`\n"
            f"📦 Block: `{height}`\n"
            f"🕐 Time: `{timestamp} UTC`\n"
            f"✅ Status: {tx_status}\n"
            f"⛽ Gas: `{gas_used}/{gas_wanted}`\n"
            f"💸 Fee: `{fee_text}`\n\n"
            f"📋 *Message Types:*\n{msg_text}",
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id_int = query.message.chat_id
    chat_id_str = str(chat_id_int)

    if query.data == "block":
        info = await get_block_info()
        if "error" in info:
            await context.bot.send_message(chat_id_int, f"❌ Error: {info['error']}")
            return
        sync_status = "✅ Synced" if not info["catching_up"] else "🔄 Syncing..."
        await context.bot.send_message(chat_id_int,
            f"📦 *Block Info*\n\n"
            f"🔗 Network: `{info['network']}`\n"
            f"📏 Block Height: `{int(info['block_height']):,}`\n"
            f"🕐 Latest Block: `{info['block_time']} UTC`\n"
            f"📡 Sync: {sync_status}",
            parse_mode="Markdown"
        )
    elif query.data == "validators":
        info = await get_validators()
        if "error" in info:
            await context.bot.send_message(chat_id_int, f"❌ Error: {info['error']}")
            return
        await context.bot.send_message(chat_id_int, format_validators(info), parse_mode="Markdown")
    elif query.data == "stats":
        info = await get_network_stats()
        if "error" in info:
            await context.bot.send_message(chat_id_int, f"❌ Error: {info['error']}")
            return
        await context.bot.send_message(chat_id_int,
            f"📊 *Network Stats*\n\n"
            f"📏 Current Block: `{int(info['height']):,}`\n"
            f"📨 TXs in Last Block: `{info['tx_in_last_block']}`\n"
            f"⏱ Avg Block Time: `{info['avg_block_time']}s` (last 100 blocks)",
            parse_mode="Markdown"
        )
    elif query.data == "mywallet":
        user = get_user_data(chat_id_str)
        wallet = user.get("saved_wallet")
        if not wallet:
            await context.bot.send_message(chat_id_int,
                "❌ No wallet saved.\n\nUse `/savewallet rai1...` to save your wallet.",
                parse_mode="Markdown"
            )
            return
        await context.bot.send_message(chat_id_int, "🔍 Fetching your wallet info...")
        info = await get_wallet_info(wallet)
        if "error" in info:
            await context.bot.send_message(chat_id_int, f"❌ Error: {info['error']}")
            return
        await context.bot.send_message(chat_id_int, format_wallet(info), parse_mode="Markdown")


# ─── MAIN ─────────────────────────────────────────────────

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("block", cmd_block))
    app.add_handler(CommandHandler("validators", cmd_validators))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("wallet", cmd_wallet))
    app.add_handler(CommandHandler("savewallet", cmd_savewallet))
    app.add_handler(CommandHandler("mywallet", cmd_mywallet))
    app.add_handler(CommandHandler("monitor", cmd_monitor))
    app.add_handler(CommandHandler("unmonitor", cmd_unmonitor))
    app.add_handler(CommandHandler("faucet", cmd_faucet))
    app.add_handler(CommandHandler("alerts", cmd_alerts))
    app.add_handler(CommandHandler("search", cmd_search))
    app.add_handler(CommandHandler("tx", cmd_tx))
    app.add_handler(CallbackQueryHandler(button_handler))

    loop = asyncio.get_event_loop()
    loop.create_task(monitor_loop(app))
    loop.create_task(faucet_reminder_loop(app))

    print("✅ Republic AI Stats Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
