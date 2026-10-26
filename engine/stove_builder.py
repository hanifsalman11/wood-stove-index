import os
import json
import re
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone

# ==========================================
# ENVIRONMENT CONFIGURATION
# ==========================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
SITE_BASE_URL = os.environ.get("SITE_BASE_URL", "https://hanifsalman11.github.io/wood-stove-index").rstrip("/")
INDEXNOW_KEY = os.environ.get("INDEXNOW_KEY", "f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9").strip()
CUSTOM_STOVE = os.environ.get("CUSTOM_STOVE", "").strip()
PAGES_PER_RUN = int(os.environ.get("PAGES_PER_RUN", "3"))

DOCS_DIR = "docs"
DATA_DIR = "data"
PUBLISHED_FILE = os.path.join(DATA_DIR, "published_stoves.json")
MONETIZATION_FILE = os.path.join(DATA_DIR, "monetization.json")

# Format: (Stove Model / Scenario Name, Peak BTU, Max Sq Ft, Flue Collar Inches, Stove Fuel Type, Efficiency Pct)
SEED_STOVES = [
    ("Drolet Escape 1800 EPA Wood Stove", 75000, 2100, 6, "Cord Wood", 78),
    ("Drolet HT-3000 Extra-Large EPA Wood Stove", 110000, 2700, 6, "Cord Wood", 78),
    ("Drolet Spark II Compact Cabin Wood Stove", 55000, 1200, 6, "Cord Wood", 76),
    ("Drolet Deco Nano & Deco II Modern Wood Stove", 65000, 1800, 6, "Cord Wood", 77),
    ("ComfortBilt HP22 Automatic Pellet Stove", 50000, 2800, 3, "Hardwood Pellets", 86),
    ("ComfortBilt HP50S 47,000 BTU Pellet Stove", 47000, 2200, 3, "Hardwood Pellets", 84),
    ("ComfortBilt HP61 Large Hopper Pellet Stove", 54000, 3000, 3, "Hardwood Pellets", 85),
    ("US Stove Forester 5824 / VG5790 Pellet Stove", 48000, 2200, 3, "Hardwood Pellets", 81),
    ("US Stove Magnolia 2015 EPA Pedestal Wood Stove", 68000, 1800, 6, "Cord Wood", 75),
    ("Ashley Hearth AW2520E-P 2,500 Sq Ft Wood Stove", 88000, 2500, 6, "Cord Wood", 76),
    ("Ashley Hearth AP5660L 2,200 Sq Ft Pellet Stove", 48000, 2200, 3, "Hardwood Pellets", 80),
    ("Pleasant Hearth 2,200 Sq Ft Large EPA Wood Stove", 75000, 2200, 6, "Cord Wood", 81),
    ("Pleasant Hearth 1,800 Sq Ft Medium EPA Wood Stove", 65000, 1800, 6, "Cord Wood", 78),
    ("Castle Serenity 12327 PelPro Pellet Stove", 40000, 1500, 3, "Hardwood Pellets", 83),
    ("PelPro PP130 130-Lb Hopper 2,500 Sq Ft Pellet Stove", 50000, 2500, 3, "Hardwood Pellets", 87),
    ("PelPro PP60-B 1,500 Sq Ft Compact Pellet Stove", 35000, 1500, 3, "Hardwood Pellets", 85),
    ("Century Heating FW3500 Extra-Large Wood Stove", 90000, 2500, 6, "Cord Wood", 77),
    ("Century Heating FW2800 Medium EPA Wood Stove", 65000, 1800, 6, "Cord Wood", 76),
    ("Englander 30-NC / 32-NC 2,200 Sq Ft Wood Stove", 75000, 2200, 6, "Cord Wood", 77),
    ("Vogelzang DefenderTR001 EPA Wood Burning Stove", 62000, 1500, 6, "Cord Wood", 75),
    ("Blaze King King 40 & Princess Catalytic Wood Stove", 85000, 2600, 8, "Cord Wood", 82),
    ("Jotul F 500 V3 Oslo Cast Iron Catalytic Wood Stove", 70000, 2000, 6, "Cord Wood", 78),
    ("HearthStone Heritage Soapstone Hybrid Wood Stove", 65000, 2000, 6, "Cord Wood", 79),
    ("1,500 Sq Ft Cabin & Home Wood Stove Sizing", 60000, 1500, 6, "Cord Wood", 78),
    ("2,000 Sq Ft Family Home Wood Stove & Chimney Sizing", 75000, 2000, 6, "Cord Wood", 78),
    ("2,500 Sq Ft Cold-Climate Home Wood Stove Sizing", 95000, 2500, 6, "Cord Wood", 79),
    ("1,000 Sq Ft A-Frame Off-Grid Cabin Wood Stove", 45000, 1000, 6, "Cord Wood", 76),
    ("6-Inch Class-A Double-Wall Chimney 3-2-10 Rule Setup", 75000, 2000, 6, "Cord Wood", 78),
    ("Drolet Escape 1800-I Fireplace Wood Insert", 75000, 2100, 6, "Cord Wood", 77),
    ("DuraVent DuraTech 6-Inch Class-A Through-Roof Kit", 75000, 2000, 6, "Cord Wood", 78)
]


def load_json(filepath, default):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARN] Could not parse {filepath}: {e}")
    return default


def save_json(filepath, data):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    return re.sub(r"[\s-]+", "-", text).strip("-")


def safe_float(val, default=75000.0):
    try:
        cleaned = re.sub(r"[^0-9.]", "", str(val))
        return float(cleaned) if cleaned else float(default)
    except Exception:
        return float(default)


def build_amazon_url(search_keywords, mon_cfg):
    domain = mon_cfg.get("marketplace_domain", "www.amazon.com")
    tag = mon_cfg.get("amazon_associate_tag", "YOUR_AMAZON_TAG-20")
    encoded_q = urllib.parse.quote_plus(search_keywords)
    return f"https://{domain}/s?k={encoded_q}&tag={tag}"


