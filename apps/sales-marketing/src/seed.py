from sm_database import init_db, get_connection
import datetime

def seed():
    init_db()
    conn = get_connection()
    c = conn.cursor()

    # 1. Seed Personas
    personas = [
        ("home_automation_specialist", "Home Automation Specialist", 
         "100% local-first, zero-cloud smart home automation retrofitted into Indian modular switchboards.", 
         "Medium (20-45 Days)", "Turnkey project fees + hardware margin",
         "Product architecture complete; missing physical 1x1 ft demo board for local interior designer visits and in-person closes.",
         "Mr. Stephan - Hall (4+1) + Bathroom reed switch automation", 10000),
        
        ("computer_service_technician", "Computer Service Technician",
         "Board-level diagnostics, schematic tracing, and in-browser boardview companion tools.",
         "Immediate upon repair (1-3 Days)", "Diagnostic fees & component-level repair billing (Free public tools)",
         "Completed zero-cost utility companion for ecomsense.in; needs traffic transition from schematics to paid offerings.",
         "Ideapad 5 15ITL05 Hinge & Antenna Repair + Local shop outreach", 5000),
          
        ("domain_reseller_hosting", "Domain Reseller & Hosting Service Provider",
         "Low-latency Mumbai VPS hosting and domain infrastructure with instant UPI billing.",
         "Fast & Recurring", "Monthly recurring UPI subscriptions",
         "Infrastructure live; needs targeted outreach and forum links in retail trading communities for VPS conversions.",
         "Indian retail algo traders in trading communities", 10000),
          
        ("used_computer_salesman", "Used Computer Salesman",
         "Procure, test, refurbish, and sell commercial business-grade laptops.",
         "Immediate upon stock (3-7 Days)", "Direct margin on refurbished hardware sales",
         "0 laptop inventory on hand; sourcing physical business-series inventory when capital is available.",
         "0 inventory on hand - waiting on procurement capital", 6000),

        ("ui_ux_tester", "UI/UX & Web Application Tester",
         "Automated black-box testing, user journeys, browser automation.",
         "Retainer Based", "Monthly agency testing retainer",
         "Client (rachis.co.in) agreed to ₹30,000/month testing retainer; start date delayed indefinitely by client.",
         "rachis.co.in contract agreed; pending client start date", 30000),

        ("business_automation_expert", "Business Automation Expert",
         "Commercial campaign state machine, 24/7 telemetry APIs, and pipeline automation.",
         "Operational Backbone", "Commercial sprint & telemetry automation",
         "Enforcing daily human outbound execution without relapsing into unmonetized code refactors or premature rewrites.",
         "sales-marketing campaign sprint + fastapi-apps telemetry", 40000),

        ("swing_trader", "Swing Trader",
         "Passive swing trading system based on FTI teachings (Fibonacci accumulation, no stop loss).",
         "Market Driven", "Capital gains from Fibonacci swing accumulation",
         "Capital availability for Fibonacci accumulation; passive system, must step aside completely when cash is constrained.",
         "fti-holdings - passive capital preservation", 3000),

        ("youtuber_content_creator", "YouTuber / Content Creator",
         "Automated high-frequency technical and educational video content creation.",
         "Medium to Long", "Top-of-funnel tech authority & lead generation",
         "Audience building required (60-120 days lead time); unmonetized top-of-funnel reach until consistent viewership is reached.",
         "make-videos & open-converter automation daemon", 0)
    ]
    for p in personas:
        c.execute("""
        INSERT OR REPLACE INTO personas (slug, title, what_you_do, speed_to_cash, revenue_model, bottleneck, active_lead_summary, value)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, p)

    # 2. Seed Campaigns (Active drives & AI proposals)
    campaigns = [
        ("b2b_repair_outreach", "Local B2B Board Diagnostics Outreach", "2026-11-10", "2026-11-20", 5000, "active",
         "ecomsense.in", "schematics", "computer_service_technician", "Visit local repair shops to offer ₹500 motherboard triage"),
        ("stephan_switchboard_retrofit", "Mr. Stephan Apartment Retrofit", "2026-11-05", "2026-11-25", 10000, "active",
         "ApartmentThread", None, "home_automation_specialist", "Lock 50% advance for hall/bathroom modular switchboard installation"),
        ("mumbai_vps_algo_traders", "Retail Algo Trader Mumbai VPS Launch", "2026-11-15", "2026-12-15", 10000, "proposed",
         "ecomsense.in", "vps", "domain_reseller_hosting", "Broadcast low-latency VPS offer on Indian retail algo trading communities"),
        ("rachis_qa_retainer", "Rachis Agency Testing Retainer Activation", "2026-11-15", "2026-12-15", 30000, "proposed",
         "gate-nine", None, "ui_ux_tester", "Deliver 2 sample black-box verification test runs to unlock monthly agency retainer"),
        ("apartment_meta_ads", "Facebook Lead Ads for Apartment Retrofit (3 Months)", "2026-11-20", "2027-02-20", 90000, "proposed",
         "ApartmentThread", None, "home_automation_specialist", "Meta ads targeting apartment renovators within 10km for switchboard retrofits")
    ]
    for c_item in campaigns:
        c.execute("""
        INSERT OR REPLACE INTO campaigns (slug, name, start_date, end_date, target_revenue, status, repo, module, persona_slug, rationale)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, c_item)

    # 3. Seed Persona Repo Actions & Objectives
    persona_actions = [
        ("used_computer_salesman", "test-suite", "Boot USB Alpine environment and execute automated hardware diagnostics suite on laptops before purchase", "Verify battery wear, RAM health, and NVMe lifespan to eliminate bad stock procurement"),
        ("used_computer_salesman", "ecomsense.in", "Create and manage forward tech auctions with base pricing and expiry dates on auctions module", "Liquidate tested hardware directly to lab tinkerers and buyers at clearance margin"),
        ("computer_service_technician", "PCBView", "Serve client-side zero-cost WebAssembly boardview viewer for .brd and .asc motherboard files", "Provide instant browser-based boardview tracing without native software installation"),
        ("computer_service_technician", "ecomsense.in", "Index, host, and serve motherboard schematics and chip-level repair manuals on schematics module", "Attract chip-level laptop and mobile technicians as a high-authority free community magnet"),
        ("home_automation_specialist", "ApartmentThread", "Flash and provision 100% local-first firmware into Indian modular wall switchboards", "Secure advance payments and hardware margin on smart switchboard installations"),
        ("home_automation_specialist", "ecomsense.in", "Deploy interactive residential wiring pattern quotation wizard on home_automation_wizard module", "Generate qualified inbound project inquiries and upfront installation advances from renovating homeowners"),
        ("domain_reseller_hosting", "ecomsense.in", "Deploy and manage Mumbai low-latency VPS instances with instant automated UPI billing", "Deliver low-latency VPS hosting with recurring UPI subscriptions for retail algo traders"),
        ("domain_reseller_hosting", "siliconhouse", "Configure and maintain client DNS records, reseller hosting tiers, and domain registration endpoints", "Provide white-labeled domain hosting and automated renewals for businesses and agencies"),
        ("ui_ux_tester", "gate-nine", "Execute human-supervised automated black-box test runs and edge-case verification on client web applications", "Deliver quality audits to unlock and maintain recurring testing retainer with rachis.co.in"),
        ("ui_ux_tester", "browser-agent", "Run local headless browser scripts across recurring web workflows and client user journeys", "Automate repetitive testing runs and capture visual regression artifacts before client releases"),
        ("business_automation_expert", "fastapi-apps", "Operate 24/7 background telemetry service on port 11173 for cash collected, receivables, and budgeting", "Expose real-time financial ground truth to agents and the dashboard without human reporting overhead"),
        ("business_automation_expert", "sales-marketing", "Evaluate active campaign state machine and assign chronological real-world field tasks to the human", "Enforce commercial execution and debt collection pace toward monthly cash goal"),
        ("swing_trader", "fti-holdings", "Execute multi-day Fibonacci accumulation swing setups under FTI price-action rules", "Generate passive capital returns from Fibonacci swing accumulation under FTI price-action rules"),
        ("youtuber_content_creator", "make-videos", "Execute automated video generation compositions and render pipeline inside Docker", "Produce automated technical explainers and software walkthroughs at scale without studio overhead"),
        ("youtuber_content_creator", "open-converter", "Run local offline faster-whisper transcription daemon across raw video and audio watch folders", "Generate time-synced subtitle transcripts for automated video editing and documentation generation")
    ]
    for pa in persona_actions:
        c.execute("""
        INSERT OR REPLACE INTO persona_repo_actions (persona_slug, repo, action, objective)
        VALUES (?, ?, ?, ?)
        """, pa)

    conn.commit()
    conn.close()
    print("Database initialized and seeded successfully.")

if __name__ == "__main__":
    seed()
