# 📖 User Manual — Asset Manager

*How to use the shop's memory — written for everyone, no tech knowledge needed.*
*In-app version: open the tool and click **📖 Manual** in the top bar (or visit `/manual`).*

---

## What is this tool for?

You buy things, you sell things, and sometimes money comes late.
This tool is your shop's memory. It remembers:

- what you bought, from whom, and what it cost
- what you are selling each item for
- what you have sold, and to whom
- who still owes you money
- how much your whole business is worth today

Nothing here is permanent on the first try — every number can be corrected later on the edit screen. So don't worry about making mistakes. Just start.

## The seven pages

| Page | What it is for |
|---|---|
| 🏠 **Dashboard** (`/`) | The big picture. Your shop's worth, stock value, cash received, money owed to you. |
| 📦 **Batches** (`/batch`) | Start here when a fresh lot arrives. A batch = one supplier, one purchase, one date. |
| 💻 **Items** (`/all-items`) | Every item in history, newest first. Click an item to see or fix its details and photos. |
| 💰 **Sales** (`/sales`) | Sell one or many items to a customer — including the money they gave you today. |
| 🧾 **Ledger** (`/ledger`) | Customers who still owe you money. Add each payment when it arrives. |
| 🛠️ **Assets** (`/assets-list`) | Things you keep and don't sell — tools, equipment. They count toward your worth but never appear in Sales. |
| 📖 **Manual** (`/manual`) | You are here. |

---

## 1. I bought some new items — how do I record them?

Every purchase starts as a **batch**. A batch is simply "the items I got from one supplier, on one day".

1. Open **Batches**.
2. Fill the empty row at the top: **Supplier** (e.g. *Neha Trading*), **Description** (e.g. *September laptop lot*), and the date (today's date is already filled for you).
3. Click **Add Batch**. Your batch appears in the list below.
4. Find your batch in the list and open the button to **add items**.
5. For each item, fill the row:

   | Field | What to type | Example |
   |---|---|---|
   | Brand | The maker | Lenovo |
   | Model | Which model | ThinkPad T490 |
   | Serial number | From the item or the label — must be **unique** | PF3XYZ12 |
   | Purchase price | What you paid *this supplier* for it | 22000.00 |
   | Profit | Either a plain amount `5000`, or a percent `15%` of the purchase price | 15% |

6. Save. Repeat for the next item. One row per item.

> 💡 **If the serial number is not known yet** (e.g. it's inside the box), type a temporary one like *NA-1*, then fix it later on the item's edit screen.

## 2. I spent extra on an item, or my details are wrong

Spend money on repairs, spares or transport before selling? Add it on the item's edit screen — it is counted in the price.

1. Open **Items** and click the item.
2. Type the extra cost in **Total expenses**.
3. Save. The **Selling price** box then shows a *suggested price*: purchase price + expenses + your profit. Adjust it up or down if you like — the suggested one is only a helper, the number you save is the one used.

On the same screen you can also fix brand, model, serial, or change the **status**:

| Status | Meaning |
|---|---|
| **In-Stock** | Sitting in storage, not yet prepared for sale |
| **Servicing** | Being cleaned, repaired or tested |
| **Ready** | Ready to sell — it will now appear on the Sales page |
| **Sold** | Done — filled automatically when you make a sale. Don't set by hand. |

## 3. How do I add photos of an item?

Also on the item's edit screen:

1. Click **Choose files / Choose images** in the Photos area. You can pick several photos at once (phone photos work fine).
2. Save the form — the photos upload with it.
3. Changed your mind about one? Press its delete button next to that photo.

Photos stay in the order you add them: 1, 2, 3… Continuous photos make a complete story for the listing, without any repeat angles.

## 4. How do I sell something?

1. Before selling: on the item's edit screen set its status to **Ready**. Only **Ready** and **In-Stock** items appear on the Sales page.
2. Open **Sales**.
3. Type or pick the **customer**. A brand-new name is remembered automatically for next time.
4. Tick every item in today's bill. Each tick shows its selling price, and the total builds as you go.
5. In **Paid**, type the money received *today*. If the customer gives a part-payment, type only that part. The rest shows up in the Ledger as pending.
6. Save. The items turn to **Sold** automatically, on their own, and you are taken to the Dashboard.

## 5. A customer paid later — I got some money. Where do I record it?

1. Open **Ledger**. You see every sale that still has a balance, with the amount pending.
2. In that row, fill **Amount received** and a short **Note** about how it came — e.g. *GPay*, *Cash*, *Cheque 2041*.
3. Save. The pending amount drops. This payment is kept permanently in that sale's payment book, together with the date and your note. You never have to remember it.

> 💡 Making several small payments? Add them one by one. Each one keeps its own entry, so the full history stays true.

## 6. What about the tools and equipment I keep?

Open **Assets** and add a row: name (e.g. *Oscilloscope*), what it cost, and when you bought it. These never go into Sales — they are things you keep. Their total shows up in your Dashboard worth.

## 7. What do the Dashboard numbers mean?

| Number | Honest meaning |
|---|---|
| **Cash received** | All money that has actually come in, ever. Real money, no assumptions. |
| **Receivables** | Total that customers still owe you (bills made minus payments received). |
| **Stock value (cost / market)** | What you paid for the unsold items — and what you expect to sell them for. |
| **Asset value** | Total of everything on the Assets page. |
| **Min worth** | A cautious guess: stock at cost, cash received, ignoring tools. The "it can't get worse than this" number. |
| **Max worth** | An optimistic guess: every item sells at its listed price, tools count, and pending money arrives. The "if all goes well" number. |

**Real life lives between Min worth and Max worth.** Watch Min worth when you worry, and let Max worth show what you're working for.

---

## Good to know

- **No delete buttons by design.** Records are instead corrected on the edit screens, so nothing is lost by accident — fixing a number works almost always. Photos are one exception, with their own delete buttons.
- **Sold items lock themselves.** When a sale is made, the items turn Sold and stay in that sale. The Sales page only offers what is not sold.
- **Saved means saved.** When a page refreshes after save (it flashes and returns to the list), your entry is in. To double-check, look at the list again.
- **Money numbers** are in ₹ and can carry paise (e.g. 19999.50).

## One-minute recap

📦 New lot arrives → create a **Batch**, add items.
🔧 Repairs / extra costs → open the item, add to **expenses**.
✅ Item ready to go → set status **Ready**.
💰 Customer buys → **Sales**, tick items, type today's payment.
🧾 Payment comes later → **Ledger**, add payment + note.
🏠 Every morning → the **Dashboard** tells you where you stand.