def discover_google_stove_queries():
    discovered = []
    seeds = [
        "what size wood stove for ",
        "drolet wood stove ",
        "comfortbilt pellet stove ",
        "chimney pipe height calculator for "
    ]
    for seed in seeds:
        try:
            url = f"http://suggestqueries.google.com/complete/search?client=firefox&hl=en&gl=us&q={urllib.parse.quote(seed)}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for suggestion in data[1]:
                    cleaned = suggestion.lower()
                    for pref in seeds:
                        if "what size" in pref or "calculator" in pref:
                            cleaned = cleaned.replace(pref, "")
                    cleaned = re.sub(
                        r"\b(calculator|size|sizing|btu|manual|review|reddit|for)\b",
                        "",
                        cleaned
                    ).strip()
                    if 5 <= len(cleaned) <= 42:
                        is_pellet = "pellet" in cleaned or "comfortbilt" in cleaned or "pelpro" in cleaned
                        if is_pellet:
                            discovered.append((cleaned.title(), 50000, 2200, 3, "Hardwood Pellets", 85))
                        else:
                            discovered.append((cleaned.title(), 75000, 2000, 6, "Cord Wood", 78))
        except Exception as e:
            print(f"[WARN] Google Suggest notice: {e}")
    return discovered


def build_deterministic_stove_data(stove_tuple):
    """Mesin Fisika Termal BTU, Aturan Cerobong NFPA 211 (3-2-10) & Konsumsi Kayu/Pelet (100% bebas gagal)."""
    model_name, peak_btu, max_sqft, flue_in, fuel_type, eff_pct = stove_tuple

    is_pellet = flue_in <= 4 or "Pellet" in fuel_type
    # NFPA 211 3-2-10 Rule pada kemiringan atap 6/12 (0.50 pitch):
    # Tinggi di atas tembusan atap = max(3.0 ft, (10 ft horizontal * 6/12) + 2 ft) = 7.0 ft di atas atap
    roof_clearance_6_12_ft = 7.0
    min_total_stack_ft = 15.0

    # Estimasi pemakaian bahan bakar musim dingin (150 hari pemanasan aktif):
    # 1 Cord Seasoned Oak/Maple = ~24,000,000 BTU | 1 Ton Hardwood Pellets (50x 40lb bags) = ~16,500,000 BTU
    seasonal_btu_needed = max_sqft * 35.0 * 12.0 * 150.0 * 0.45
    if is_pellet:
        pellets_tons = round(seasonal_btu_needed / (16500000.0 * (eff_pct / 100.0)), 1)
        fuel_summary = f"{pellets_tons} Tons ({int(round(pellets_tons * 50))} × 40-lb bags) of Premium Hardwood Pellets"
        pipe_title = f"{flue_in}-Inch Type-L Stainless Steel Pellet Vent Pipe & Wall Thimble Kit"
        pipe_query = f"{flue_in} Inch Pellet Stove Vent Pipe Kit DuraVent Selkirk"
        pipe_price = "$189 - $429"
    else:
        wood_cords = round(seasonal_btu_needed / (24000000.0 * (eff_pct / 100.0)), 1)
        fuel_summary = f"{wood_cords} Full Cords of Seasoned Hardwood (<20% Moisture Content)"
        pipe_title = f"{flue_in}-Inch Class-A Double/Triple-Wall Insulated Stainless Chimney Pipe & Roof Kit"
        pipe_query = f"{flue_in} Inch Class A Insulated Stainless Steel Chimney Pipe Kit DuraVent"
        pipe_price = "$389 - $999"

    return {
        "stove_name": model_name,
        "fuel_type": fuel_type,
        "seo_title": f"{model_name} BTU Sizing, Chimney 3-2-10 Rule & Fuel Calculator (2026)",
        "meta_description": f"Calculate exact heating coverage ({max_sqft:,} sq ft / {peak_btu:,} BTU), NFPA 211 3-2-10 chimney height ({roof_clearance_6_12_ft}' above 6/12 roof), and winter fuel usage ({fuel_summary}) for {model_name}.",
        "specs": {
            "peak_btu": peak_btu,
            "max_coverage_sqft": max_sqft,
            "flue_collar_inches": flue_in,
            "fuel_type": fuel_type,
            "efficiency_pct": eff_pct,
            "min_stack_height_ft": min_total_stack_ft,
            "roof_6_12_clearance_ft": roof_clearance_6_12_ft,
            "seasonal_fuel_estimate": fuel_summary
        },
        "nfpa_verdict": f"Rated at {peak_btu:,} BTU/hr ({eff_pct}% EPA thermal efficiency) for spaces up to {max_sqft:,} sq. ft., the {model_name} vents through a {flue_in}-inch flue collar and consumes approximately {fuel_summary} per winter. Under NFPA 211 (3-2-10 Chimney Rule), a vertical chimney penetrating a standard 6/12 pitch roof must extend at least {roof_clearance_6_12_ft} feet above the roof penetration (2 feet higher than any roof ridge within 10 feet horizontally) with a minimum 15-foot total vertical draft column.",
        "hardware_bundle": [
            {
                "badge": f"{peak_btu // 1000}K BTU Heating Unit",
                "title": f"{model_name} ({max_sqft:,} Sq Ft EPA High-Efficiency Heater)",
                "price_range": "$799 - $2,499",
                "amazon_query": f"{model_name} Stove",
                "stove_note": f"Delivers {peak_btu:,} BTU/hr at {eff_pct}% efficiency with air-wash ceramic glass and variable-speed blower."
            },
            {
                "badge": f"{flue_in}\" Chimney & Vent Kit",
                "title": pipe_title,
                "price_range": pipe_price,
                "amazon_query": pipe_query,
                "stove_note": "UL-103HT / UL-641 rated high-temperature stainless steel maintains flue draft and zero-clearance roof safety."
            },
            {
                "badge": "UL-1618 Hearth & Flue",
                "title": "UL-1618 Type-2 Ember & Thermal Hearth Pad + Magnetic Flue Creosote Thermometer",
                "price_range": "$129 - $349",
                "amazon_query": "Wood Stove Hearth Pad Floor Protection Plate Magnetic Flue Thermometer",
                "stove_note": "Protects combustible flooring from radiant heat and monitors optimal 300°F–500°F anti-creosote flue zone."
            },
            {
                "badge": "Ash Vac, Moisture & Fan",
                "title": "Metal HEPA Warm-Ash Vacuum + Digital Firewood Moisture Meter & Heat-Powered Stove Fan",
                "price_range": "$69 - $159",
                "amazon_query": "Metal Pellet Wood Stove Ash Vacuum Firewood Moisture Meter Stove Fan",
                "stove_note": "Verifies firewood is below 20% moisture before burning and circulates warm air without grid electricity."
            }
        ],
        "nfpa_checklist": [
            "Enforce the NFPA 211 3-2-10 Chimney Rule: the top of your Class-A chimney cap must be at least 3 feet above the roof penetration AND 2 feet higher than any roof surface or ridge within a 10-foot horizontal radius.",
            "Never use single-wall black stove pipe to pass through a ceiling, attic, or exterior wall! Single-wall or double-wall black connector pipe is strictly for inside the room up to the ceiling support box, where it MUST transition to Class-A Insulated Chimney Pipe.",
            "Add a roof Guy-Wire Roof Brace Support Kit whenever your Class-A stainless chimney pipe extends 5 feet or more above the roofline to prevent winter wind & snow-slide shear.",
            "Burn only seasoned hardwood split and dried to 15%–20% internal moisture content (verified on a freshly split face with a pin moisture meter) to prevent flammable Stage-3 glazed creosote buildup."
        ],
        "faqs": [
            {
                "q": f"How many square feet can the {model_name} heat in winter?",
                "a": f"With {peak_btu:,} BTU/hr peak output and {eff_pct}% efficiency, it heats up to {max_sqft:,} sq. ft. in mild/moderate climate zones, or around {int(round(max_sqft * 0.72)):,} sq. ft. in severe northern sub-zero zones (requiring 40–45 BTU per sq. ft.)."
            },
            {
                "q": f"How high above the roof does the chimney pipe need to be for the {model_name}?",
                "a": f"Per NFPA 211 (3-2-10 Rule), multiply 10 feet by your roof pitch and add 2 feet. On a 6/12 pitch roof ((10 × 0.5) + 2), the pipe must extend {roof_clearance_6_12_ft} feet above the penetration point, with a minimum 15-foot total vertical stack from stove flue collar to rain cap."
            },
            {
                "q": f"How much wood or pellets will the {model_name} use per winter?",
                "a": f"Heating {max_sqft:,} sq. ft. through a 150-day winter consumes approximately {fuel_summary}, saving $1,200 to $2,400 per season compared to propane, heating oil, or baseboard electric heat."
            }
        ]
    }


