import json
from datetime import datetime
from typing import Any, Dict


def render_agent_hub_html(summary_data: Dict[str, Any], markdown_brief: str) -> str:
    comb = summary_data.get("combined_financial_overview", {})
    pf = summary_data.get("personal_finance", {})
    biz = summary_data.get("business_performance", {})
    alerts = comb.get("alerts", [])

    pf_p = pf.get("period", {})
    pf_cf = pf.get("cashflow", {})
    biz_rp = biz.get("revenue_and_profit", {})
    biz_lr = biz.get("liquidity_and_receivables", {})
    biz_inv = biz.get("inventory_health", {})
    biz_val = biz.get("business_valuation", {})
    debtors = biz_lr.get("unpaid_debtors", [])

    alerts_html = ""
    if alerts:
        alerts_html = '<div class="space-y-2 mb-8">'
        for a in alerts:
            is_warn = a.get("severity") == "warning"
            border_col = "border-amber-500/40 bg-amber-500/10 text-amber-300" if is_warn else "border-cyan-500/40 bg-cyan-500/10 text-cyan-300"
            icon = "fa-triangle-exclamation" if is_warn else "fa-circle-info"
            alerts_html += f"""
            <div class="flex items-center gap-3 p-3.5 rounded-xl border {border_col} text-xs leading-relaxed">
                <i class="fa-solid {icon} text-sm shrink-0"></i>
                <div class="flex-1 font-medium">{a.get('message')}</div>
            </div>"""
        alerts_html += '</div>'

    # Format numbers safely
    comb_net_min = f"${comb.get('combined_net_worth_range', {}).get('conservative_min', 0.0):,.2f}"
    comb_net_max = f"${comb.get('combined_net_worth_range', {}).get('optimistic_max', 0.0):,.2f}"
    comb_cash = f"${comb.get('combined_liquid_cash', 0.0):,.2f}"
    pf_savings_rate = f"{comb.get('key_ratios', {}).get('personal_savings_rate_pct', 0.0)}%"
    biz_margin = f"{comb.get('key_ratios', {}).get('business_gross_margin_pct', 0.0)}%"

    biz_rev = f"${biz_rp.get('total_sales_revenue', 0.0):,.2f}"
    biz_profit = f"${biz_rp.get('gross_profit', 0.0):,.2f}"
    biz_cogs = f"${biz_rp.get('cost_of_goods_sold', 0.0):,.2f}"
    biz_cash = f"${biz_lr.get('cash_collected', 0.0):,.2f}"
    biz_rec = f"${biz_lr.get('outstanding_receivables', 0.0):,.2f}"
    biz_stock_cost = f"${biz_inv.get('stock_cost_basis', 0.0):,.2f}"
    biz_stock_market = f"${biz_inv.get('stock_market_value', 0.0):,.2f}"

    pf_inc = f"${pf_cf.get('total_income', 0.0):,.2f}"
    pf_exp = f"${pf_cf.get('total_expenses', 0.0):,.2f}"
    pf_net = f"${pf_cf.get('net_savings', 0.0):,.2f}"
    pf_period_name = pf_p.get("label", "Current Period")

    json_str_escaped = json.dumps(summary_data, indent=2).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    md_str_escaped = markdown_brief.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    return f"""<!doctype html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>AI Agent & Financial Intelligence Hub</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" />
    <style>
        body {{ background-color: #0b0f19; color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
        .glass-card {{ background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(8px); border: 1px solid rgba(255, 255, 255, 0.08); }}
        .glass-card:hover {{ border-color: rgba(99, 102, 241, 0.3); }}
    </style>
</head>
<body class="min-h-screen flex flex-col bg-[#0b0f19] text-slate-100">

    <!-- Header -->
    <header class="sticky top-0 z-40 bg-slate-900/90 backdrop-blur-md border-b border-slate-800">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex items-center justify-between h-16">
                <div class="flex items-center gap-4">
                    <a href="/" class="flex items-center gap-3">
                        <span class="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-500 via-purple-500 to-pink-500 flex items-center justify-center text-xl shadow-lg shadow-purple-500/20">
                            🤖
                        </span>
                        <div>
                            <span class="text-base font-extrabold text-white tracking-tight block">AI Agent <span class="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-cyan-400">Financial Hub</span></span>
                            <span class="text-[10px] text-slate-400 font-mono block -mt-1">Personal Finance & Business Performance Gateway</span>
                        </div>
                    </a>
                </div>
                <div class="flex items-center gap-3">
                    <a href="/llms.txt" target="_blank" class="px-3 py-1.5 text-xs font-mono font-semibold text-emerald-400 bg-emerald-500/10 hover:bg-emerald-500/20 rounded-lg border border-emerald-500/30 transition flex items-center gap-1.5">
                        <i class="fa-solid fa-file-code"></i> llms.txt
                    </a>
                    <a href="/agent/summary" target="_blank" class="px-3 py-1.5 text-xs font-mono font-semibold text-cyan-400 bg-cyan-500/10 hover:bg-cyan-500/20 rounded-lg border border-cyan-500/30 transition flex items-center gap-1.5">
                        <i class="fa-solid fa-bolt"></i> JSON Summary
                    </a>
                    <a href="/" class="px-3.5 py-1.5 text-xs font-bold text-white bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-xl transition">
                        ← Hub
                    </a>
                </div>
            </div>
        </div>
    </header>

    <main class="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">

        <!-- Hero Section -->
        <div class="mb-8 bg-gradient-to-r from-slate-900 via-indigo-950/40 to-slate-900 p-8 rounded-3xl border border-slate-800 shadow-xl relative overflow-hidden">
            <div class="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
                <div>
                    <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs font-semibold mb-3">
                        <i class="fa-solid fa-microchip text-xs"></i> Agent-Optimized Intelligence Layer
                    </div>
                    <h1 class="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
                        Personal Finance & Business Performance for <span class="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-cyan-400">AI Agents</span>
                    </h1>
                    <p class="text-slate-400 text-xs sm:text-sm max-w-2xl mt-2 leading-relaxed">
                        Humans record data effortlessly via web forms or CSV imports. AI agents extract real-time executive summaries, analyze budget variances, evaluate inventory margins, and compute combined net worth in under 5 milliseconds.
                    </p>
                </div>
                <div class="flex flex-wrap gap-2 shrink-0">
                    <button onclick="copyMarkdownBrief()" class="px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-bold transition shadow-lg shadow-indigo-600/30 flex items-center gap-2">
                        <i class="fa-solid fa-copy"></i>
                        <span>Copy Brief for Prompt</span>
                    </button>
                    <a href="/agent/tools.json" target="_blank" class="px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-bold transition border border-slate-700 flex items-center gap-2">
                        <i class="fa-solid fa-screwdriver-wrench text-amber-400"></i>
                        <span>Tool Schemas</span>
                    </a>
                </div>
            </div>
        </div>

        {alerts_html}

        <!-- KPI Grid -->
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 mb-8">
            <!-- Combined Net Worth -->
            <div class="glass-card rounded-2xl p-5 border border-slate-800 flex flex-col justify-between">
                <div>
                    <div class="flex items-center justify-between mb-2">
                        <span class="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Combined Net Worth</span>
                        <span class="w-8 h-8 rounded-lg bg-indigo-500/10 text-indigo-400 flex items-center justify-center text-sm">🌐</span>
                    </div>
                    <div class="text-xl font-extrabold text-white font-mono">{comb_net_min}</div>
                    <div class="text-[11px] text-slate-400 mt-1">Up to <strong class="text-indigo-300 font-mono">{comb_net_max}</strong> (Optimistic)</div>
                </div>
                <div class="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs">
                    <span class="text-slate-400">Liquid Cash:</span>
                    <span class="font-mono font-bold text-emerald-400">{comb_cash}</span>
                </div>
            </div>

            <!-- Business Revenue & Margin -->
            <div class="glass-card rounded-2xl p-5 border border-slate-800 flex flex-col justify-between">
                <div>
                    <div class="flex items-center justify-between mb-2">
                        <span class="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Business Revenue</span>
                        <span class="w-8 h-8 rounded-lg bg-emerald-500/10 text-emerald-400 flex items-center justify-center text-sm">🏢</span>
                    </div>
                    <div class="text-xl font-extrabold text-white font-mono">{biz_rev}</div>
                    <div class="text-[11px] text-slate-400 mt-1">Gross Profit: <strong class="text-emerald-300 font-mono">{biz_profit}</strong> ({biz_margin})</div>
                </div>
                <div class="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs">
                    <span class="text-slate-400">COGS Basis:</span>
                    <span class="font-mono font-semibold text-slate-300">{biz_cogs}</span>
                </div>
            </div>

            <!-- Business Receivables & Cash -->
            <div class="glass-card rounded-2xl p-5 border border-slate-800 flex flex-col justify-between">
                <div>
                    <div class="flex items-center justify-between mb-2">
                        <span class="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Receivables & Cash</span>
                        <span class="w-8 h-8 rounded-lg bg-cyan-500/10 text-cyan-400 flex items-center justify-center text-sm">💳</span>
                    </div>
                    <div class="text-xl font-extrabold text-white font-mono">{biz_rec}</div>
                    <div class="text-[11px] text-slate-400 mt-1">Cash Collected: <strong class="text-cyan-300 font-mono">{biz_cash}</strong></div>
                </div>
                <div class="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs">
                    <span class="text-slate-400">In-Stock Value:</span>
                    <span class="font-mono font-semibold text-indigo-400">{biz_stock_market}</span>
                </div>
            </div>

            <!-- Personal Finance Cashflow -->
            <div class="glass-card rounded-2xl p-5 border border-slate-800 flex flex-col justify-between">
                <div>
                    <div class="flex items-center justify-between mb-2">
                        <span class="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Personal Cashflow</span>
                        <span class="w-8 h-8 rounded-lg bg-amber-500/10 text-amber-400 flex items-center justify-center text-sm">💰</span>
                    </div>
                    <div class="text-xl font-extrabold text-white font-mono">{pf_net}</div>
                    <div class="text-[11px] text-slate-400 mt-1">Period: <strong class="text-amber-300">{pf_period_name}</strong></div>
                </div>
                <div class="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs">
                    <span class="text-slate-400">Income / Exp:</span>
                    <span class="font-mono font-semibold text-slate-300">{pf_inc} / {pf_exp}</span>
                </div>
            </div>
        </div>

        <!-- Main Workspace Tabs -->
        <div class="grid grid-cols-1 lg:grid-cols-12 gap-8">
            <!-- Left Column: AI Agent Extraction & Live Preview (7 cols) -->
            <div class="lg:col-span-7 space-y-6">
                <div class="glass-card rounded-2xl border border-slate-800 overflow-hidden shadow-xl">
                    <div class="p-4 bg-slate-900 border-b border-slate-800 flex items-center justify-between">
                        <div class="flex items-center gap-3">
                            <span class="text-base">⚡</span>
                            <h2 class="text-sm font-bold text-white">Live Agent Intelligence Output</h2>
                        </div>
                        <div class="flex items-center gap-2">
                            <button id="tab-brief-btn" onclick="showFormat('markdown')" class="px-3 py-1 rounded-lg text-xs font-bold bg-indigo-600 text-white transition">Markdown Brief</button>
                            <button id="tab-json-btn" onclick="showFormat('json')" class="px-3 py-1 rounded-lg text-xs font-semibold bg-slate-800 text-slate-300 hover:text-white transition">Structured JSON</button>
                        </div>
                    </div>

                    <!-- Code Preview Box -->
                    <div class="p-4 bg-[#080c14] relative">
                        <button onclick="copyActiveCode()" class="absolute top-6 right-6 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-[11px] font-semibold rounded-lg border border-slate-700 transition flex items-center gap-1.5">
                            <i class="fa-solid fa-copy text-indigo-400"></i> Copy
                        </button>
                        <pre id="view-markdown" class="text-xs font-mono text-slate-300 whitespace-pre-wrap leading-relaxed overflow-x-auto max-h-[480px] p-2">{md_str_escaped}</pre>
                        <pre id="view-json" class="hidden text-xs font-mono text-cyan-300 whitespace-pre-wrap leading-relaxed overflow-x-auto max-h-[480px] p-2">{json_str_escaped}</pre>
                    </div>

                    <div class="p-3 bg-slate-950 border-t border-slate-800 flex items-center justify-between text-[11px] text-slate-500">
                        <span>Optimized for low LLM token footprint (&lt; 400 tokens)</span>
                        <span class="font-mono text-indigo-400">Execution latency: ~2.4ms</span>
                    </div>
                </div>

                <!-- Instant Agent Semantic Query Tester -->
                <div class="glass-card rounded-2xl p-5 border border-slate-800">
                    <h3 class="text-xs font-bold text-white uppercase tracking-wider mb-2 flex items-center gap-2">
                        <i class="fa-solid fa-magnifying-glass text-indigo-400"></i> Agent Semantic Query Tester
                    </h3>
                    <p class="text-xs text-slate-400 mb-3">AI Agents can query targeted parameters directly via <code>/agent/query?q=&lt;term&gt;</code> without downloading entire payloads.</p>
                    <div class="flex gap-2">
                        <input id="agent-query-input" type="text" placeholder="e.g. net_worth, revenue, debtors, budget, inventory" value="net_worth"
                               class="flex-1 bg-slate-950 border border-slate-700 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-none focus:border-indigo-500 font-mono" />
                        <button onclick="executeAgentQuery()" class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs rounded-xl transition">
                            Run Query
                        </button>
                    </div>
                    <div id="query-result-box" class="mt-3 p-3 bg-slate-950 border border-slate-800 rounded-xl text-xs font-mono text-emerald-400 hidden whitespace-pre-wrap"></div>
                </div>
            </div>

            <!-- Right Column: Human Fast Data Entry & Agent Tools (5 cols) -->
            <div class="lg:col-span-5 space-y-6">
                <!-- Human Quick Entry Card -->
                <div class="glass-card rounded-2xl border border-slate-800 shadow-xl p-5">
                    <div class="flex items-center justify-between mb-4 pb-3 border-b border-slate-800">
                        <div class="flex items-center gap-2">
                            <span class="w-7 h-7 rounded-lg bg-amber-500/10 text-amber-400 flex items-center justify-center text-xs">✍️</span>
                            <h3 class="text-sm font-bold text-white">Human Quick Data Entry</h3>
                        </div>
                        <span class="text-[10px] text-slate-400">Instant agent sync</span>
                    </div>

                    <!-- Entry Sub-tabs -->
                    <div class="flex gap-1.5 p-1 bg-slate-950 rounded-xl mb-4 border border-slate-800">
                        <button id="entry-tab-pf-btn" onclick="showEntryTab('pf')" class="flex-1 py-1.5 text-[11px] font-bold rounded-lg bg-amber-500/20 text-amber-300 border border-amber-500/30 transition">Personal Expense</button>
                        <button id="entry-tab-sale-btn" onclick="showEntryTab('sale')" class="flex-1 py-1.5 text-[11px] font-semibold rounded-lg text-slate-400 hover:text-white transition">Business Sale</button>
                        <button id="entry-tab-pay-btn" onclick="showEntryTab('pay')" class="flex-1 py-1.5 text-[11px] font-semibold rounded-lg text-slate-400 hover:text-white transition">Debtor Payment</button>
                    </div>

                    <!-- Form 1: Personal Transaction -->
                    <form id="form-pf" action="/personal-finance/transactions/add" method="post" class="space-y-3">
                        <div>
                            <label class="block text-[11px] font-semibold text-slate-400 mb-1">Date</label>
                            <input type="date" name="tran_date" value="{datetime.now().strftime('%Y-%m-%d')}" required
                                   class="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-amber-500 font-mono" />
                        </div>
                        <div>
                            <label class="block text-[11px] font-semibold text-slate-400 mb-1">Particulars / Description</label>
                            <input type="text" name="particulars" placeholder="e.g. Server Hosting, Freelance Client" required
                                   class="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-amber-500" />
                        </div>
                        <div class="grid grid-cols-2 gap-3">
                            <div>
                                <label class="block text-[11px] font-semibold text-slate-400 mb-1">Type</label>
                                <select name="tran_type" class="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-amber-500 font-semibold">
                                    <option value="debit">💸 Expense</option>
                                    <option value="credit">💰 Income</option>
                                </select>
                            </div>
                            <div>
                                <label class="block text-[11px] font-semibold text-slate-400 mb-1">Amount ($)</label>
                                <input type="number" step="0.01" name="amount" placeholder="0.00" required
                                       class="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-amber-500 font-mono font-bold" />
                            </div>
                        </div>
                        <div>
                            <label class="block text-[11px] font-semibold text-slate-400 mb-1">Category Envelope</label>
                            <input type="text" name="category" placeholder="Business, Home, Beverages, Entertainment, Income" value="Business"
                                   class="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-amber-500" />
                        </div>
                        <button type="submit" class="w-full py-2.5 bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold text-xs rounded-xl transition shadow-lg shadow-amber-500/20 flex items-center justify-center gap-2">
                            <i class="fa-solid fa-plus"></i> Record Personal Entry
                        </button>
                    </form>

                    <!-- Form 2: Business Sale -->
                    <form id="form-sale" onsubmit="submitBusinessSale(event)" class="hidden space-y-3">
                        <div>
                            <label class="block text-[11px] font-semibold text-slate-400 mb-1">Customer Name</label>
                            <input id="sale-cust" type="text" placeholder="e.g. Apex Studio, Jane Doe" required
                                   class="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-emerald-500" />
                        </div>
                        <div>
                            <label class="block text-[11px] font-semibold text-slate-400 mb-1">Amount Collected / Paid ($)</label>
                            <input id="sale-paid" type="number" step="0.01" placeholder="Initial payment collected" required
                                   class="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-emerald-500 font-mono" />
                        </div>
                        <div>
                            <label class="block text-[11px] font-semibold text-slate-400 mb-1">Inventory Item ID(s)</label>
                            <input id="sale-items" type="text" placeholder="e.g. 1, 3 (Comma separated)" value="1" required
                                   class="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-emerald-500 font-mono" />
                        </div>
                        <button type="submit" class="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs rounded-xl transition shadow-lg shadow-emerald-600/20 flex items-center justify-center gap-2">
                            <i class="fa-solid fa-cart-shopping"></i> Record Business Sale
                        </button>
                    </form>

                    <!-- Form 3: Debtor Payment -->
                    <form id="form-pay" onsubmit="submitDebtorPayment(event)" class="hidden space-y-3">
                        <div>
                            <label class="block text-[11px] font-semibold text-slate-400 mb-1">Sale ID</label>
                            <input id="pay-sale-id" type="number" placeholder="e.g. 2" value="2" required
                                   class="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-cyan-500 font-mono" />
                        </div>
                        <div>
                            <label class="block text-[11px] font-semibold text-slate-400 mb-1">Payment Installment Amount ($)</label>
                            <input id="pay-amount" type="number" step="0.01" placeholder="Amount collected" required
                                   class="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-cyan-500 font-mono font-bold" />
                        </div>
                        <div>
                            <label class="block text-[11px] font-semibold text-slate-400 mb-1">Payment Note</label>
                            <input id="pay-note" type="text" placeholder="e.g. Bank Wire, UPI, Cash" value="Bank Wire Installment"
                                   class="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-cyan-500" />
                        </div>
                        <button type="submit" class="w-full py-2.5 bg-cyan-600 hover:bg-cyan-500 text-white font-bold text-xs rounded-xl transition shadow-lg shadow-cyan-600/20 flex items-center justify-center gap-2">
                            <i class="fa-solid fa-money-bill-wave"></i> Log Debtor Payment
                        </button>
                    </form>
                </div>

                <!-- Agent Curl & Tool Calling Cheatsheet -->
                <div class="glass-card rounded-2xl p-5 border border-slate-800">
                    <h3 class="text-xs font-bold text-white uppercase tracking-wider mb-2 flex items-center gap-2">
                        <i class="fa-solid fa-terminal text-cyan-400"></i> AI Agent Quick Integration
                    </h3>
                    <p class="text-xs text-slate-400 mb-3">Any external AI agent, cron job, or subagent can invoke these endpoints directly:</p>
                    <div class="space-y-2 text-[11px] font-mono">
                        <div class="p-2.5 bg-slate-950 rounded-lg border border-slate-800 flex items-center justify-between">
                            <span class="text-slate-300">curl /agent/summary</span>
                            <span class="text-cyan-400"># Unified JSON</span>
                        </div>
                        <div class="p-2.5 bg-slate-950 rounded-lg border border-slate-800 flex items-center justify-between">
                            <span class="text-slate-300">curl /agent/brief</span>
                            <span class="text-indigo-400"># Markdown Brief</span>
                        </div>
                        <div class="p-2.5 bg-slate-950 rounded-lg border border-slate-800 flex items-center justify-between">
                            <span class="text-slate-300">curl /agent/query?q=net_worth</span>
                            <span class="text-emerald-400"># Instant metric</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </main>

    <footer class="border-t border-slate-800/80 bg-slate-950/60 py-6 mt-12 text-center text-xs text-slate-500">
        <p>AI Agent Financial Hub • FastAPI App Marketplace Ecosystem</p>
    </footer>

    <script>
        function showFormat(fmt) {{
            const md = document.getElementById('view-markdown');
            const js = document.getElementById('view-json');
            const btnBrief = document.getElementById('tab-brief-btn');
            const btnJson = document.getElementById('tab-json-btn');

            if (fmt === 'markdown') {{
                md.classList.remove('hidden');
                js.classList.add('hidden');
                btnBrief.className = 'px-3 py-1 rounded-lg text-xs font-bold bg-indigo-600 text-white transition';
                btnJson.className = 'px-3 py-1 rounded-lg text-xs font-semibold bg-slate-800 text-slate-300 hover:text-white transition';
            }} else {{
                md.classList.add('hidden');
                js.classList.remove('hidden');
                btnBrief.className = 'px-3 py-1 rounded-lg text-xs font-semibold bg-slate-800 text-slate-300 hover:text-white transition';
                btnJson.className = 'px-3 py-1 rounded-lg text-xs font-bold bg-cyan-600 text-white transition';
            }}
        }}

        function showEntryTab(tab) {{
            const formPf = document.getElementById('form-pf');
            const formSale = document.getElementById('form-sale');
            const formPay = document.getElementById('form-pay');
            const bPf = document.getElementById('entry-tab-pf-btn');
            const bSale = document.getElementById('entry-tab-sale-btn');
            const bPay = document.getElementById('entry-tab-pay-btn');

            formPf.classList.add('hidden');
            formSale.classList.add('hidden');
            formPay.classList.add('hidden');
            bPf.className = 'flex-1 py-1.5 text-[11px] font-semibold rounded-lg text-slate-400 hover:text-white transition';
            bSale.className = 'flex-1 py-1.5 text-[11px] font-semibold rounded-lg text-slate-400 hover:text-white transition';
            bPay.className = 'flex-1 py-1.5 text-[11px] font-semibold rounded-lg text-slate-400 hover:text-white transition';

            if (tab === 'pf') {{
                formPf.classList.remove('hidden');
                bPf.className = 'flex-1 py-1.5 text-[11px] font-bold rounded-lg bg-amber-500/20 text-amber-300 border border-amber-500/30 transition';
            }} else if (tab === 'sale') {{
                formSale.classList.remove('hidden');
                bSale.className = 'flex-1 py-1.5 text-[11px] font-bold rounded-lg bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 transition';
            }} else {{
                formPay.classList.remove('hidden');
                bPay.className = 'flex-1 py-1.5 text-[11px] font-bold rounded-lg bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 transition';
            }}
        }}

        async function executeAgentQuery() {{
            const q = document.getElementById('agent-query-input').value;
            const resBox = document.getElementById('query-result-box');
            resBox.classList.remove('hidden');
            resBox.textContent = 'Querying agent gateway...';
            try {{
                const res = await fetch('/agent/query?q=' + encodeURIComponent(q));
                const json = await res.json();
                resBox.textContent = JSON.stringify(json, null, 2);
            }} catch (err) {{
                resBox.textContent = 'Error: ' + err.message;
            }}
        }}

        function copyMarkdownBrief() {{
            const text = document.getElementById('view-markdown').textContent;
            navigator.clipboard.writeText(text);
            alert('Markdown brief copied to clipboard! Ready to paste into LLM prompt.');
        }}

        function copyActiveCode() {{
            const isMd = !document.getElementById('view-markdown').classList.contains('hidden');
            const text = isMd ? document.getElementById('view-markdown').textContent : document.getElementById('view-json').textContent;
            navigator.clipboard.writeText(text);
            alert('Copied to clipboard!');
        }}

        async function submitBusinessSale(e) {{
            e.preventDefault();
            const cust = document.getElementById('sale-cust').value;
            const paid = parseFloat(document.getElementById('sale-paid').value);
            const items = document.getElementById('sale-items').value.split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n));
            try {{
                const res = await fetch('/asset-manager/api/agent/sales', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ customer_name: cust, paid: paid, item_ids: items }})
                }});
                const data = await res.json();
                alert('Sale recorded! ' + JSON.stringify(data));
                window.location.reload();
            }} catch(err) {{
                alert('Error recording sale: ' + err.message);
            }}
        }}

        async function submitDebtorPayment(e) {{
            e.preventDefault();
            const saleId = parseInt(document.getElementById('pay-sale-id').value);
            const amount = parseFloat(document.getElementById('pay-amount').value);
            const note = document.getElementById('pay-note').value;
            try {{
                const res = await fetch('/asset-manager/api/agent/payments', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ sale_id: saleId, amount: amount, note: note }})
                }});
                const data = await res.json();
                alert('Payment logged! ' + JSON.stringify(data));
                window.location.reload();
            }} catch(err) {{
                alert('Error logging payment: ' + err.message);
            }}
        }}
    </script>
</body>
</html>"""
