# Hyperliquid MCP - Quick Start Guide

Get trading on Hyperliquid with AI in 5 minutes!

## Prerequisites Check

```bash
# Check Python version (need 3.10+)
python --version

# Install uv if not installed
pip install uv
```

## Step 1: Register Your Wallet (2 minutes)

### For Mainnet:
1. Go to https://app.hyperliquid.xyz
2. Connect your MetaMask or wallet
3. Click "Deposit" and bridge any amount from Arbitrum One
   - Even $10 USDC works - this registers your wallet

### For Testnet:
1. Go to https://app.hyperliquid-testnet.xyz
2. Connect your wallet
3. Use the faucet or bridge testnet funds

**✅ Checkpoint:** You should see a balance on Hyperliquid's UI

## Step 2: Configure the MCP (1 minute)

### Option A: Direct Environment Variables (Simplest)

Edit your Claude Desktop config directly:

**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`  
**Mac:** `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "hyperliquid": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/yourusername/hyperliquid-mcp.git", "hyperliquid-mcp"],
      "env": {
        "HYPERLIQUID_PRIVATE_KEY": "0xYOUR_PRIVATE_KEY_HERE",
        "HYPERLIQUID_TESTNET": "false"
      }
    }
  }
}
```

### Option B: Local Installation

```bash
# Clone and setup
git clone <repo-url> hyperliquid-mcp
cd hyperliquid-mcp

# Create .env file
cp .env.example .env

# Edit .env with your private key
nano .env
# Set: HYPERLIQUID_PRIVATE_KEY=0xYourKeyHere

# Configure Claude Desktop to use local version
```

Config for local:
```json
{
  "mcpServers": {
    "hyperliquid": {
      "command": "uv",
      "args": ["run", "--directory", "D:\\path\\mcp\\hyperliquid-mcp", "python", "-m", "hyperliquid_mcp.server"]
    }
  }
}
```

**✅ Checkpoint:** Config file saved and closed

## Step 3: Restart Claude Desktop (30 seconds)

1. **Completely quit** Claude Desktop (not just close window)
   - Windows: Right-click system tray icon → Exit
   - Mac: Cmd+Q or Claude → Quit Claude

2. **Restart** Claude Desktop

3. **Verify** the MCP loaded:
   - Look for the 🔌 icon in Claude's interface
   - Click it to see "hyperliquid" listed

**✅ Checkpoint:** You see "hyperliquid" in the MCP list

## Step 4: Test It! (30 seconds)

Try these commands in Claude:

### Test 1: Check Connection
```
Show me my Hyperliquid account balance
```

Expected: Shows your account value, margin, and withdrawable amount

### Test 2: Get Market Data
```
What's the current price of BTC, ETH, and SOL on Hyperliquid?
```

Expected: Shows current prices for all three assets

### Test 3: View Asset List
```
Show me all tradeable assets on Hyperliquid with their indices
```

Expected: Complete list of assets with index numbers (BTC=0, ETH=1, SOL=5, etc.)

**✅ Checkpoint:** All three commands work!

## Step 5: Place Your First Order (Optional - 1 minute)

### Practice with a Small Order

```
Place a test order on Hyperliquid:
- Asset: SOL
- Side: BUY
- Size: 0.05 SOL (about $10)
- Price: [current price - 10%] (so it won't fill)
- Type: Limit order

Just to test, we'll cancel it right after.
```

Expected: Order places successfully, you get an order ID

### Cancel the Test Order

```
Cancel all my open orders on Hyperliquid
```

Expected: Test order is cancelled

**✅ Checkpoint:** You successfully placed and cancelled an order!

## Common Issues & Fixes

### Issue: "User or API Wallet does not exist"

**Fix:** Your wallet isn't registered yet
- Go back to Step 1
- Make sure you deposited funds on Hyperliquid
- Wait 1-2 minutes for registration to process

### Issue: MCP not showing in Claude

**Fix:** Configuration problem
1. Check your `claude_desktop_config.json` syntax (use JSON validator)
2. Make sure private key starts with `0x`
3. Restart Claude completely (quit and reopen)

### Issue: "Order value must be at least $10"

**Fix:** Order too small
- Calculate: size × price must be ≥ $10
- For SOL at $200: need at least 0.05 SOL
- For BTC at $50k: need at least 0.0002 BTC

### Issue: Python version too old

**Fix:** Update Python
```bash
# Check version
python --version

# If < 3.10, install Python 3.11+
# Windows: Download from python.org
# Mac: brew install python@3.11
# Linux: sudo apt install python3.11
```

## Next Steps

Now that you're set up, try:

1. **Read the full README.md** for all available tools
2. **Check your positions:** "Show me my open positions"
3. **View trade history:** "Show my trades from the past 24 hours"
4. **Practice bracket orders:** "Place a bracket order for SOL..."

## Safety Tips for Your First Trades

1. ✅ **Start with testnet** until comfortable
2. ✅ **Use small sizes** for first real trades
3. ✅ **Always set stop losses** (use bracket orders)
4. ✅ **Test cancellation** works before large orders
5. ✅ **Monitor positions** regularly

## Need Help?

- **Full Documentation:** See README.md
- **Hyperliquid Docs:** https://hyperliquid.gitbook.io/
- **MCP Issues:** Open a GitHub issue
- **Trading Support:** Hyperliquid Discord

## Pro Tips

### Use Natural Language

Instead of memorizing commands, just talk naturally:

```
"What's my account worth?"
"Show me the SOL order book"
"Buy 0.1 BTC at market price with a stop loss 2% below"
"Close all my positions"
```

Claude will figure out which tools to use!

### Get Asset Indices Quickly

```
"What's the asset index for SOL?"
```

Claude will call `hyperliquid_get_meta` and tell you (it's 5).

### Check Before You Trade

```
"Before I trade, show me:
1. My current balance
2. Current SOL price
3. My open orders"
```

Claude will run all three checks!

---

**You're all set! Happy trading! 🚀**

Remember: Start small, use stop losses, and never risk more than you can afford to lose.