def generate_stove_data(stove_tuple):
    if not GEMINI_API_KEY:
        return build_deterministic_stove_data(stove_tuple)

    model_name, peak_btu, max_sqft, flue_in, fuel_type, eff_pct = stove_tuple
    det_fallback = build_deterministic_stove_data(stove_tuple)
    fuel_est = det_fallback["specs"]["seasonal_fuel_estimate"]

    prompt = f"""
You are a CSIA Certified Chimney Sweep & NFI (National Fireplace Institute) Master Hearth Engineer. Create an accurate 2026 BTU room sizing, NFPA 211 (3-2-10 Rule) chimney pipe height, and winter fuel consumption guide for: "{model_name}".
Baseline specs: Peak Output={peak_btu} BTU/hr, Max Area={max_sqft} sq ft, Flue Collar={flue_in} Inch, Fuel={fuel_type}, Efficiency={eff_pct}%, Seasonal Fuel={fuel_est}.
Return ONLY a valid JSON object matching this exact schema:
{{
  "stove_name": "{model_name}",
  "fuel_type": "{fuel_type}",
  "seo_title": "{model_name} BTU Sizing, Chimney 3-2-10 Rule & Fuel Calculator (2026)",
  "meta_description": "Calculate exact heating BTU coverage, NFPA 211 3-2-10 chimney pipe height, and winter fuel cords/pellets for {model_name}.",
  "specs": {{
    "peak_btu": {peak_btu},
    "max_coverage_sqft": {max_sqft},
    "flue_collar_inches": {flue_in},
    "fuel_type": "{fuel_type}",
    "efficiency_pct": {eff_pct},
    "min_stack_height_ft": 15.0,
    "roof_6_12_clearance_ft": 7.0,
    "seasonal_fuel_estimate": "{fuel_est}"
  }},
  "nfpa_verdict": "3-sentence technical summary stating BTU output, square footage by climate zone, NFPA 211 3-2-10 chimney height requirement, and winter fuel consumption.",
  "hardware_bundle": [
    {{
      "badge": "EPA Heating Stove",
      "title": "{model_name}",
      "price_range": "$799 - $2,499",
      "amazon_query": "{model_name} Stove",
      "stove_note": "1-sentence BTU and thermal efficiency note"
    }},
    {{
      "badge": "{flue_in}\" Chimney & Vent Kit",
      "title": "{flue_in}-Inch Class-A Stainless Insulated Chimney / Pellet Vent Kit",
      "price_range": "$249 - $999",
      "amazon_query": "{flue_in} Inch Class A Stainless Chimney Pipe Kit DuraVent",
      "stove_note": "1-sentence UL-103HT draft and clearance note"
    }},
    {{
      "badge": "Hearth Pad & Thermometer",
      "title": "UL-1618 Thermal Hearth Pad + Magnetic Flue Creosote Thermometer",
      "price_range": "$129 - $349",
      "amazon_query": "Wood Stove Hearth Pad Magnetic Flue Thermometer",
      "stove_note": "1-sentence floor protection and creosote temp note"
    }},
    {{
      "badge": "Ash Vac & Moisture Meter",
      "title": "Metal HEPA Ash Vacuum + Digital Firewood Moisture Meter & Heat-Powered Fan",
      "price_range": "$69 - $159",
      "amazon_query": "Wood Pellet Stove Ash Vacuum Firewood Moisture Meter Fan",
      "stove_note": "1-sentence <20% wood moisture and heat circulation note"
    }}
  ],
  "nfpa_checklist": [
    "Step 1 regarding NFPA 211 3-2-10 roof clearance rule",
    "Step 2 regarding Class-A insulated pipe transition at ceiling support box",
    "Step 3 regarding roof brace kit required at 5+ feet above roofline",
    "Step 4 regarding <20% firewood moisture content and 15-ft minimum stack draft"
  ],
  "faqs": [
    {{"q": "How many square feet can the {model_name} heat?", "a": "Exact sq ft in mild vs cold northern climates."}},
    {{"q": "How high does the chimney pipe need to be for the {model_name}?", "a": "Exact NFPA 211 3-2-10 calculation and 15-ft minimum vertical draft stack."}},
    {{"q": "How many cords of wood or bags of pellets does the {model_name} burn per winter?", "a": "Exact cords or pellet tons/bags and dollar savings."}}
  ]
}}
"""

    for model_id in ["gemini-2.5-flash", "gemini-2.0-flash"]:
        try:
            endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={GEMINI_API_KEY}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.2,
                    "responseMimeType": "application/json"
                }
            }
            req = urllib.request.Request(
                endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=35) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                raw_text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
                raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
                raw_text = re.sub(r"\s*```$", "", raw_text)
                parsed = json.loads(raw_text)
                if "specs" in parsed and "hardware_bundle" in parsed:
                    return parsed
        except Exception as e:
            print(f"[WARN] Gemini ({model_id}) notice for '{model_name}': {e}")

    return det_fallback


