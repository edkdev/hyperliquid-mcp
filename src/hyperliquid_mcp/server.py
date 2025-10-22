"""Hyperliquid MCP Server - Main implementation."""

import asyncio
import json
import logging
import os
import sys
from typing import Any, Optional

import eth_account
from eth_account.signers.local import LocalAccount
from hyperliquid.exchange import Exchange
from hyperliquid.info import Info
from hyperliquid.utils import constants
from hyperliquid.utils.types import Cloid
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment variables are now loaded from client config (MCP settings)
# No need for dotenv - variables come from the env section in mcp.json


class HyperliquidMCPServer:
    """MCP Server for Hyperliquid trading using the official Python SDK."""
    
    def __init__(self):
        """Initialize the Hyperliquid MCP server."""
        self.server = Server("hyperliquid-mcp")
        
        # Load configuration from environment
        self.private_key = os.getenv("HYPERLIQUID_PRIVATE_KEY")
        self.account_address = os.getenv("HYPERLIQUID_ACCOUNT_ADDRESS")
        self.vault_address = os.getenv("HYPERLIQUID_VAULT_ADDRESS")
        self.testnet = os.getenv("HYPERLIQUID_TESTNET", "").lower() == "true"
        
        if not self.private_key:
            raise ValueError("HYPERLIQUID_PRIVATE_KEY environment variable is required")
        
        # Initialize Hyperliquid SDK
        self._init_hyperliquid()
        
        # Register handlers
        self._register_handlers()
    
    def _init_hyperliquid(self):
        """Initialize Hyperliquid Exchange and Info instances."""
        try:
            # Create wallet from private key
            self.wallet: LocalAccount = eth_account.Account.from_key(self.private_key)
            
            # Determine account address (for agent mode support)
            if not self.account_address:
                self.account_address = self.wallet.address
                logger.info(f"Using wallet address as account: {self.account_address}")
            else:
                logger.info(f"Agent mode: API wallet {self.wallet.address} signing for account {self.account_address}")
            
            # Set base URL based on testnet flag
            base_url = constants.TESTNET_API_URL if self.testnet else constants.MAINNET_API_URL
            logger.info(f"Connecting to: {base_url}")
            
            # Initialize Info (read-only queries)
            self.info = Info(base_url, skip_ws=True)
            
            # Initialize Exchange (trading operations)
            self.exchange = Exchange(
                wallet=self.wallet,
                base_url=base_url,
                account_address=self.account_address,
                vault_address=self.vault_address
            )
            
            # Verify wallet is registered
            try:
                user_state = self.info.user_state(self.account_address)
                logger.info(f"✅ Wallet verified! Account value: ${user_state['marginSummary']['accountValue']}")
            except Exception as e:
                logger.warning(f"⚠️  Could not verify wallet: {e}")
                logger.warning("Make sure your wallet is registered on Hyperliquid (deposit funds to register)")
                
        except Exception as e:
            logger.error(f"Failed to initialize Hyperliquid SDK: {e}")
            raise
    
    def _register_handlers(self):
        """Register all MCP handlers."""
        
        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """List all available Hyperliquid tools."""
            return [
                # Account & Position Management
                Tool(
                    name="hyperliquid_get_account_info",
                    description="Get user's perpetual account summary including positions and margin",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "userAddress": {
                                "type": "string",
                                "description": "User address (optional, defaults to configured account)"
                            },
                            "dex": {
                                "type": "string",
                                "description": "Perp dex name (optional, defaults to empty string)",
                                "default": ""
                            }
                        }
                    }
                ),
                Tool(
                    name="hyperliquid_get_positions",
                    description="Get user's open positions with margin summary",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "userAddress": {
                                "type": "string",
                                "description": "User address (optional, defaults to configured account)"
                            },
                            "dex": {
                                "type": "string",
                                "description": "Perp dex name (optional, defaults to empty string)",
                                "default": ""
                            }
                        }
                    }
                ),
                Tool(
                    name="hyperliquid_get_balance",
                    description="Get user's account balance and withdrawable amount",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "userAddress": {
                                "type": "string",
                                "description": "User address (optional, defaults to configured account)"
                            },
                            "dex": {
                                "type": "string",
                                "description": "Perp dex name (optional, defaults to empty string)",
                                "default": ""
                            }
                        }
                    }
                ),
                
                # Order Management
                Tool(
                    name="hyperliquid_place_order",
                    description="Place a single order on Hyperliquid. Minimum order value is $10. Use asset index from get_meta (e.g., 0=BTC, 1=ETH, 5=SOL).",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "asset": {
                                "type": "integer",
                                "description": "Asset index (e.g., 0 for BTC, 1 for ETH, 5 for SOL). Use hyperliquid_get_meta to get the full list.",
                                "minimum": 0
                            },
                            "isBuy": {
                                "type": "boolean",
                                "description": "True for buy/long orders, false for sell/short orders"
                            },
                            "size": {
                                "type": "string",
                                "description": "Order size/quantity as a string (e.g., '0.1' for 0.1 BTC). Ensure size * price >= $10."
                            },
                            "price": {
                                "type": "string",
                                "description": "Limit price as a string (e.g., '181.5'). Set to '0' for market orders."
                            },
                            "reduceOnly": {
                                "type": "boolean",
                                "description": "Whether this is a reduce-only order (only closes existing positions)",
                                "default": False
                            },
                            "orderType": {
                                "type": "object",
                                "description": "Order type configuration. For limit orders use {limit: {tif: 'Gtc'}}. For trigger orders use {trigger: {isMarket: false, triggerPx: 'price', tpsl: 'tp' or 'sl'}}",
                                "default": {"limit": {"tif": "Gtc"}}
                            },
                            "cloid": {
                                "type": "string",
                                "description": "Client order ID (optional, for tracking)"
                            }
                        },
                        "required": ["asset", "isBuy", "size"]
                    }
                ),
                Tool(
                    name="hyperliquid_place_bracket_order",
                    description="Place a complete bracket order (entry + take profit + stop loss) in a single atomic batch. Minimum order value is $10. The TP and SL orders are automatically set as reduce-only and trigger orders.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "asset": {
                                "type": "integer",
                                "description": "Asset index (e.g., 0 for BTC, 1 for ETH, 5 for SOL)",
                                "minimum": 0
                            },
                            "isBuy": {
                                "type": "boolean",
                                "description": "True for buy/long positions, false for sell/short positions"
                            },
                            "size": {
                                "type": "string",
                                "description": "Position size as a string (e.g., '4.96' for 4.96 SOL)"
                            },
                            "entryPrice": {
                                "type": "string",
                                "description": "Entry limit price as a string (e.g., '181.5'). Set to '0' for market entry."
                            },
                            "takeProfitPrice": {
                                "type": "string",
                                "description": "Take profit trigger price. For long: above entry. For short: below entry."
                            },
                            "stopLossPrice": {
                                "type": "string",
                                "description": "Stop loss trigger price. For long: below entry. For short: above entry."
                            },
                            "reduceOnly": {
                                "type": "boolean",
                                "description": "Whether the ENTRY order is reduce-only (usually false)",
                                "default": False
                            },
                            "entryOrderType": {
                                "type": "object",
                                "description": "Entry order type configuration",
                                "default": {"limit": {"tif": "Gtc"}}
                            }
                        },
                        "required": ["asset", "isBuy", "size", "takeProfitPrice", "stopLossPrice"]
                    }
                ),
                Tool(
                    name="hyperliquid_cancel_order",
                    description="Cancel a specific order by coin name and order ID (oid). Always use oid for cancellation.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "coin": {
                                "type": "string",
                                "description": "Coin/asset name (e.g., 'BTC', 'ETH', 'SOL')"
                            },
                            "oid": {
                                "type": "integer",
                                "description": "Order ID (oid) - the unique order identifier returned when order was placed"
                            }
                        },
                        "required": ["coin", "oid"]
                    }
                ),
                Tool(
                    name="hyperliquid_cancel_all_orders",
                    description="Cancel all open orders for the user. Fetches all open orders and cancels them.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "userAddress": {
                                "type": "string",
                                "description": "User address (optional, defaults to configured account)"
                            },
                            "dex": {
                                "type": "string",
                                "description": "Perp dex name (optional)",
                                "default": ""
                            }
                        }
                    }
                ),
                Tool(
                    name="hyperliquid_modify_order",
                    description="Modify an existing order",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "oid": {
                                "type": "integer",
                                "description": "Order ID to modify"
                            },
                            "coin": {
                                "type": "string",
                                "description": "Coin/asset name (e.g., 'BTC', 'ETH', 'SOL')"
                            },
                            "isBuy": {
                                "type": "boolean",
                                "description": "True for buy orders, false for sell orders"
                            },
                            "size": {
                                "type": "string",
                                "description": "New order size"
                            },
                            "price": {
                                "type": "string",
                                "description": "New limit price"
                            },
                            "reduceOnly": {
                                "type": "boolean",
                                "description": "Whether this is a reduce-only order",
                                "default": False
                            },
                            "orderType": {
                                "type": "object",
                                "description": "Order type configuration",
                                "default": {"limit": {"tif": "Gtc"}}
                            }
                        },
                        "required": ["oid", "coin", "isBuy", "size", "price"]
                    }
                ),
                Tool(
                    name="hyperliquid_place_twap_order",
                    description="Place a Time-Weighted Average Price (TWAP) order",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "coin": {
                                "type": "string",
                                "description": "Coin/asset name (e.g., 'BTC', 'ETH', 'SOL')"
                            },
                            "isBuy": {
                                "type": "boolean",
                                "description": "True for buy orders, false for sell orders"
                            },
                            "size": {
                                "type": "string",
                                "description": "Total order size to be executed over time"
                            },
                            "minutes": {
                                "type": "integer",
                                "description": "Duration in minutes for TWAP execution",
                                "minimum": 2
                            },
                            "reduceOnly": {
                                "type": "boolean",
                                "description": "Whether this is a reduce-only order",
                                "default": False
                            },
                            "randomize": {
                                "type": "boolean",
                                "description": "Whether to randomize TWAP intervals",
                                "default": True
                            }
                        },
                        "required": ["coin", "isBuy", "size", "minutes"]
                    }
                ),
                Tool(
                    name="hyperliquid_cancel_twap_order",
                    description="Cancel a TWAP order by its ID",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "twapId": {
                                "type": "integer",
                                "description": "TWAP order ID to cancel"
                            }
                        },
                        "required": ["twapId"]
                    }
                ),
                
                # Order Queries
                Tool(
                    name="hyperliquid_get_open_orders",
                    description="Get user's currently open orders",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "userAddress": {
                                "type": "string",
                                "description": "User address (optional, defaults to configured account)"
                            },
                            "dex": {
                                "type": "string",
                                "description": "Perp dex name (optional)",
                                "default": ""
                            }
                        }
                    }
                ),
                Tool(
                    name="hyperliquid_get_order_status",
                    description="Get the status of a specific order by oid",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "userAddress": {
                                "type": "string",
                                "description": "User address (optional, defaults to configured account)"
                            },
                            "oid": {
                                "type": "integer",
                                "description": "Order ID"
                            }
                        },
                        "required": ["oid"]
                    }
                ),
                Tool(
                    name="hyperliquid_get_user_fills",
                    description="Get user's historical trade fills",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "userAddress": {
                                "type": "string",
                                "description": "User address (optional, defaults to configured account)"
                            },
                            "startTime": {
                                "type": "integer",
                                "description": "Start time in milliseconds (required)"
                            },
                            "endTime": {
                                "type": "integer",
                                "description": "End time in milliseconds (optional, defaults to current time)"
                            },
                            "aggregateByTime": {
                                "type": "boolean",
                                "description": "Whether to aggregate partial fills by time",
                                "default": False
                            }
                        },
                        "required": ["startTime"]
                    }
                ),
                Tool(
                    name="hyperliquid_get_user_funding",
                    description="Get user's funding payment history",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "userAddress": {
                                "type": "string",
                                "description": "User address (optional, defaults to configured account)"
                            },
                            "startTime": {
                                "type": "integer",
                                "description": "Start time in milliseconds (required)"
                            },
                            "endTime": {
                                "type": "integer",
                                "description": "End time in milliseconds (optional, defaults to current time)"
                            }
                        },
                        "required": ["startTime"]
                    }
                ),
                
                # Market Data
                Tool(
                    name="hyperliquid_get_meta",
                    description="Get exchange metadata including all available trading assets with their indices, names, max leverage, and trading parameters. Essential for mapping coin names to asset indices.",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="hyperliquid_get_all_mids",
                    description="Get current mid prices for all assets",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="hyperliquid_get_order_book",
                    description="Get order book (market depth) for a specific asset",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "coin": {
                                "type": "string",
                                "description": "Asset symbol (e.g., 'BTC', 'ETH', 'SOL')"
                            }
                        },
                        "required": ["coin"]
                    }
                ),
                Tool(
                    name="hyperliquid_get_recent_trades",
                    description="Get recent trades for a specific asset",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "coin": {
                                "type": "string",
                                "description": "Asset symbol (e.g., 'BTC', 'ETH', 'SOL')"
                            }
                        },
                        "required": ["coin"]
                    }
                ),
                Tool(
                    name="hyperliquid_get_historical_funding",
                    description="Get historical funding rates for an asset",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "coin": {
                                "type": "string",
                                "description": "Asset symbol (e.g., 'BTC', 'ETH', 'SOL')"
                            },
                            "startTime": {
                                "type": "integer",
                                "description": "Start time in milliseconds"
                            },
                            "endTime": {
                                "type": "integer",
                                "description": "End time in milliseconds (optional, defaults to current time)"
                            }
                        },
                        "required": ["coin", "startTime"]
                    }
                ),
                Tool(
                    name="hyperliquid_get_candles",
                    description="Get historical candle/OHLCV data for an asset",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "coin": {
                                "type": "string",
                                "description": "Asset symbol (e.g., 'BTC', 'ETH', 'SOL')"
                            },
                            "interval": {
                                "type": "string",
                                "description": "Candle interval",
                                "enum": ["1m", "5m", "15m", "1h", "4h", "1d"]
                            },
                            "startTime": {
                                "type": "integer",
                                "description": "Start time in milliseconds"
                            },
                            "endTime": {
                                "type": "integer",
                                "description": "End time in milliseconds (optional, defaults to current time)"
                            }
                        },
                        "required": ["coin", "interval", "startTime"]
                    }
                ),
                
                # Vault Management
                Tool(
                    name="hyperliquid_vault_details",
                    description="Get detailed information about a specific vault",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "vaultAddress": {
                                "type": "string",
                                "description": "Vault address in 42-character hexadecimal format"
                            }
                        },
                        "required": ["vaultAddress"]
                    }
                ),
                Tool(
                    name="hyperliquid_vault_performance",
                    description="Get performance metrics for a specific vault",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "vaultAddress": {
                                "type": "string",
                                "description": "Vault address in 42-character hexadecimal format"
                            },
                            "startTime": {
                                "type": "integer",
                                "description": "Start time in milliseconds"
                            },
                            "endTime": {
                                "type": "integer",
                                "description": "End time in milliseconds (optional, defaults to current time)"
                            }
                        },
                        "required": ["vaultAddress", "startTime"]
                    }
                ),
                
                # Utility
                Tool(
                    name="hyperliquid_get_server_time",
                    description="Get estimated server time",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[TextContent]:
            """Handle tool calls."""
            try:
                result = await self._handle_tool_call(name, arguments)
                return [TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )]
            except Exception as e:
                logger.error(f"Tool {name} failed: {e}", exc_info=True)
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "error": str(e),
                        "tool": name,
                        "arguments": arguments
                    }, indent=2)
                )]
    
    async def _handle_tool_call(self, name: str, arguments: dict) -> dict:
        """Route tool calls to appropriate handlers."""
        
        # Normalize integer parameters (convert float to int if needed)
        integer_params = ["asset", "oid", "startTime", "endTime", "twapId", "minutes"]
        for param in integer_params:
            if param in arguments and arguments[param] is not None:
                try:
                    arguments[param] = int(float(arguments[param]))
                    logger.debug(f"Normalized {param} parameter: {arguments[param]} (type: {type(arguments[param])})")
                except (ValueError, TypeError) as e:
                    logger.error(f"Failed to convert {param} parameter to integer: {arguments.get(param)} - {e}")
                    raise ValueError(f"Invalid {param} parameter: {arguments.get(param)}. Must be a valid integer.")
        
        # Get user address (use configured account if not provided)
        user_address = arguments.get("userAddress", self.account_address)
        
        # Account & Position Management
        if name == "hyperliquid_get_account_info":
            dex = arguments.get("dex", "")
            result = self.info.user_state(user_address, dex=dex)
            return {
                "message": "Account information retrieved successfully",
                "data": result,
                "summary": {
                    "accountValue": result["marginSummary"]["accountValue"],
                    "totalMarginUsed": result["marginSummary"]["totalMarginUsed"],
                    "withdrawable": result["withdrawable"],
                    "numberOfPositions": len(result["assetPositions"])
                }
            }
        
        elif name == "hyperliquid_get_positions":
            dex = arguments.get("dex", "")
            result = self.info.user_state(user_address, dex=dex)
            return {
                "message": "Positions retrieved successfully",
                "data": {
                    "assetPositions": result["assetPositions"],
                    "marginSummary": result["marginSummary"],
                    "crossMarginSummary": result.get("crossMarginSummary"),
                    "withdrawable": result["withdrawable"]
                },
                "summary": {
                    "numberOfPositions": len(result["assetPositions"]),
                    "accountValue": result["marginSummary"]["accountValue"],
                    "totalMarginUsed": result["marginSummary"]["totalMarginUsed"]
                }
            }
        
        elif name == "hyperliquid_get_balance":
            dex = arguments.get("dex", "")
            result = self.info.user_state(user_address, dex=dex)
            margin_summary = result["marginSummary"]
            return {
                "message": "Balance retrieved successfully",
                "data": {
                    "accountValue": margin_summary["accountValue"],
                    "totalMarginUsed": margin_summary["totalMarginUsed"],
                    "totalNtlPos": margin_summary["totalNtlPos"],
                    "totalRawUsd": margin_summary["totalRawUsd"],
                    "withdrawable": result["withdrawable"]
                },
                "summary": {
                    "accountValue": margin_summary["accountValue"],
                    "withdrawable": result["withdrawable"],
                    "availableBalance": str(float(margin_summary["accountValue"]) - float(margin_summary["totalMarginUsed"]))
                }
            }
        
        # Order Management
        elif name == "hyperliquid_place_order":
            asset = arguments["asset"]  # Already normalized to integer
            is_buy = arguments["isBuy"]
            size = float(arguments["size"])
            # Keep price as string if provided, convert to float for SDK
            price_str = arguments.get("price", "0")
            price = float(price_str) if price_str else 0.0
            reduce_only = arguments.get("reduceOnly", False)
            order_type = arguments.get("orderType", {"limit": {"tif": "Gtc"}})
            cloid_str = arguments.get("cloid")
            
            # Convert asset index to coin name
            meta = self.info.meta()
            coin_name = meta["universe"][asset]["name"]
            
            # Create cloid if provided
            cloid = Cloid(cloid_str) if cloid_str else None
            
            # Handle trigger orders: convert triggerPx string to float
            if "trigger" in order_type:
                trigger = order_type["trigger"]
                if "triggerPx" in trigger and isinstance(trigger["triggerPx"], str):
                    trigger["triggerPx"] = float(trigger["triggerPx"])
            
            result = self.exchange.order(
                name=coin_name,
                is_buy=is_buy,
                sz=size,
                limit_px=price,
                order_type=order_type,
                reduce_only=reduce_only,
                cloid=cloid
            )
            
            # Parse response
            order_info = self._parse_order_response(result)
            
            return {
                "message": f"Order placed for {coin_name}",
                "data": result,
                "orderInfo": order_info,
                "requestParams": arguments
            }
        
        elif name == "hyperliquid_place_bracket_order":
            asset = arguments["asset"]  # Already normalized to integer
            is_buy = arguments["isBuy"]
            size = float(arguments["size"])
            entry_price = float(arguments.get("entryPrice", 0))
            tp_price = float(arguments["takeProfitPrice"])
            sl_price = float(arguments["stopLossPrice"])
            reduce_only = arguments.get("reduceOnly", False)
            entry_order_type = arguments.get("entryOrderType", {"limit": {"tif": "Gtc"}})
            
            # Convert asset index to coin name
            meta = self.info.meta()
            coin_name = meta["universe"][asset]["name"]
            
            # Create order requests for bracket
            # Note: The SDK's exchange.order() expects floats, not strings
            # The SDK will handle the conversion to wire format internally
            orders = [
                # Entry order
                {
                    "coin": coin_name,
                    "is_buy": is_buy,
                    "sz": size,
                    "limit_px": entry_price,
                    "order_type": entry_order_type,
                    "reduce_only": reduce_only
                },
                # Take profit order (opposite side, reduce-only)
                {
                    "coin": coin_name,
                    "is_buy": not is_buy,
                    "sz": size,
                    "limit_px": tp_price,
                    "order_type": {"trigger": {"triggerPx": tp_price, "isMarket": False, "tpsl": "tp"}},
                    "reduce_only": True
                },
                # Stop loss order (opposite side, reduce-only)
                {
                    "coin": coin_name,
                    "is_buy": not is_buy,
                    "sz": size,
                    "limit_px": sl_price,
                    "order_type": {"trigger": {"triggerPx": sl_price, "isMarket": False, "tpsl": "sl"}},
                    "reduce_only": True
                }
            ]
            
            result = self.exchange.bulk_orders(orders)
            
            # Parse response for all three orders
            statuses = result.get("response", {}).get("data", {}).get("statuses", [])
            order_infos = []
            for idx, status in enumerate(statuses):
                order_type = ["entry", "take-profit", "stop-loss"][idx]
                info = self._parse_order_status(status)
                info["orderType"] = order_type
                order_infos.append(info)
            
            return {
                "message": "Bracket order placed successfully",
                "data": result,
                "orders": order_infos,
                "requestParams": arguments
            }
        
        elif name == "hyperliquid_cancel_order":
            coin = arguments["coin"]
            oid = arguments["oid"]  # Already normalized to integer
            
            result = self.exchange.cancel(coin, oid)
            
            return {
                "message": f"Order {oid} cancelled for {coin}",
                "data": result,
                "cancelledOrder": {
                    "coin": coin,
                    "orderId": oid
                }
            }
        
        elif name == "hyperliquid_cancel_all_orders":
            dex = arguments.get("dex", "")
            
            # Get all open orders
            open_orders = self.info.open_orders(user_address, dex=dex)
            
            if not open_orders:
                return {
                    "message": "No open orders to cancel",
                    "data": {"status": "ok", "response": {"data": {"statuses": []}}},
                    "cancelledCount": 0
                }
            
            # Build cancel requests
            cancel_requests = [
                {"coin": order["coin"], "oid": order["oid"]}
                for order in open_orders
            ]
            
            result = self.exchange.bulk_cancel(cancel_requests)
            
            return {
                "message": f"Cancelled {len(cancel_requests)} orders",
                "data": result,
                "cancelledCount": len(cancel_requests)
            }
        
        elif name == "hyperliquid_modify_order":
            oid = arguments["oid"]  # Already normalized to integer
            coin = arguments["coin"]
            is_buy = arguments["isBuy"]
            size = float(arguments["size"])
            price = float(arguments["price"])
            reduce_only = arguments.get("reduceOnly", False)
            order_type = arguments.get("orderType", {"limit": {"tif": "Gtc"}})
            
            result = self.exchange.modify_order(
                oid=oid,
                name=coin,
                is_buy=is_buy,
                sz=size,
                limit_px=price,
                order_type=order_type,
                reduce_only=reduce_only
            )
            
            return {
                "message": f"Order {oid} modified successfully",
                "data": result,
                "modifiedOrder": {
                    "orderId": oid,
                    "coin": coin,
                    "newPrice": price,
                    "newSize": size
                }
            }
        
        elif name == "hyperliquid_place_twap_order":
            # Note: TWAP requires special handling, not directly supported in basic SDK
            # This would need the TWAP action structure
            raise NotImplementedError("TWAP orders require additional implementation")
        
        elif name == "hyperliquid_cancel_twap_order":
            raise NotImplementedError("TWAP cancellation requires additional implementation")
        
        # Order Queries
        elif name == "hyperliquid_get_open_orders":
            dex = arguments.get("dex", "")
            result = self.info.open_orders(user_address, dex=dex)
            
            return {
                "message": "Open orders retrieved successfully",
                "data": result,
                "summary": {
                    "numberOfOrders": len(result) if result else 0
                }
            }
        
        elif name == "hyperliquid_get_order_status":
            oid = arguments["oid"]  # Already normalized to integer
            result = self.info.query_order_by_oid(user_address, oid)
            
            return {
                "message": "Order status retrieved successfully",
                "data": result,
                "orderId": oid
            }
        
        elif name == "hyperliquid_get_user_fills":
            start_time = arguments["startTime"]  # Already normalized to integer
            end_time = arguments.get("endTime")  # Already normalized to integer if present
            aggregate = arguments.get("aggregateByTime", False)
            
            result = self.info.user_fills_by_time(
                user=user_address,
                start_time=start_time,
                end_time=end_time,
                aggregate_by_time=aggregate
            )
            
            return {
                "message": "User fills retrieved successfully",
                "data": result,
                "summary": {
                    "numberOfFills": len(result) if result else 0,
                    "timeRange": {
                        "startTime": start_time,
                        "endTime": end_time or "current"
                    }
                }
            }
        
        elif name == "hyperliquid_get_user_funding":
            start_time = arguments["startTime"]  # Already normalized to integer
            end_time = arguments.get("endTime")  # Already normalized to integer if present
            
            result = self.info.user_funding(
                user=user_address,
                start_time=start_time,
                end_time=end_time
            )
            
            return {
                "message": "User funding retrieved successfully",
                "data": result,
                "summary": {
                    "numberOfEntries": len(result) if result else 0,
                    "timeRange": {
                        "startTime": start_time,
                        "endTime": end_time or "current"
                    }
                }
            }
        
        # Market Data
        elif name == "hyperliquid_get_meta":
            result = self.info.meta()
            
            # Format universe with indices
            assets_with_indices = [
                {
                    "index": idx,
                    "name": asset["name"],
                    "maxLeverage": asset["maxLeverage"],
                    "onlyIsolated": asset.get("onlyIsolated", False)
                }
                for idx, asset in enumerate(result["universe"])
            ]
            
            return {
                "message": "Exchange metadata retrieved successfully",
                "data": result,
                "summary": {
                    "numberOfAssets": len(result["universe"]),
                    "assetsWithIndices": assets_with_indices
                }
            }
        
        elif name == "hyperliquid_get_all_mids":
            result = self.info.all_mids()
            
            return {
                "message": "All mid prices retrieved successfully",
                "data": result,
                "summary": {
                    "numberOfAssets": len(result)
                }
            }
        
        elif name == "hyperliquid_get_order_book":
            coin = arguments["coin"]
            result = self.info.l2_snapshot(coin)
            
            return {
                "message": f"Order book for {coin} retrieved successfully",
                "data": result,
                "summary": {
                    "coin": coin,
                    "bidsCount": len(result["levels"][0]) if result.get("levels") else 0,
                    "asksCount": len(result["levels"][1]) if result.get("levels") else 0
                }
            }
        
        elif name == "hyperliquid_get_recent_trades":
            coin = arguments["coin"]
            result = self.info.recent_trades(coin)
            
            return {
                "message": f"Recent trades for {coin} retrieved successfully",
                "data": result,
                "summary": {
                    "coin": coin,
                    "numberOfTrades": len(result) if result else 0
                }
            }
        
        elif name == "hyperliquid_get_historical_funding":
            coin = arguments["coin"]
            start_time = int(arguments["startTime"])  # Ensure integer
            end_time = int(arguments["endTime"]) if arguments.get("endTime") else None
            
            result = self.info.funding_history(
                coin=coin,
                start_time=start_time,
                end_time=end_time
            )
            
            return {
                "message": f"Historical funding for {coin} retrieved successfully",
                "data": result,
                "summary": {
                    "coin": coin,
                    "numberOfEntries": len(result) if result else 0
                }
            }
        
        elif name == "hyperliquid_get_candles":
            coin = arguments["coin"]
            interval = arguments["interval"]
            start_time = int(arguments["startTime"])  # Ensure integer
            end_time = int(arguments["endTime"]) if arguments.get("endTime") else None
            
            result = self.info.candles_snapshot(
                coin=coin,
                interval=interval,
                start_time=start_time,
                end_time=end_time
            )
            
            return {
                "message": f"Candles for {coin} ({interval}) retrieved successfully",
                "data": result,
                "summary": {
                    "coin": coin,
                    "interval": interval,
                    "numberOfCandles": len(result) if result else 0
                }
            }
        
        # Vault Management
        elif name == "hyperliquid_vault_details":
            vault_address = arguments["vaultAddress"]
            result = self.info.vault_details(vault_address)
            
            return {
                "message": f"Vault details for {vault_address} retrieved successfully",
                "data": result,
                "vaultAddress": vault_address
            }
        
        elif name == "hyperliquid_vault_performance":
            vault_address = arguments["vaultAddress"]
            start_time = int(arguments["startTime"])  # Ensure integer
            end_time = int(arguments["endTime"]) if arguments.get("endTime") else None
            
            result = self.info.vault_details(vault_address, start_time, end_time)
            
            return {
                "message": f"Vault performance for {vault_address} retrieved successfully",
                "data": result,
                "summary": {
                    "vaultAddress": vault_address,
                    "timeRange": {
                        "startTime": start_time,
                        "endTime": end_time or "current"
                    }
                }
            }
        
        # Utility
        elif name == "hyperliquid_get_server_time":
            import time
            server_time = int(time.time() * 1000)
            
            return {
                "message": "Server time retrieved successfully",
                "data": {
                    "serverTime": server_time
                }
            }
        
        else:
            raise ValueError(f"Unknown tool: {name}")
    
    def _parse_order_response(self, result: dict) -> dict:
        """Parse order placement response."""
        order_status = result.get("response", {}).get("data", {}).get("statuses", [{}])[0]
        return self._parse_order_status(order_status)
    
    def _parse_order_status(self, status: dict) -> dict:
        """Parse a single order status."""
        if "resting" in status:
            return {
                "status": "resting",
                "orderId": status["resting"]["oid"],
                "message": "Order placed and resting on order book"
            }
        elif "filled" in status:
            return {
                "status": "filled",
                "orderId": status["filled"]["oid"],
                "totalSize": status["filled"]["totalSz"],
                "averagePrice": status["filled"]["avgPx"],
                "message": "Order filled successfully"
            }
        elif "error" in status:
            return {
                "status": "error",
                "error": status["error"],
                "message": "Order placement failed"
            }
        else:
            return {
                "status": "unknown",
                "rawStatus": status
            }
    
    async def run(self):
        """Run the MCP server."""
        async with stdio_server() as (read_stream, write_stream):
            logger.info("Hyperliquid MCP Server started")
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )


def main():
    """Main entry point."""
    try:
        server = HyperliquidMCPServer()
        asyncio.run(server.run())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