def build_stove_html_page(data, slug, mon_cfg):
    stove_name = data.get("stove_name", "EPA Wood & Pellet Stove")
    sp = data.get("specs", {})
    peak_btu = int(safe_float(sp.get("peak_btu", 75000), 75000))
    max_sqft = int(safe_float(sp.get("max_coverage_sqft", 2000), 2000))
    flue_in = int(safe_float(sp.get("flue_collar_inches", 6), 6))
    fuel_type = sp.get("fuel_type", "Cord Wood")
    eff_pct = int(safe_float(sp.get("efficiency_pct", 78), 78))

    header_cta = mon_cfg.get("header_cta", {})
    header_cta_url = build_amazon_url(header_cta.get("search_query", "EPA+Wood+Stove+Pellet+Stove+Chimney+Kit"), mon_cfg)

    schema_graph = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "SoftwareApplication",
                "name": f"{stove_name} BTU, Chimney 3-2-10 & Fuel Calculator",
                "applicationCategory": "UtilitiesApplication",
                "operatingSystem": "Web Browser",
                "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}
            },
            {
                "@type": "FAQPage",
                "mainEntity": [
                    {
                        "@type": "Question",
                        "name": f.get("q", ""),
                        "acceptedAnswer": {"@type": "Answer", "text": f.get("a", "")}
                    } for f in data.get("faqs", [])
                ]
            }
        ]
    }

    bundle_html = ""
    for item in data.get("hardware_bundle", []):
        amz_url = build_amazon_url(item.get("amazon_query", item.get("title", "EPA Wood Stove")), mon_cfg)
        bundle_html += f"""
        <div class="bg-stone-900 border border-stone-800 rounded-xl p-5 flex flex-col justify-between hover:border-orange-500/60 transition">
          <div>
            <div class="flex items-center justify-between gap-2 mb-2">
              <span class="text-xs font-bold uppercase tracking-wider bg-orange-500/10 text-orange-400 border border-orange-500/20 px-2.5 py-0.5 rounded">{item.get('badge', 'Hearth Gear')}</span>
              <span class="text-sm font-bold text-emerald-400">{item.get('price_range', '$129+')}</span>
            </div>
            <h3 class="text-base font-bold text-white mt-2">{item.get('title', '')}</h3>
            <p class="text-xs text-stone-400 mt-2 leading-relaxed">🔥 {item.get('stove_note', '')}</p>
          </div>
          <a href="{amz_url}" target="_blank" rel="nofollow sponsored" class="mt-5 block text-center bg-orange-500 hover:bg-orange-400 text-stone-950 font-extrabold py-2.5 px-4 rounded-lg text-sm transition shadow-lg">
            Check Price on Amazon →
          </a>
        </div>"""

    # Build Roof Pitch vs NFPA 211 (3-2-10 Rule) Chimney Height Matrix Table
    pitch_tiers = [
        ("Flat / 2/12 Pitch Roof", "3.7 Feet Above Roof", "No Roof Brace Needed", "Min 15 ft Total Stack"),
        ("4/12 Pitch Roof", "5.3 Feet Above Roof", "1x Roof Guy-Bracket Kit", "Min 15 ft Total Stack"),
        ("6/12 Standard Pitch", "7.0 Feet Above Roof", "1x Roof Guy-Bracket Kit", "Min 15–16 ft Stack"),
        ("8/12 Steep Pitch Roof", "8.7 Feet Above Roof", "1x Roof Guy-Bracket Kit", "Min 16–18 ft Stack"),
        ("10/12 – 12/12 A-Frame", "10.3 – 12.0 Ft (or Penetrate Near Ridge)", "2x Extended Roof Braces", "Min 18+ ft Stack")
    ]
    matrix_rows_html = ""
    for p_lbl, h_lbl, br_lbl, st_lbl in pitch_tiers:
        matrix_rows_html += f"""
        <tr class="border-b border-stone-800 hover:bg-stone-800/40">
          <td class="py-3 px-4 font-bold text-white">{p_lbl}</td>
          <td class="py-3 px-4 font-bold text-orange-400">{h_lbl}</td>
          <td class="py-3 px-4 text-emerald-400 font-semibold">{br_lbl}</td>
          <td class="py-3 px-4 text-xs text-stone-300">{st_lbl}</td>
        </tr>"""

    checklist_html = ""
    for idx, step_text in enumerate(data.get("nfpa_checklist", []), start=1):
        checklist_html += f"""
        <label class="flex items-start gap-3.5 bg-stone-900 border border-stone-800 rounded-xl p-4 cursor-pointer hover:border-stone-700 transition">
          <input type="checkbox" class="mt-1 w-5 h-5 accent-orange-500 rounded cursor-pointer stove-check">
          <span class="text-sm text-stone-200 leading-relaxed"><strong>NFPA 211 Step {idx}:</strong> {step_text}</span>
        </label>"""

    faqs_html = "".join([
        f"<div class='bg-stone-900 border border-stone-800 rounded-xl p-5'><h3 class='font-bold text-white text-base mb-2'>{f.get('q', '')}</h3><p class='text-sm text-stone-300 leading-relaxed'>{f.get('a', '')}</p></div>"
        for f in data.get("faqs", [])
    ])

    canonical_url = f"{SITE_BASE_URL}/{slug}.html"
    amz_domain = mon_cfg.get("marketplace_domain", "www.amazon.com")
    amz_tag = mon_cfg.get("amazon_associate_tag", "YOUR_AMAZON_TAG-20")

    html = f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{data.get('seo_title', stove_name)}</title>
  <meta name="description" content="{data.get('meta_description', '')}">
  <link rel="canonical" href="{canonical_url}">
  <meta property="og:title" content="{data.get('seo_title', stove_name)}">
  <meta property="og:description" content="{data.get('meta_description', '')}">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{canonical_url}">
  <script src="https://cdn.tailwindcss.com"></script>
  <script type="application/ld+json">{json.dumps(schema_graph)}</script>
</head>
<body class="bg-stone-950 text-stone-100 antialiased min-h-screen flex flex-col">
  <header class="border-b border-stone-800 bg-stone-900/80 backdrop-blur sticky top-0 z-30">
    <div class="max-w-5xl mx-auto px-4 py-3.5 flex items-center justify-between">
      <a href="index.html" class="text-lg font-black tracking-tight text-white flex items-center gap-2">
        <span class="bg-orange-500 text-stone-950 px-2 py-0.5 rounded font-black">HEARTH</span>StoveIndex
      </a>
      <a href="{header_cta_url}" target="_blank" rel="nofollow sponsored" class="text-xs sm:text-sm bg-orange-500 hover:bg-orange-400 text-stone-950 font-extrabold px-3.5 py-2 rounded-lg transition">
        {header_cta.get('cta_text', 'Shop Stoves & Chimney Kits →')}
      </a>
    </div>
  </header>

  <main class="max-w-5xl mx-auto px-4 py-10 flex-1 w-full">
    <div class="mb-8">
      <div class="flex flex-wrap items-center gap-2.5 mb-3">
        <span class="text-xs font-extrabold uppercase tracking-widest bg-orange-500 text-stone-950 px-3 py-1 rounded-full">{peak_btu:,} BTU ({eff_pct}% Eff)</span>
        <span class="text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-3 py-1 rounded-full">Up to {max_sqft:,} Sq Ft</span>
        <span class="text-xs font-semibold bg-stone-800 text-stone-300 px-3 py-1 rounded-full">{flue_in}" Flue Collar | {fuel_type}</span>
      </div>
      <h1 class="text-3xl sm:text-4xl font-black text-white leading-tight">{data.get('seo_title', stove_name)}</h1>
      <div class="mt-4 bg-stone-900 border-l-4 border-orange-500 p-4 rounded-r-xl text-sm text-stone-200 leading-relaxed">
        <strong>NFI & NFPA 211 Engineering Verdict:</strong> {data.get('nfpa_verdict', '')}
      </div>
    </div>

    <!-- INTERACTIVE BTU LOAD, NFPA 211 (3-2-10) CHIMNEY HEIGHT & FUEL CALCULATOR -->
    <section class="bg-stone-900 border border-stone-800 rounded-2xl p-6 sm:p-8 mb-12 shadow-2xl">
      <h2 class="text-xl font-extrabold text-white mb-2">Interactive {stove_name} BTU, 3-2-10 Chimney & Fuel Calculator</h2>
      <p class="text-xs text-stone-400 mb-6">Adjust your home square footage, winter climate zone, roof pitch, and home elevation to compute required stove BTU, NFPA 211 exterior chimney height, and winter firewood/pellet consumption.</p>

      <div class="grid md:grid-cols-2 gap-8 items-center">
        <div class="space-y-5">
          <div>
            <div class="flex justify-between text-sm font-medium mb-1.5">
              <label for="sqftSlider" class="text-stone-300">Heated Home or Cabin Area (Sq Ft)</label>
              <span class="text-orange-400 font-bold"><span id="sqftVal">{max_sqft:,}</span> sq ft</span>
            </div>
            <input id="sqftSlider" type="range" min="500" max="3500" step="100" value="{max_sqft}" class="w-full accent-orange-500 cursor-pointer">
          </div>

          <div class="grid grid-cols-2 gap-3">
            <div>
              <label for="zoneSelect" class="block text-xs font-medium text-stone-400 mb-1">Winter Climate & Insulation</label>
              <select id="zoneSelect" class="w-full bg-stone-950 border border-stone-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-orange-500">
                <option value="25">Mild Winter / Well Insulated (25 BTU/ft²)</option>
                <option value="35" selected>Moderate / Average Home (35 BTU/ft²)</option>
                <option value="45">Frigid North / Log Cabin (45 BTU/ft²)</option>
              </select>
            </div>
            <div>
              <label for="pitchSelect" class="block text-xs font-medium text-stone-400 mb-1">Roof Pitch (NFPA 3-2-10 Rule)</label>
              <select id="pitchSelect" class="w-full bg-stone-950 border border-stone-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-orange-500">
                <option value="2">2/12 Low Slope Roof</option>
                <option value="4">4/12 Moderate Pitch</option>
                <option value="6" selected>6/12 Standard Pitch</option>
                <option value="8">8/12 Steep Pitch</option>
                <option value="10">10/12 A-Frame / Chalet</option>
              </select>
            </div>
          </div>

          <div>
            <div class="flex justify-between text-sm font-medium mb-1.5">
              <label for="altSlider" class="text-stone-300">Property Elevation Above Sea Level (Feet — +3% Draft/1,000 ft)</label>
              <span class="text-orange-400 font-bold"><span id="altVal">1,000</span> ft</span>
            </div>
            <input id="altSlider" type="range" min="0" max="8000" step="500" value="1000" class="w-full accent-orange-500 cursor-pointer">
          </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div class="bg-stone-950 border border-orange-500/30 rounded-xl p-4">
            <span class="text-xs uppercase text-orange-400 font-bold">Required Stove BTU</span>
            <div class="text-xl sm:text-2xl font-black text-white mt-1"><span id="btuOut">{peak_btu:,}</span> <span class="text-xs font-normal text-stone-400">BTU</span></div>
            <p id="fuelSeasonOut" class="text-xs text-orange-400 font-semibold mt-1">~3.2 Cords / 3.8 Tons Pellets</p>
          </div>

          <div class="bg-stone-950 border border-emerald-500/30 rounded-xl p-4">
            <span class="text-xs uppercase text-emerald-400 font-bold">3-2-10 Chimney Height</span>
            <div id="roofPipeOut" class="text-xl sm:text-2xl font-black text-emerald-400 mt-1">7.0 ft Above Roof</div>
            <p id="stackMinOut" class="text-xs text-stone-300 font-semibold mt-1">Min Total Stack: 15.5 ft</p>
          </div>
        </div>
      </div>

      <div class="mt-6 bg-orange-950/40 border border-orange-500/30 rounded-xl p-4 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div id="stoveAdviceBanner" class="text-sm text-orange-100 font-medium"></div>
        <a id="dynamicStoveBtn" href="{header_cta_url}" target="_blank" rel="nofollow sponsored" class="shrink-0 bg-orange-500 hover:bg-orange-400 text-stone-950 font-extrabold px-4 py-2.5 rounded-lg text-xs uppercase tracking-wider transition">
          Shop Matched Stove & Chimney Kit on Amazon →
        </a>
      </div>
    </section>

    <!-- 4-CARD HARDWARE BUNDLE -->
    <section class="mb-12">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-2xl font-extrabold text-white">Complete {stove_name} Chimney, Hearth Pad & Tool Bundle</h2>
        <span class="text-xs text-stone-400">EPA 2020 & UL-103HT / NFPA 211 Compliant</span>
      </div>
      <div class="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">{bundle_html}</div>
    </section>

    <!-- ROOF PITCH & CHIMNEY HEIGHT MATRIX TABLE -->
    <section class="mb-12">
      <h2 class="text-2xl font-extrabold text-white mb-4">NFPA 211 (3-2-10 Rule) Class-A Chimney Pipe Height by Roof Pitch</h2>
      <div class="overflow-x-auto bg-stone-900 border border-stone-800 rounded-xl">
        <table class="w-full text-left border-collapse text-sm">
          <thead>
            <tr class="border-b border-stone-800 bg-stone-950/60 text-stone-400 uppercase text-xs">
              <th class="py-3.5 px-4">Roof Pitch Slope</th>
              <th class="py-3.5 px-4 text-orange-400">Min Pipe Height Above Penetration</th>
              <th class="py-3.5 px-4 text-emerald-400">Roof Guy-Brace Requirement</th>
              <th class="py-3.5 px-4">Total Vertical Draft Stack</th>
            </tr>
          </thead>
          <tbody>{matrix_rows_html}</tbody>
        </table>
      </div>
    </section>

    <!-- NFPA 211 CHECKLIST -->
    <section class="mb-12">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-2xl font-extrabold text-white">CSIA & NFPA 211 Chimney Draft & Hearth Safety Checklist</h2>
        <span id="stoveBadge" class="text-xs font-bold bg-stone-800 text-orange-400 px-3 py-1 rounded-full">0 / 4 Completed</span>
      </div>
      <div class="space-y-3">{checklist_html}</div>
    </section>

    <!-- FAQ -->
    <section class="mb-12">
      <h2 class="text-2xl font-extrabold text-white mb-5">Frequently Asked Questions ({stove_name})</h2>
      <div class="space-y-4">{faqs_html}</div>
    </section>
  </main>

  <footer class="border-t border-stone-800 py-8 text-center text-xs text-stone-500 px-4">
    <p>© {datetime.now(timezone.utc).year} HearthStoveIndex. Independent Wood/Pellet Stove BTU & NFPA 211 Chimney Engineering Database. As an Amazon Associate, we earn from qualifying purchases.</p>
  </footer>

  <script>
    const flueDiaIn = {flue_in};
    const amzDomain = "{amz_domain}";
    const amzTag = "{amz_tag}";

    const sqftSlider = document.getElementById('sqftSlider');
    const zoneSelect = document.getElementById('zoneSelect');
    const pitchSelect = document.getElementById('pitchSelect');
    const altSlider = document.getElementById('altSlider');
    const sqftVal = document.getElementById('sqftVal');
    const altVal = document.getElementById('altVal');
    const btuOut = document.getElementById('btuOut');
    const fuelSeasonOut = document.getElementById('fuelSeasonOut');
    const roofPipeOut = document.getElementById('roofPipeOut');
    const stackMinOut = document.getElementById('stackMinOut');
    const stoveAdviceBanner = document.getElementById('stoveAdviceBanner');
    const dynamicStoveBtn = document.getElementById('dynamicStoveBtn');

    function recalculateStove() {{
      const sqft = parseInt(sqftSlider.value, 10);
      const btuPerSqft = parseInt(zoneSelect.value, 10);
      const pitchRise = parseInt(pitchSelect.value, 10);
      const elevFt = parseInt(altSlider.value, 10);

      sqftVal.textContent = sqft.toLocaleString();
      altVal.textContent = elevFt.toLocaleString();

      const reqBtu = Math.round((sqft * btuPerSqft) / 1000) * 1000;
      const roofPipeFt = Math.max(3.0, ((10.0 * (pitchRise / 12.0)) + 2.0));
      const minTotalStackFt = 15.0 * (1.0 + ((elevFt / 1000.0) * 0.03));

      const seasonBtu = reqBtu * 10.0 * 150.0 * 0.45;
      const cordsWood = (seasonBtu / (24000000.0 * 0.78)).toFixed(1);
      const tonsPellets = (seasonBtu / (16500000.0 * 0.85)).toFixed(1);

      btuOut.textContent = reqBtu.toLocaleString();
      fuelSeasonOut.textContent = `~${{cordsWood}} Cords Wood / ${{tonsPellets}} Tons Pellets`;
      roofPipeOut.textContent = `${{roofPipeFt.toFixed(1)}} ft Above Roof`;
      stackMinOut.textContent = `Min Total Stack: ${{minTotalStackFt.toFixed(1)}} ft`;

      const braceNote = roofPipeFt >= 5.0 ? " + Extended Roof Guy-Brace Kit" : "";
      stoveAdviceBanner.innerHTML = `🔥 <strong>NFPA 211 Spec:</strong> Heating ${{sqft.toLocaleString()}} sq ft requires a <strong>${{reqBtu.toLocaleString()}} BTU EPA Stove</strong> and <strong>${{roofPipeFt.toFixed(1)}} ft of ${{flueDiaIn}}" Class-A Chimney Pipe above your ${{pitchRise}}/12 roof${{braceNote}}</strong>.`;
      dynamicStoveBtn.href = `https://${{amzDomain}}/s?k=${{reqBtu}}+BTU+EPA+Wood+Pellet+Stove+${{flueDiaIn}}+Inch+Class+A+Chimney+Pipe+Kit&tag=${{amzTag}}`;
    }}

    sqftSlider.addEventListener('input', recalculateStove);
    zoneSelect.addEventListener('change', recalculateStove);
    pitchSelect.addEventListener('change', recalculateStove);
    altSlider.addEventListener('input', recalculateStove);
    recalculateStove();

    const checks = document.querySelectorAll('.stove-check');
    const badge = document.getElementById('stoveBadge');
    checks.forEach(ch => {{
      ch.addEventListener('change', () => {{
        const done = Array.from(checks).filter(c => c.checked).length;
        badge.textContent = `${{done}} / ${{checks.length}} Completed`;
      }});
    }});
  </script>
</body>
</html>"""

    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(os.path.join(DOCS_DIR, f"{slug}.html"), "w", encoding="utf-8") as f:
        f.write(html)


def rebuild_portal_sitemap_and_rss(published, mon_cfg):
    header_cta = mon_cfg.get("header_cta", {})
    header_cta_url = build_amazon_url(header_cta.get("search_query", "EPA+Wood+Stove+Pellet+Stove+Chimney+Kit"), mon_cfg)

    cards_html = ""
    for item in reversed(published):
        cards_html += f"""
        <a href="{item['slug']}.html" class="block bg-stone-900 border border-stone-800 hover:border-orange-500/60 rounded-xl p-5 transition group">
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs font-black uppercase bg-orange-500 text-stone-950 px-2.5 py-0.5 rounded">{item.get('peak_btu', 75000):,} BTU</span>
            <span class="text-xs text-stone-400">Up to {item.get('max_sqft', 2000):,} Sq Ft | {item.get('flue_in', 6)}" Flue</span>
          </div>
          <h2 class="text-base font-bold text-white group-hover:text-orange-400 transition">{item['stove_name']}</h2>
          <p class="text-xs text-stone-400 mt-2 line-clamp-2">{item['description']}</p>
          <span class="inline-block mt-4 text-xs font-extrabold text-orange-400">Calculate BTU, 3-2-10 Chimney & Fuel →</span>
        </a>"""

    index_html = f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>HearthStoveIndex — Wood & Pellet Stove BTU, Chimney 3-2-10 Rule & Fuel Calculator (2026)</title>
  <meta name="description" content="Calculate exact wood and pellet stove BTU heating capacity, NFPA 211 (3-2-10 rule) Class-A chimney pipe height, and winter firewood cords or pellet bags for Drolet, ComfortBilt, PelPro, Pleasant Hearth, and US Stove models.">
  <link rel="canonical" href="{SITE_BASE_URL}/">
  <link rel="alternate" type="application/rss+xml" title="HearthStoveIndex RSS Feed" href="{SITE_BASE_URL}/rss.xml">
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-stone-950 text-stone-100 min-h-screen flex flex-col">
  <header class="border-b border-stone-800 bg-stone-900/80 sticky top-0 z-30 backdrop-blur">
    <div class="max-w-5xl mx-auto px-4 py-3.5 flex items-center justify-between">
      <div class="text-lg font-black text-white flex items-center gap-2">
        <span class="bg-orange-500 text-stone-950 px-2 py-0.5 rounded font-black">HEARTH</span>StoveIndex
      </div>
      <a href="{header_cta_url}" target="_blank" rel="nofollow sponsored" class="text-xs sm:text-sm bg-orange-500 hover:bg-orange-400 text-stone-950 font-extrabold px-3.5 py-2 rounded-lg transition">
        {header_cta.get('cta_text', 'Shop Stoves & Chimney Kits →')}
      </a>
    </div>
  </header>

  <main class="max-w-5xl mx-auto px-4 py-12 flex-1 w-full">
    <div class="text-center max-w-2xl mx-auto mb-10">
      <h1 class="text-3xl sm:text-5xl font-black text-white tracking-tight">Wood & Pellet Stove BTU, Chimney Pipe & Fuel Database</h1>
      <p class="text-stone-400 mt-3 text-base sm:text-lg">Select your wood or pellet stove model below to calculate room BTU requirements, NFPA 211 (3-2-10 rule) roof chimney pipe height, and seasonal firewood cords or pellet tons.</p>
      <div class="mt-6">
        <input id="filterInput" type="text" placeholder="Search stove model or home size (e.g. Drolet Escape 1800, ComfortBilt HP22, PelPro, 2000 Sq Ft, Chimney Pipe...)" class="w-full bg-stone-900 border border-stone-700 rounded-xl px-4 py-3.5 text-sm text-white focus:outline-none focus:border-orange-500">
      </div>
    </div>

    <div id="stoveGrid" class="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">{cards_html}</div>
  </main>

  <footer class="border-t border-stone-800 py-8 text-center text-xs text-stone-500">
    <p>© {datetime.now(timezone.utc).year} HearthStoveIndex. As an Amazon Associate, we earn from qualifying purchases.</p>
  </footer>

  <script>
    const filterInput = document.getElementById('filterInput');
    const cards = Array.from(document.getElementById('stoveGrid').children);
    filterInput.addEventListener('input', (e) => {{
      const q = e.target.value.toLowerCase();
      cards.forEach(c => {{
        c.style.display = c.textContent.toLowerCase().includes(q) ? 'block' : 'none';
      }});
    }});
  </script>
</body>
</html>"""

    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(os.path.join(DOCS_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    urls_xml = f"""  <url>
    <loc>{SITE_BASE_URL}/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>\n"""

    for item in published:
        urls_xml += f"""  <url>
    <loc>{SITE_BASE_URL}/{item['slug']}.html</loc>
    <lastmod>{item.get('date', today)}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.9</priority>
  </url>\n"""

    with open(os.path.join(DOCS_DIR, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(f"""<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls_xml}</urlset>""")

    rss_items = ""
    for item in list(reversed(published))[:30]:
        rss_items += f"""    <item>
      <title>{item['title']}</title>
      <link>{SITE_BASE_URL}/{item['slug']}.html</link>
      <guid>{SITE_BASE_URL}/{item['slug']}.html</guid>
      <description>{item['description']}</description>
    </item>\n"""

    rss_xml = f"""<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>HearthStoveIndex Wood & Pellet Stove Sizing Database</title>
    <link>{SITE_BASE_URL}/</link>
    <description>Interactive Wood & Pellet Stove BTU, NFPA 211 Chimney Height & Fuel Calculators</description>
    <atom:link href="{SITE_BASE_URL}/rss.xml" rel="self" type="application/rss+xml" />
    <atom:link href="https://pubsubhubbub.appspot.com/" rel="hub" />
{rss_items}  </channel>
</rss>"""

    with open(os.path.join(DOCS_DIR, "rss.xml"), "w", encoding="utf-8") as f:
        f.write(rss_xml)

    with open(os.path.join(DOCS_DIR, "robots.txt"), "w", encoding="utf-8") as f:
        f.write(f"User-agent: *\nAllow: /\nSitemap: {SITE_BASE_URL}/sitemap.xml\n")

    with open(os.path.join(DOCS_DIR, f"{INDEXNOW_KEY}.txt"), "w", encoding="utf-8") as f:
        f.write(INDEXNOW_KEY)


def notify_search_engines(new_urls):
    if not SITE_BASE_URL or not new_urls:
        return
    parsed_host = urllib.parse.urlparse(SITE_BASE_URL).netloc
    payload = {
        "host": parsed_host,
        "key": INDEXNOW_KEY,
        "keyLocation": f"{SITE_BASE_URL}/{INDEXNOW_KEY}.txt",
        "urlList": new_urls
    }
    try:
        req = urllib.request.Request(
            "https://api.indexnow.org/indexnow",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(f"[INDEXNOW] Pushed {len(new_urls)} URLs (HTTP {resp.status})")
    except Exception as e:
        print(f"[WARN] IndexNow ping notice: {e}")

    try:
        hub_data = urllib.parse.urlencode({
            "hub.mode": "publish",
            "hub.url": f"{SITE_BASE_URL}/rss.xml"
        }).encode("utf-8")
        req_hub = urllib.request.Request(
            "https://pubsubhubbub.appspot.com/",
            data=hub_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST"
        )
        with urllib.request.urlopen(req_hub, timeout=15) as resp_hub:
            print(f"[WEBSUB] Google PubSubHubbub ping status: {resp_hub.status}")
    except Exception as e:
        print(f"[WARN] WebSub ping notice: {e}")


def main():
    published = load_json(PUBLISHED_FILE, [])
    mon_cfg = load_json(MONETIZATION_FILE, {})
    published_slugs = {item["slug"] for item in published}

    candidates = []
    if CUSTOM_STOVE:
        candidates.append((CUSTOM_STOVE.strip(), 75000, 2000, 6, "Cord Wood", 78))
    candidates.extend(SEED_STOVES)
    candidates.extend(discover_google_stove_queries())

    new_urls = []
    count = 0

    for stove_tuple in candidates:
        if count >= PAGES_PER_RUN:
            break
        s_name = stove_tuple[0]
        slug = slugify(f"{s_name}-btu-chimney-calculator")
        if slug in published_slugs:
            continue

        print(f"[ENGINE] Generating wood/pellet stove BTU & chimney calculator for: {s_name}...")
        try:
            data = generate_stove_data(stove_tuple)
            build_stove_html_page(data, slug, mon_cfg)
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            sp = data.get("specs", {})

            published.append({
                "stove_name": data.get("stove_name", s_name),
                "slug": slug,
                "title": data.get("seo_title", f"{s_name} BTU & Chimney Calculator"),
                "description": data.get("meta_description", ""),
                "peak_btu": int(safe_float(sp.get("peak_btu", stove_tuple[1]), stove_tuple[1])),
                "max_sqft": int(safe_float(sp.get("max_coverage_sqft", stove_tuple[2]), stove_tuple[2])),
                "flue_in": int(safe_float(sp.get("flue_collar_inches", stove_tuple[3]), stove_tuple[3])),
                "date": today
            })
            published_slugs.add(slug)
            if SITE_BASE_URL:
                new_urls.append(f"{SITE_BASE_URL}/{slug}.html")
            count += 1
            time.sleep(2)
        except Exception as e:
            print(f"[ERROR] Failed building {s_name}: {e}")

    save_json(PUBLISHED_FILE, published)
    rebuild_portal_sitemap_and_rss(published, mon_cfg)
    if new_urls and SITE_BASE_URL:
        new_urls.append(f"{SITE_BASE_URL}/")
        notify_search_engines(new_urls)
    print(f"[DONE] Published {count} new wood & pellet stove calculator pages.")


if __name__ == "__main__":
    main()
