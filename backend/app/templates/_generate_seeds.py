#!/usr/bin/env python3
"""One-shot generator for vertical starter templates under app/templates/."""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent

# Keep titles <= 24, option labels <= 20, <=6 items/cat, modifiers <=3 opts


def cat(cid: str, name: str, sort: int, parent_id: str | None = None) -> dict:
    assert len(name) <= 24, name
    out = {"id": cid, "name": name, "sort": sort, "visible": True}
    if parent_id:
        out["parent_id"] = parent_id
    return out


def item(
    iid: str,
    cat_id: str,
    name: str,
    price: int,
    sort: int,
    desc: str = "",
    modifiers: list | None = None,
) -> dict:
    assert len(name) <= 24, f"{name} ({len(name)})"
    assert len(desc) <= 72, desc
    return {
        "id": iid,
        "category_id": cat_id,
        "name": name,
        "description": desc,
        "price": price,
        "available": True,
        "sort": sort,
        "modifiers": modifiers or [],
    }


def size_mod(opts: list[tuple[str, str, int]] | None = None) -> list:
    opts = opts or [("S", "S", 0), ("M", "M", 0), ("L", "L", 0)]
    return [
        {
            "id": "mod_size",
            "name": "Size",
            "options": [
                {"id": f"sz_{o[0].lower()}", "label": o[1], "price_delta": o[2]}
                for o in opts
            ],
        }
    ]


def menu(
    greeting: str,
    categories: list,
    items: list,
    *,
    delivery_enabled=True,
    charge=100,
    free_above=1500,
    area_note="",
    confirm="Confirm karein?",
    btn="Menu dekhein",
) -> dict:
    assert len(btn) <= 20
    return {
        "categories": categories,
        "items": items,
        "settings": {
            "greeting_text": greeting,
            "menu_button_label": btn,
            "delivery": {
                "enabled": delivery_enabled,
                "charge": charge,
                "free_above": free_above,
                "area_note": area_note,
            },
            "order_confirm_note": confirm,
            "currency": "PKR",
        },
    }


def lead_interactive(business_types, locations=None, current_system=None):
    return {
        "business_types": business_types,
        "locations": locations
        or [
            {"id": "loc_1", "title": "1", "value": "1"},
            {"id": "loc_2_3", "title": "2-3", "value": "2-3"},
            {"id": "loc_4p", "title": "4+", "value": "4+"},
        ],
        "current_system": current_system
        or [
            {"id": "sys_a", "title": "Manual", "sheet_value": "Manual"},
            {"id": "sys_b", "title": "Software", "sheet_value": "Software"},
            {"id": "sys_c", "title": "Kuch nahi", "sheet_value": "None"},
        ],
    }


def tmpl(
    tid: str,
    name: str,
    vertical: str,
    flow_mode: str,
    blurb: str,
    *,
    greeting_ur: str,
    greeting_en: str,
    icon: str = "store",
    campaign: str = "",
    demo_slots: list | None = None,
    facts: str = "",
    facts_pricing: str = "",
    facts_claims: str = "",
    notes: str = "",
    menu_v2: dict | None = None,
    messages_overlay: dict | None = None,
    extra_config: dict | None = None,
) -> dict:
    cfg: dict = {
        "greeting_language": "roman_urdu",
        "campaign_phrase": campaign or name,
        "greeting_text": greeting_ur,
        "demo_slots": demo_slots or ["Kal 11am", "Kal 4pm"],
        "facts_features": facts,
        "facts_pricing_note": facts_pricing,
        "facts_claims_note": facts_claims,
        "template_notes": notes,
        "i18n": {
            "english": {
                "greeting_text": greeting_en,
            }
        },
    }
    if menu_v2:
        # Embed business placeholder already in greeting
        cfg["menu_v2"] = menu_v2
    if messages_overlay:
        cfg["messages_overlay"] = messages_overlay
    if extra_config:
        cfg.update(extra_config)
    return {
        "id": tid,
        "name": name,
        "vertical": vertical,
        "flow_mode": flow_mode,
        "blurb": blurb,
        "icon": icon,
        "languages": ["roman_urdu", "english"],
        "config": cfg,
    }


TEMPLATES: list[dict] = []

# ── 1. restaurant ────────────────────────────────────────────────────────────
TEMPLATES.append(
    tmpl(
        "restaurant",
        "Restaurant / Cafe",
        "restaurant",
        "order",
        "Pakistani restaurant menu — starters, mains, BBQ, deals, drinks.",
        icon="utensils",
        greeting_ur=(
            "Assalam o Alaikum! [Business] mein khush aamdeed 🍽️ "
            "Order karne ke liye neeche menu dekhein."
        ),
        greeting_en="Welcome to [Business]! Tap below to browse the menu and order.",
        campaign="Order Now",
        facts="Dine-in quality, home delivery available.",
        notes="Replace [Business] is auto-filled with tenant name on apply.",
        menu_v2=menu(
            "Assalam o Alaikum! [Business] mein khush aamdeed 🍽️ Order karne ke liye neeche menu dekhein.",
            [
                cat("c_start", "Starters", 0),
                cat("c_main", "Main Course", 1),
                cat("c_bbq", "BBQ", 2),
                cat("c_deals", "Deals", 3),
                cat("c_drink", "Drinks", 4),
            ],
            [
                item("i_soup", "c_start", "Chicken Corn Soup", 350, 0),
                item("i_fries", "c_start", "Masala Fries", 250, 1),
                item("i_wings", "c_start", "Hot Wings (6pc)", 450, 2),
                item("i_samosa", "c_start", "Chicken Samosa", 80, 3),
                item("i_biryani", "c_main", "Chicken Biryani", 450, 0, "Full plate"),
                item("i_karahi", "c_main", "Chicken Karahi", 1200, 1, "Half"),
                item("i_karahi_f", "c_main", "Chicken Karahi Full", 2200, 2),
                item("i_daal", "c_main", "Daal Mash Fry", 350, 3),
                item("i_pulao", "c_main", "Beef Pulao", 500, 4),
                item("i_boti", "c_bbq", "Chicken Boti", 650, 0),
                item("i_seekh", "c_bbq", "Seekh Kabab (4)", 480, 1),
                item("i_malai", "c_bbq", "Malai Boti", 720, 2),
                item("i_tikka", "c_bbq", "Chicken Tikka", 550, 3),
                item("i_deal2", "c_deals", "Deal for 2", 1499, 0, "2 mains + drinks"),
                item("i_deal4", "c_deals", "Family Deal", 2999, 1, "4 people"),
                item("i_student", "c_deals", "Student Deal", 499, 2),
                item("i_bbqdeal", "c_deals", "BBQ Platter", 2499, 3, "Mixed BBQ"),
                item("i_lunch", "c_deals", "Lunch Special", 399, 4),
                item("i_chai", "c_drink", "Doodh Patti", 100, 0),
                item("i_soft", "c_drink", "Soft Drink", 80, 1),
                item("i_lassi", "c_drink", "Sweet Lassi", 150, 2),
                item("i_water", "c_drink", "Mineral Water", 60, 3),
            ],
            charge=100,
            free_above=1500,
            area_note="City limits",
        ),
        messages_overlay={
            "order": {
                "greeting": (
                    "Assalam o Alaikum! [Business] mein khush aamdeed 🍽️ "
                    "Order karne ke liye neeche menu dekhein."
                )
            }
        },
    )
)

# ── 2. grocery_kiryana ───────────────────────────────────────────────────────
TEMPLATES.append(
    tmpl(
        "grocery_kiryana",
        "Grocery / Kiryana",
        "grocery",
        "order",
        "Neighborhood kiryana staples — aata, oil, dairy, household.",
        icon="shopping-basket",
        greeting_ur=(
            "Assalam o Alaikum! [Business] — ghar ki zarooriyat yahan se order karein. "
            "Menu neeche hai."
        ),
        greeting_en="Assalam o Alaikum! Order groceries from [Business] — tap menu below.",
        menu_v2=menu(
            "Assalam o Alaikum! [Business] — ghar ki zarooriyat yahan se order karein. Menu neeche hai.",
            [
                cat("c_grain", "Aata/Rice/Daal", 0),
                cat("c_oil", "Cooking Oil/Ghee", 1),
                cat("c_dairy", "Dairy/Eggs", 2),
                cat("c_bev", "Beverages", 3),
                cat("c_house", "Household", 4),
            ],
            [
                item("i_aata", "c_grain", "Aata 10kg", 1450, 0),
                item("i_rice", "c_grain", "Basmati Rice 5kg", 1800, 1),
                item("i_daal", "c_grain", "Daal Masoor 1kg", 320, 2),
                item("i_chann", "c_grain", "Chana Daal 1kg", 280, 3),
                item("i_oil", "c_oil", "Cooking Oil 5L", 2100, 0),
                item("i_ghee", "c_oil", "Banaspati 1kg", 550, 1),
                item("i_olive", "c_oil", "Olive Oil 500ml", 1200, 2),
                item("i_mustard", "c_oil", "Mustard Oil 1L", 650, 3),
                item("i_sunflo", "c_oil", "Sunflower Oil 5L", 1950, 4),
                item("i_milk", "c_dairy", "Milk Pack 1L", 280, 0),
                item("i_eggs", "c_dairy", "Eggs (Dozen)", 420, 1),
                item("i_yogurt", "c_dairy", "Yogurt 1kg", 350, 2),
                item("i_butter", "c_dairy", "Butter 200g", 380, 3),
                item("i_tea", "c_bev", "Tea Whitener", 250, 0),
                item("i_juice", "c_bev", "Juice 1L", 220, 1),
                item("i_cola", "c_bev", "Soft Drink 1.5L", 180, 2),
                item("i_waterb", "c_bev", "Mineral Water 6pk", 280, 3),
                item("i_energy", "c_bev", "Energy Drink", 250, 4),
                item("i_det", "c_house", "Detergent 1kg", 450, 0),
                item("i_soap", "c_house", "Bath Soap", 120, 1),
                item("i_tissue", "c_house", "Tissue Pack", 180, 2),
                item("i_dish", "c_house", "Dishwash Liquid", 220, 3),
                item("i_phenol", "c_house", "Phenyl 1L", 180, 4),
            ],
            charge=50,
            free_above=2000,
            area_note="Local delivery only",
        ),
    )
)

# ── 3. water_supplier ────────────────────────────────────────────────────────
TEMPLATES.append(
    tmpl(
        "water_supplier",
        "Water Supplier",
        "water",
        "order",
        "Bottled water + refill — tuned for repeat / regular delivery.",
        icon="droplets",
        greeting_ur=(
            "Assalam o Alaikum! Paani order karne ke liye neeche se muntakhib karein 💧"
        ),
        greeting_en="Assalam o Alaikum! Choose your water order below 💧",
        notes="Regular delivery: customer can mention weekly schedule in chat.",
        facts="19L bottles, refill, packs. Regular delivery available on request.",
        menu_v2=menu(
            "Assalam o Alaikum! Paani order karne ke liye neeche se muntakhib karein 💧",
            [
                cat("c_bottle", "19L Bottles", 0),
                cat("c_pack", "Packs & Dispenser", 1),
            ],
            [
                item("i_19new", "c_bottle", "19L Bottle (new)", 350, 0, "With bottle"),
                item("i_19ref", "c_bottle", "19L Refill", 150, 1, "Empty exchange"),
                item("i_19x2", "c_bottle", "2x 19L Refill", 280, 2),
                item("i_19x4", "c_bottle", "4x 19L Refill", 520, 3),
                item("i_pack6", "c_pack", "6-Bottle Pack", 800, 0, "Small bottles"),
                item("i_pack12", "c_pack", "12-Bottle Pack", 1500, 1),
                item("i_disp", "c_pack", "Dispenser", 4500, 2, "Purchase"),
                item("i_stand", "c_pack", "Bottle Stand", 1200, 3),
            ],
            charge=0,
            free_above=0,
            area_note="Service area — confirm before first delivery",
            confirm="Order confirm? (Regular delivery note bata sakte hain)",
            btn="Order karein",
        ),
        messages_overlay={
            "order": {
                "greeting": (
                    "Assalam o Alaikum! Paani order karne ke liye neeche se muntakhib karein 💧"
                ),
                "confirm_note": (
                    "Confirm karein? Agar regular delivery chahiye to address ke sath likhein."
                ),
            }
        },
    )
)

# ── 4. pharmacy ──────────────────────────────────────────────────────────────
TEMPLATES.append(
    tmpl(
        "pharmacy",
        "Pharmacy",
        "pharmacy",
        "order",
        "OTC, personal care, baby care, supplements. Rx via nuskha.",
        icon="pill",
        greeting_ur=(
            "Assalam o Alaikum! [Business] — OTC items menu se order karein. "
            "Prescription medicines ke liye nuskha bhejein."
        ),
        greeting_en=(
            "Welcome to [Business]! Order OTC below. "
            "For prescription medicines, please send your nuskha."
        ),
        notes="Prescription items require pharmacist confirmation — never auto-confirm Rx.",
        facts="OTC only via menu. Rx: send prescription photo for pharmacist confirmation.",
        menu_v2=menu(
            "Assalam o Alaikum! [Business] — OTC menu. Prescription medicines ke liye nuskha bhejein.",
            [
                cat("c_otc", "OTC Medicines", 0),
                cat("c_pc", "Personal Care", 1),
                cat("c_baby", "Baby Care", 2),
                cat("c_supp", "Supplements", 3),
            ],
            [
                item("i_panadol", "c_otc", "Panadol Tab", 35, 0, "Strip"),
                item("i_disprin", "c_otc", "Disprin", 40, 1),
                item("i_ors", "c_otc", "ORS Sachet", 50, 2),
                item("i_cough", "c_otc", "Cough Syrup", 280, 3),
                item("i_antac", "c_otc", "Antacid Tab", 80, 4),
                item("i_shamp", "c_pc", "Shampoo 200ml", 450, 0),
                item("i_tooth", "c_pc", "Toothpaste", 220, 1),
                item("i_san", "c_pc", "Hand Sanitizer", 180, 2),
                item("i_lotion", "c_pc", "Body Lotion", 550, 3),
                item("i_diaper", "c_baby", "Diapers M (pack)", 1200, 0),
                item("i_wipes", "c_baby", "Baby Wipes", 350, 1),
                item("i_feed", "c_baby", "Feeding Bottle", 650, 2),
                item("i_bsoap", "c_baby", "Baby Soap", 280, 3),
                item("i_vitc", "c_supp", "Vitamin C", 400, 0),
                item("i_multi", "c_supp", "Multivitamin", 850, 1),
                item("i_omega", "c_supp", "Omega-3", 1100, 2),
                item("i_cal", "c_supp", "Calcium Tab", 650, 3),
            ],
            charge=100,
            free_above=2000,
            area_note="Same-day local delivery",
        ),
    )
)

# ── 5. bakery ────────────────────────────────────────────────────────────────
TEMPLATES.append(
    tmpl(
        "bakery",
        "Bakery",
        "bakery",
        "order",
        "Cakes, pastries, bread, savory — birthday deals + custom-cake note.",
        icon="cake",
        greeting_ur=(
            "Assalam o Alaikum! [Business] bakery — fresh items order karein. "
            "Custom cake ke liye details likhein."
        ),
        greeting_en="Welcome to [Business]! Order fresh bakes below. Custom cakes: describe in chat.",
        notes="Custom-cake: customer describes size/flavor in chat after selecting Custom Cake.",
        menu_v2=menu(
            "Assalam o Alaikum! [Business] bakery — fresh order. Custom cake ke liye details likhein.",
            [
                cat("c_cakes", "Cakes", 0),
                cat("c_past", "Pastries", 1),
                cat("c_bread", "Bread/Rusk", 2),
                cat("c_sav", "Savory", 3),
            ],
            [
                item("i_choc", "c_cakes", "Chocolate Cake", 2500, 0, "1 pound"),
                item("i_pine", "c_cakes", "Pineapple Cake", 2200, 1, "1 pound"),
                item("i_bday", "c_cakes", "Birthday Deal", 3500, 2, "Cake + 6 pastries"),
                item("i_custom", "c_cakes", "Custom Cake", 3000, 3, "Details in chat"),
                item("i_croissant", "c_past", "Croissant", 180, 0),
                item("i_danish", "c_past", "Danish Pastry", 200, 1),
                item("i_cup", "c_past", "Cupcake (2pc)", 250, 2),
                item("i_eclair", "c_past", "Chocolate Eclair", 220, 3),
                item("i_bread", "c_bread", "Sandwich Bread", 160, 0),
                item("i_rusk", "c_bread", "Rusk Pack", 280, 1),
                item("i_bun", "c_bread", "Burger Buns (4)", 120, 2),
                item("i_naan", "c_bread", "Naan (2pc)", 80, 3),
                item("i_toast", "c_bread", "Toast Pack", 200, 4),
                item("i_patties", "c_sav", "Chicken Patty", 120, 0),
                item("i_roll", "c_sav", "Chicken Roll", 200, 1),
                item("i_samosa_b", "c_sav", "Aloo Samosa", 60, 2),
                item("i_pakora", "c_sav", "Pakora Plate", 150, 3),
                item("i_pizza_s", "c_sav", "Mini Pizza", 350, 4),
            ],
            charge=100,
            free_above=2500,
        ),
    )
)

# ── 6. clothing_retail ───────────────────────────────────────────────────────
size = size_mod()
TEMPLATES.append(
    tmpl(
        "clothing_retail",
        "Clothing Retail",
        "clothing",
        "order",
        "Men/Women/Kids/Fabric with Size modifier — ask for availability.",
        icon="shirt",
        greeting_ur=(
            "Assalam o Alaikum! [Business] — collection dekhein. "
            "Size/availability poochne ke liye message karein."
        ),
        greeting_en="Welcome to [Business]! Browse below. Ask in chat for size or stock.",
        facts="Sizes vary — confirm availability before payment.",
        menu_v2=menu(
            "Assalam o Alaikum! [Business] — collection dekhein. Size/availability pooch sakte hain.",
            [
                cat("c_men", "Men", 0),
                cat("c_wom", "Women", 1),
                cat("c_kid", "Kids", 2),
                cat("c_fab", "Fabric", 3),
            ],
            [
                item("i_kurta", "c_men", "Cotton Kurta", 2200, 0, modifiers=size),
                item("i_shalwar", "c_men", "Shalwar Kameez", 3500, 1, modifiers=size),
                item("i_jeans", "c_men", "Denim Jeans", 2800, 2, modifiers=size),
                item("i_polo", "c_men", "Polo Shirt", 1800, 3, modifiers=size),
                item("i_lawn", "c_wom", "Lawn Suit", 4500, 0, modifiers=size),
                item("i_abaya", "c_wom", "Abaya", 3200, 1, modifiers=size),
                item("i_dupatta", "c_wom", "Dupatta", 900, 2),
                item("i_kurti", "c_wom", "Kurti", 2200, 3, modifiers=size),
                item("i_kidset", "c_kid", "Kids Suit", 1800, 0, modifiers=size),
                item("i_kidt", "c_kid", "Kids T-Shirt", 650, 1, modifiers=size),
                item("i_kidj", "c_kid", "Kids Jeans", 1200, 2, modifiers=size),
                item("i_kidf", "c_kid", "Kids Frock", 1500, 3, modifiers=size),
                item("i_cotton", "c_fab", "Cotton (meter)", 450, 0),
                item("i_lawnf", "c_fab", "Lawn (meter)", 380, 1),
                item("i_silk", "c_fab", "Silk (meter)", 1200, 2),
                item("i_chiff", "c_fab", "Chiffon (meter)", 550, 3),
            ],
            charge=150,
            free_above=5000,
            area_note="City delivery",
        ),
    )
)

# ── 7. salon_booking (lead) ──────────────────────────────────────────────────
TEMPLATES.append(
    tmpl(
        "salon_booking",
        "Salon Booking",
        "salon",
        "lead",
        "Appointment bot — services list then scheduling slots.",
        icon="scissors",
        greeting_ur=(
            "Assalam o Alaikum! Appointment book karne mein madad karte hain. "
            "Service choose karein."
        ),
        greeting_en="Assalam o Alaikum! Let's book your appointment — pick a service.",
        demo_slots=["Aaj 4pm", "Kal 11am"],
        campaign="Book Appointment",
        messages_overlay={
            "lead": {
                "greeting_line": (
                    "Assalam o Alaikum! Appointment book karne mein madad karte hain."
                ),
                "value_line": "Preferred time batayein — hum confirm kar denge.",
                "q_business_name": "Aapka naam kya hai?",
                "q_business_type": "Kaunsi service chahiye?",
                "q_locations": "Kaunsa branch / area?",
                "q_current_system": "Pehle kab aaye the?",
                "q_scheduling": "Preferred slot choose karein:",
            },
            "interactive": lead_interactive(
                [
                    {"id": "svc_cut", "title": "Haircut", "description": "Cut & style", "value": "Haircut"},
                    {"id": "svc_fac", "title": "Facial", "description": "Skin care", "value": "Facial"},
                    {"id": "svc_bri", "title": "Bridal", "description": "Bridal package", "value": "Bridal"},
                    {"id": "svc_man", "title": "Manicure", "description": "Nails", "value": "Manicure"},
                    {"id": "svc_ped", "title": "Pedicure", "description": "Feet care", "value": "Pedicure"},
                    {"id": "svc_col", "title": "Hair Color", "description": "Coloring", "value": "Color"},
                    {"id": "svc_wax", "title": "Waxing", "description": "Body wax", "value": "Waxing"},
                    {"id": "svc_meh", "title": "Mehndi", "description": "Henna", "value": "Mehndi"},
                    {"id": "svc_mak", "title": "Makeup", "description": "Party/bridal", "value": "Makeup"},
                    {"id": "svc_oth", "title": "Other", "description": "Something else", "value": "Other"},
                ],
                [
                    {"id": "loc_main", "title": "Main branch", "value": "Main"},
                    {"id": "loc_mall", "title": "Mall outlet", "value": "Mall"},
                    {"id": "loc_home", "title": "Home service", "value": "Home"},
                    {"id": "loc_ladies", "title": "Ladies only", "value": "Ladies"},
                ],
                [
                    {"id": "vis_new", "title": "Pehli baar", "sheet_value": "New"},
                    {"id": "vis_ret", "title": "Wapas aa rahe", "sheet_value": "Returning"},
                    {"id": "vis_ref", "title": "Referral", "sheet_value": "Referral"},
                    {"id": "vis_pkg", "title": "Package member", "sheet_value": "Package"},
                ],
            ),
        },
    )
)

# ── 8. pos_lead ──────────────────────────────────────────────────────────────
TEMPLATES.append(
    tmpl(
        "pos_lead",
        "POS / B2B Software Lead",
        "pos",
        "lead",
        "Bahi POS–style lead qualification for any B2B software reseller.",
        icon="monitor",
        greeting_ur="Assalam o Alaikum 🙏 Bahi POS mein aap ki dilchaspi ka shukriya.",
        greeting_en="Assalam o Alaikum! Thanks for your interest in our POS software.",
        campaign="Bahi POS",
        demo_slots=["Kal 11am", "Kal 4pm"],
        facts="Inventory, billing, multi-branch reports, WhatsApp order sync.",
        facts_pricing="Packages start from a monthly subscription — quote after demo.",
        facts_claims="Used by retailers, pharmacies, and restaurants across Pakistan.",
        messages_overlay={
            "lead": {
                "greeting_line": "Assalam o Alaikum 🙏 Bahi POS mein aap ki dilchaspi ka shukriya.",
                "value_line": (
                    "Bahi POS aap ke business ki sales, stock, khata aur invoicing "
                    "ko ek jagah manage karta hai."
                ),
            },
            "interactive": lead_interactive(
                [
                    {"id": "grocery", "title": "Grocery / Kiryana", "description": "Kirana store", "value": "Grocery / Kiryana"},
                    {"id": "restaurant", "title": "Restaurant", "description": "Cafe / restaurant", "value": "Restaurant"},
                    {"id": "pharmacy", "title": "Pharmacy", "description": "Medical store", "value": "Pharmacy"},
                    {"id": "garments", "title": "Garments", "description": "Clothing retail", "value": "Garments"},
                    {"id": "electronics", "title": "Mobile / Electronics", "description": "Phones & gadgets", "value": "Mobile / Electronics"},
                    {"id": "general_store", "title": "General Store", "description": "Variety store", "value": "General Store"},
                    {"id": "hardware", "title": "Hardware", "description": "Tools & supplies", "value": "Hardware"},
                    {"id": "bakery", "title": "Bakery", "description": "Cakes & bread", "value": "Bakery"},
                    {"id": "beauty", "title": "Beauty / Salon", "description": "Cosmetics / salon", "value": "Beauty"},
                    {"id": "other", "title": "Other", "description": "Something else", "value": "Other"},
                ],
            ),
        },
    )
)

# ── 9. generic_order / generic_lead ───────────────────────────────────────────
TEMPLATES.append(
    tmpl(
        "generic_order",
        "Generic Order",
        "generic",
        "order",
        "Minimal order skeleton — add your own categories in Settings.",
        icon="shopping-cart",
        greeting_ur="Assalam o Alaikum! Order ke liye neeche menu dekhein.",
        greeting_en="Assalam o Alaikum! Tap below to view the menu.",
        menu_v2=menu(
            "Assalam o Alaikum! Order ke liye neeche menu dekhein.",
            [
                cat("c_pop", "Popular", 0),
                cat("c_more", "More Items", 1),
            ],
            [
                item("i_a", "c_pop", "Item A", 100, 0, "Edit in Settings"),
                item("i_b", "c_pop", "Item B", 200, 1),
                item("i_c", "c_pop", "Item C", 300, 2),
                item("i_d", "c_pop", "Item D", 400, 3),
                item("i_e", "c_more", "Item E", 500, 0),
                item("i_f", "c_more", "Item F", 600, 1),
                item("i_g", "c_more", "Item G", 700, 2),
                item("i_h", "c_more", "Item H", 800, 3),
            ],
            charge=100,
            free_above=0,
        ),
    )
)

TEMPLATES.append(
    tmpl(
        "generic_lead",
        "Generic Lead",
        "generic",
        "lead",
        "Minimal lead skeleton — customize questions in Settings.",
        icon="message-circle",
        greeting_ur="Assalam o Alaikum! Kaise madad kar sakte hain?",
        greeting_en="Assalam o Alaikum! How can we help you today?",
        campaign="Hello",
        messages_overlay={
            "lead": {
                "greeting_line": "Assalam o Alaikum! Kaise madad kar sakte hain?",
                "value_line": "Thori si info dein — hum guide kar denge.",
            }
        },
    )
)

# ── 10. hardware_store ───────────────────────────────────────────────────────
TEMPLATES.append(
    tmpl(
        "hardware_store",
        "Hardware Store",
        "hardware",
        "order",
        "Tools, paint, plumbing, electrical, fasteners.",
        icon="wrench",
        greeting_ur="Assalam o Alaikum! [Business] hardware — zarooriyat order karein.",
        greeting_en="Welcome to [Business] hardware — order tools and supplies below.",
        menu_v2=menu(
            "Assalam o Alaikum! [Business] hardware — zarooriyat order karein.",
            [
                cat("c_tools", "Tools", 0),
                cat("c_paint", "Paint/Chemicals", 1),
                cat("c_plumb", "Plumbing", 2),
                cat("c_elec", "Electrical", 3),
                cat("c_fast", "Fasteners", 4),
            ],
            [
                item("i_ham", "c_tools", "Hammer", 650, 0),
                item("i_screw", "c_tools", "Screwdriver Set", 850, 1),
                item("i_plier", "c_tools", "Pliers", 450, 2),
                item("i_tape", "c_tools", "Measuring Tape", 280, 3),
                item("i_paint1", "c_paint", "Emulsion 1L", 1200, 0),
                item("i_paint4", "c_paint", "Emulsion 4L", 4200, 1),
                item("i_thinner", "c_paint", "Thinner 1L", 350, 2),
                item("i_primer", "c_paint", "Primer 1L", 900, 3),
                item("i_brush", "c_paint", "Paint Brush Set", 450, 4),
                item("i_pipe", "c_plumb", "PVC Pipe 1in", 180, 0, "Per length"),
                item("i_tap", "c_plumb", "Basin Mixer", 2200, 1),
                item("i_elbow", "c_plumb", "Elbow Joint", 60, 2),
                item("i_valve", "c_plumb", "Ball Valve", 350, 3),
                item("i_switch", "c_elec", "Switch Board", 450, 0),
                item("i_wire", "c_elec", "Wire 1.5mm (coil)", 2800, 1),
                item("i_bulb", "c_elec", "LED Bulb 12W", 350, 2),
                item("i_socket", "c_elec", "Wall Socket", 280, 3),
                item("i_screw2", "c_fast", "Screw Pack", 150, 0),
                item("i_nail", "c_fast", "Nail Pack", 120, 1),
                item("i_nut", "c_fast", "Nut Bolt Assort", 200, 2),
                item("i_washer", "c_fast", "Washer Pack", 100, 3),
            ],
            delivery_enabled=False,
            charge=0,
            free_above=0,
            area_note="Delivery optional — ask in chat",
        ),
    )
)

# ── 11. mobile_accessories ───────────────────────────────────────────────────
TEMPLATES.append(
    tmpl(
        "mobile_accessories",
        "Mobile Accessories",
        "mobile",
        "order",
        "Chargers, covers, earbuds, power banks + repair inquiry.",
        icon="smartphone",
        greeting_ur=(
            "Assalam o Alaikum! [Business] — accessories order karein. "
            "Model bata kar availability pooch sakte hain."
        ),
        greeting_en="Welcome to [Business]! Order accessories or ask about your phone model.",
        menu_v2=menu(
            "Assalam o Alaikum! [Business] — accessories. Model-specific sawal pooch sakte hain.",
            [
                cat("c_chg", "Chargers/Cables", 0),
                cat("c_cov", "Covers/Protectors", 1),
                cat("c_aud", "Earbuds/Audio", 2),
                cat("c_pb", "Power Banks", 3),
                cat("c_rep", "Repairs", 4),
            ],
            [
                item("i_c20", "c_chg", "20W Fast Charger", 1200, 0),
                item("i_ctype", "c_chg", "Type-C Cable", 450, 1),
                item("i_light", "c_chg", "Lightning Cable", 550, 2),
                item("i_car", "c_chg", "Car Charger", 800, 3),
                item("i_cover", "c_cov", "Silicon Cover", 400, 0),
                item("i_glass", "c_cov", "Tempered Glass", 350, 1),
                item("i_wallet", "c_cov", "Wallet Case", 900, 2),
                item("i_clear", "c_cov", "Clear Case", 350, 3),
                item("i_buds", "c_aud", "Wireless Earbuds", 2500, 0),
                item("i_bt", "c_aud", "BT Speaker Mini", 1800, 1),
                item("i_wired", "c_aud", "Wired Earphones", 450, 2),
                item("i_neck", "c_aud", "Neckband", 2200, 3),
                item("i_pb10", "c_pb", "Power Bank 10k", 2200, 0),
                item("i_pb20", "c_pb", "Power Bank 20k", 3500, 1),
                item("i_pb5", "c_pb", "Power Bank 5k", 1500, 2),
                item("i_mag", "c_pb", "MagSafe Bank", 4500, 3),
                item("i_scr", "c_rep", "Screen Repair", 1, 0, "Quote after model"),
                item("i_bat", "c_rep", "Battery Replace", 1, 1, "Quote after model"),
                item("i_diag", "c_rep", "Diagnosis", 500, 2),
                item("i_soft", "c_rep", "Software Fix", 800, 3),
            ],
            charge=100,
            free_above=3000,
        ),
    )
)

# ── 12. electronics_appliances ───────────────────────────────────────────────
TEMPLATES.append(
    tmpl(
        "electronics_appliances",
        "Electronics & Appliances",
        "electronics",
        "order",
        "Home/kitchen appliances — installation & warranty notes.",
        icon="tv",
        greeting_ur=(
            "Assalam o Alaikum! [Business] — appliances dekhein. "
            "Warranty included; installation alag se confirm."
        ),
        greeting_en="Welcome to [Business]! Browse appliances. Warranty included; ask about install.",
        notes="Installation note: confirm separately. Warranty mentioned in greeting.",
        menu_v2=menu(
            "Assalam o Alaikum! [Business] — appliances. Warranty included; installation confirm karein.",
            [
                cat("c_home", "Home Appliances", 0),
                cat("c_kit", "Kitchen", 1),
                cat("c_fan", "Fans/Cooling", 2),
                cat("c_sm", "Small Electronics", 3),
            ],
            [
                item("i_wash", "c_home", "Washing Machine", 45000, 0, "Auto 7kg"),
                item("i_fridge", "c_home", "Refrigerator", 85000, 1, "Inverter"),
                item("i_iron", "c_home", "Dry Iron", 3500, 2),
                item("i_vac", "c_home", "Vacuum Cleaner", 18000, 3),
                item("i_micro", "c_kit", "Microwave", 22000, 0),
                item("i_blend", "c_kit", "Blender", 6500, 1),
                item("i_kettle", "c_kit", "Electric Kettle", 4200, 2),
                item("i_toast", "c_kit", "Toaster", 5500, 3),
                item("i_fan", "c_fan", "Pedestal Fan", 8500, 0),
                item("i_ac", "c_fan", "AC 1.5 Ton", 145000, 1, "Inverter"),
                item("i_cooler", "c_fan", "Room Cooler", 18000, 2),
                item("i_cfan", "c_fan", "Ceiling Fan", 6500, 3),
                item("i_trim", "c_sm", "Trimmer", 2800, 0),
                item("i_scale", "c_sm", "Kitchen Scale", 1500, 1),
                item("i_ext", "c_sm", "Extension Board", 900, 2),
                item("i_hair", "c_sm", "Hair Dryer", 3200, 3),
            ],
            charge=300,
            free_above=50000,
            area_note="Installation on request",
            confirm="Confirm? Installation/warranty chat mein pooch sakte hain.",
        ),
    )
)

# ── 13. meat_poultry ─────────────────────────────────────────────────────────
TEMPLATES.append(
    tmpl(
        "meat_poultry",
        "Meat & Poultry",
        "meat",
        "order",
        "Per-kg chicken/mutton/beef/fish — same-day delivery cutoff.",
        icon="beef",
        greeting_ur=(
            "Assalam o Alaikum! [Business] — fresh meat order karein (per kg). "
            "Kitne kg chahiye batayein. Same-day delivery (cutoff note Settings mein)."
        ),
        greeting_en="Order fresh meat from [Business] (per kg). Tell us how many kg. Same-day delivery.",
        notes="Weight-based: after item pick, ask kitne kg. Cutoff-time in area_note.",
        menu_v2=menu(
            "Assalam o Alaikum! Fresh meat (per kg). Kitne kg chahiye batayein. Same-day delivery.",
            [
                cat("c_ch", "Chicken", 0),
                cat("c_mut", "Mutton", 1),
                cat("c_beef", "Beef", 2),
                cat("c_fish", "Fish", 3),
                cat("c_cut", "Ready Cuts", 4),
            ],
            [
                item("i_chkg", "c_ch", "Chicken (per kg)", 550, 0),
                item("i_chbon", "c_ch", "Boneless (kg)", 850, 1),
                item("i_chleg", "c_ch", "Legs (kg)", 600, 2),
                item("i_chbr", "c_ch", "Breast (kg)", 750, 3),
                item("i_mutkg", "c_mut", "Mutton (per kg)", 2200, 0),
                item("i_mutk", "c_mut", "Mutton Karahi Cut", 2300, 1),
                item("i_mutch", "c_mut", "Mutton Chops (kg)", 2400, 2),
                item("i_mutleg", "c_mut", "Leg Piece (kg)", 2350, 3),
                item("i_beefkg", "c_beef", "Beef (per kg)", 1600, 0),
                item("i_keema", "c_beef", "Beef Keema (kg)", 1700, 1),
                item("i_steak", "c_beef", "Beef Steak (kg)", 2200, 2),
                item("i_ribs", "c_beef", "Beef Ribs (kg)", 1800, 3),
                item("i_fishkg", "c_fish", "Rohu (per kg)", 900, 0),
                item("i_prawn", "c_fish", "Prawns (kg)", 1800, 1),
                item("i_til", "c_fish", "Tilapia (kg)", 750, 2),
                item("i_surmai", "c_fish", "Surmai (kg)", 2200, 3),
                item("i_qorma", "c_cut", "Qorma Cut (kg)", 600, 0),
                item("i_boticut", "c_cut", "Boti Cut (kg)", 650, 1),
                item("i_handi", "c_cut", "Handi Cut (kg)", 620, 2),
                item("i_biryani", "c_cut", "Biryani Cut (kg)", 580, 3),
            ],
            charge=100,
            free_above=3000,
            area_note="Same-day: order before 4pm",
            confirm="Confirm? Kg quantity chat mein likhein.",
            btn="Meat menu",
        ),
    )
)

# ── 14. fruits_vegetables ────────────────────────────────────────────────────
TEMPLATES.append(
    tmpl(
        "fruits_vegetables",
        "Fruits & Vegetables",
        "produce",
        "order",
        "Sabzi mandi style — rates aaj ke hisaab se, weight-based.",
        icon="carrot",
        greeting_ur=(
            "Assalam o Alaikum! [Business] sabzi — rates aaj ke hisaab se. "
            "Neeche se order karein (per kg)."
        ),
        greeting_en="Assalam o Alaikum! Today's rates at [Business]. Order produce below (per kg).",
        notes="Prices change daily — update in Settings each morning.",
        facts="Rates aaj ke hisaab se — daily update recommended.",
        menu_v2=menu(
            "Assalam o Alaikum! Rates aaj ke hisaab se. Sabzi/fruit (per kg) order karein.",
            [
                cat("c_veg", "Vegetables", 0),
                cat("c_fru", "Fruits", 1),
                cat("c_herb", "Herbs", 2),
            ],
            [
                item("i_tam", "c_veg", "Tamatar (kg)", 120, 0),
                item("i_alu", "c_veg", "Aalu (kg)", 80, 1),
                item("i_pyaz", "c_veg", "Pyaz (kg)", 100, 2),
                item("i_bhindi", "c_veg", "Bhindi (kg)", 160, 3),
                item("i_matar", "c_veg", "Matar (kg)", 200, 4),
                item("i_kela", "c_fru", "Kela (dozen)", 180, 0),
                item("i_saib", "c_fru", "Saib (kg)", 350, 1),
                item("i_ambo", "c_fru", "Aam (kg)", 400, 2),
                item("i_angur", "c_fru", "Angoor (kg)", 450, 3),
                item("i_dhani", "c_herb", "Dhania bunch", 40, 0),
                item("i_podi", "c_herb", "Podina bunch", 40, 1),
                item("i_adrak", "c_herb", "Adrak (kg)", 500, 2),
                item("i_lehsun", "c_herb", "Lehsun (kg)", 450, 3),
                item("i_hari", "c_herb", "Hari Mirch (kg)", 200, 4),
            ],
            charge=80,
            free_above=1500,
            area_note="Morning delivery preferred",
            confirm="Confirm? Kg batayein. Rates aaj ke hisaab se.",
        ),
    )
)

# ── 15. dairy_milk ───────────────────────────────────────────────────────────
TEMPLATES.append(
    tmpl(
        "dairy_milk",
        "Dairy / Milk",
        "dairy",
        "order",
        "Fresh milk & dairy — morning delivery + subscription note.",
        icon="milk",
        greeting_ur=(
            "Assalam o Alaikum! [Business] dairy — fresh milk order karein. "
            "Subah delivery / regular subscription available."
        ),
        greeting_en="Fresh dairy from [Business]. Morning delivery & regular subscription available.",
        notes="Like water_supplier: customers can request regular morning delivery.",
        menu_v2=menu(
            "Assalam o Alaikum! Fresh dairy — subah delivery / regular subscription available.",
            [
                cat("c_milk", "Fresh Milk", 0),
                cat("c_cult", "Yogurt/Butter", 1),
                cat("c_ghee", "Ghee/Cream", 2),
            ],
            [
                item("i_milk1", "c_milk", "Fresh Milk 1L", 220, 0),
                item("i_milk2", "c_milk", "Fresh Milk 2L", 420, 1),
                item("i_milk5", "c_milk", "Fresh Milk 5L", 1000, 2),
                item("i_toned", "c_milk", "Toned Milk 1L", 200, 3),
                item("i_yog", "c_cult", "Yogurt 1kg", 300, 0),
                item("i_but", "c_cult", "Butter 200g", 380, 1),
                item("i_lassi", "c_cult", "Lassi 1L", 250, 2),
                item("i_raita", "c_cult", "Raita Pack", 180, 3),
                item("i_ghee", "c_ghee", "Desi Ghee 1kg", 2200, 0),
                item("i_cream", "c_ghee", "Fresh Cream", 250, 1),
                item("i_cheese", "c_ghee", "Cheese Slice", 450, 2),
                item("i_khoya", "c_ghee", "Khoya 500g", 800, 3),
            ],
            charge=50,
            free_above=1000,
            area_note="Morning delivery window 7–10am",
            confirm="Confirm? Regular delivery chahiye to likhein.",
            btn="Dairy menu",
        ),
    )
)

# ── 16. gym_fitness (lead) ───────────────────────────────────────────────────
TEMPLATES.append(
    tmpl(
        "gym_fitness",
        "Gym / Fitness",
        "gym",
        "lead",
        "Membership plans → trial/tour scheduling.",
        icon="dumbbell",
        greeting_ur=(
            "Assalam o Alaikum! [Business] — membership ya trial book karein. "
            "Plan choose karein."
        ),
        greeting_en="Join [Business]! Pick a plan or book a trial tour.",
        demo_slots=["Aaj 6pm", "Kal 10am"],
        campaign="Gym Trial",
        messages_overlay={
            "lead": {
                "greeting_line": "Assalam o Alaikum! Membership ya trial book karein.",
                "value_line": "Plan choose karein — hum tour/trial schedule kar denge.",
                "q_business_name": "Aapka naam?",
                "q_business_type": "Kaunsa plan / interest?",
                "q_locations": "Preferred branch?",
                "q_current_system": "Pehle gym join kiya tha?",
                "q_scheduling": "Trial/tour ke liye slot choose karein:",
                "pricing_text": (
                    "Fees plan aur duration pe depend karti hai — "
                    "tour ke dauran clear quote milegi."
                ),
            },
            "interactive": lead_interactive(
                [
                    {"id": "p_m", "title": "Monthly", "description": "1 month", "value": "Monthly"},
                    {"id": "p_q", "title": "Quarterly", "description": "3 months", "value": "Quarterly"},
                    {"id": "p_a", "title": "Annual", "description": "12 months", "value": "Annual"},
                    {"id": "p_pt", "title": "Personal Train", "description": "PT sessions", "value": "PT"},
                    {"id": "p_tr", "title": "Free Trial", "description": "Tour + trial", "value": "Trial"},
                    {"id": "p_coup", "title": "Couple", "description": "2 members", "value": "Couple"},
                    {"id": "p_stud", "title": "Student", "description": "Student plan", "value": "Student"},
                    {"id": "p_corp", "title": "Corporate", "description": "Office group", "value": "Corporate"},
                ],
                [
                    {"id": "b1", "title": "Main gym", "value": "Main"},
                    {"id": "b2", "title": "Ladies", "value": "Ladies"},
                    {"id": "b3", "title": "Branch 2", "value": "Branch2"},
                    {"id": "b4", "title": "24/7 branch", "value": "24/7"},
                ],
            ),
        },
    )
)

# ── 17. clinic_doctor (lead) ─────────────────────────────────────────────────
TEMPLATES.append(
    tmpl(
        "clinic_doctor",
        "Clinic / Doctor",
        "clinic",
        "lead",
        "Appointment only — no medical advice from the bot.",
        icon="stethoscope",
        greeting_ur=(
            "Assalam o Alaikum! Appointment book karne ke liye neeche se "
            "specialty choose karein. (Sirf booking — medical advice nahi)"
        ),
        greeting_en="Book an appointment — select a specialty. Booking only; no medical advice.",
        notes="CRITICAL: bot never answers health questions — only schedules.",
        facts="Booking only. No diagnosis or medical advice via WhatsApp bot.",
        demo_slots=["Kal 11am", "Kal 3pm"],
        campaign="Book Appointment",
        messages_overlay={
            "lead": {
                "greeting_line": (
                    "Assalam o Alaikum! Appointment book karne ke liye madad karte hain."
                ),
                "value_line": (
                    "Sirf scheduling — medical sawalon ka jawab yahan nahi. "
                    "Doctor se mil kar discuss karein."
                ),
                "q_business_name": "Patient ka naam?",
                "q_business_type": "Kaunsi specialty / service?",
                "q_locations": "Clinic location?",
                "q_current_system": "Pehle visit kiya tha?",
                "q_scheduling": "Appointment slot choose karein:",
                "info_text": (
                    "Yeh bot sirf appointment book karta hai. "
                    "Koi medical advice ya diagnosis yahan available nahi."
                ),
                "pricing_text": "Consultation fee clinic policy ke mutabiq — reception confirm karegi.",
            },
            "interactive": lead_interactive(
                [
                    {"id": "s_gp", "title": "General", "description": "GP", "value": "General"},
                    {"id": "s_den", "title": "Dental", "description": "Teeth", "value": "Dental"},
                    {"id": "s_skin", "title": "Skin", "description": "Dermatology", "value": "Skin"},
                    {"id": "s_child", "title": "Child", "description": "Pediatrics", "value": "Child"},
                    {"id": "s_gyn", "title": "Gyne", "description": "Women health", "value": "Gyne"},
                    {"id": "s_ent", "title": "ENT", "description": "Ear nose throat", "value": "ENT"},
                    {"id": "s_eye", "title": "Eye", "description": "Ophthalmology", "value": "Eye"},
                    {"id": "s_ortho", "title": "Ortho", "description": "Bones / joints", "value": "Ortho"},
                    {"id": "s_card", "title": "Cardio", "description": "Heart", "value": "Cardio"},
                    {"id": "s_oth", "title": "Other", "description": "Other", "value": "Other"},
                ],
            ),
        },
    )
)

# ── 18. auto_workshop (lead) ─────────────────────────────────────────────────
TEMPLATES.append(
    tmpl(
        "auto_workshop",
        "Auto Workshop",
        "auto",
        "lead",
        "Service booking — capture vehicle make/model then schedule.",
        icon="car",
        greeting_ur=(
            "Assalam o Alaikum! [Business] workshop — service book karein. "
            "Gaari ka make/model zaroor batayein."
        ),
        greeting_en="Book a service at [Business]. Please share your vehicle make/model.",
        notes="Vehicle make/model captured via business_name / free-text step.",
        demo_slots=["Kal 10am", "Kal 4pm"],
        messages_overlay={
            "lead": {
                "greeting_line": "Assalam o Alaikum! Workshop service book karein.",
                "value_line": "Service choose karein — make/model batayein.",
                "q_business_name": "Gaari ka make/model? (e.g. Honda City 2018)",
                "q_business_type": "Kaunsi service chahiye?",
                "q_locations": "Workshop branch?",
                "q_current_system": "Pehli baar aa rahe hain?",
                "q_scheduling": "Drop-off / visit slot choose karein:",
            },
            "interactive": lead_interactive(
                [
                    {"id": "s_oil", "title": "Oil change", "description": "Oil + filter", "value": "Oil"},
                    {"id": "s_dent", "title": "Denting/Paint", "description": "Body work", "value": "Dent"},
                    {"id": "s_ac", "title": "AC service", "description": "Cooling", "value": "AC"},
                    {"id": "s_gen", "title": "General check", "description": "Inspection", "value": "Check"},
                    {"id": "s_brake", "title": "Brakes", "description": "Brake service", "value": "Brakes"},
                    {"id": "s_tyre", "title": "Tyres", "description": "Tyre change", "value": "Tyres"},
                    {"id": "s_batt", "title": "Battery", "description": "Battery replace", "value": "Battery"},
                    {"id": "s_detail", "title": "Detailing", "description": "Wash + polish", "value": "Detailing"},
                    {"id": "s_oth", "title": "Other", "description": "Other job", "value": "Other"},
                ],
            ),
        },
    )
)

# ── 19. education_tuition (lead) ─────────────────────────────────────────────
TEMPLATES.append(
    tmpl(
        "education_tuition",
        "Education / Tuition",
        "education",
        "lead",
        "Courses list → inquiry + demo class; fee deflection like POS.",
        icon="graduation-cap",
        greeting_ur=(
            "Assalam o Alaikum! [Business] — course / demo class ke liye "
            "interest batayein. Fees/timings pooch sakte hain."
        ),
        greeting_en="Explore courses at [Business]. Ask about fees/timings or book a demo class.",
        demo_slots=["Kal 5pm", "Hafta 11am"],
        messages_overlay={
            "lead": {
                "greeting_line": "Assalam o Alaikum! Course ya demo class book karein.",
                "value_line": "Subject choose karein — timings/fees guide karenge.",
                "q_business_name": "Student ka naam?",
                "q_business_type": "Kaunsa course / class?",
                "q_locations": "Online ya campus?",
                "q_current_system": "Class / grade?",
                "q_scheduling": "Demo class ka slot choose karein:",
                "pricing_text": (
                    "Fees course aur duration pe depend karti hai — "
                    "sahi quote demo / counseling mein milti hai."
                ),
                "price_deflect_mid": (
                    "Fees short counseling ke baad clear hoti hai. {{current_question}}"
                ),
            },
            "interactive": lead_interactive(
                [
                    {"id": "c_math", "title": "Math", "description": "Mathematics", "value": "Math"},
                    {"id": "c_eng", "title": "English", "description": "Language", "value": "English"},
                    {"id": "c_sci", "title": "Science", "description": "Physics/Chem", "value": "Science"},
                    {"id": "c_comp", "title": "Computer", "description": "IT / coding", "value": "Computer"},
                    {"id": "c_entry", "title": "Entry test", "description": "ECAT/MDCAT", "value": "Entry"},
                    {"id": "c_acc", "title": "Accounts", "description": "Commerce", "value": "Accounts"},
                    {"id": "c_urdu", "title": "Urdu", "description": "Language", "value": "Urdu"},
                    {"id": "c_isl", "title": "Islamiyat", "description": "Islamic studies", "value": "Islamiyat"},
                    {"id": "c_css", "title": "CSS / PMS", "description": "Competitive", "value": "CSS"},
                    {"id": "c_oth", "title": "Other", "description": "Other", "value": "Other"},
                ],
                [
                    {"id": "m_on", "title": "Online", "value": "Online"},
                    {"id": "m_camp", "title": "Campus", "value": "Campus"},
                    {"id": "m_home", "title": "Home tutor", "value": "Home"},
                    {"id": "m_group", "title": "Group class", "value": "Group"},
                ],
            ),
        },
    )
)

# ── 20. real_estate (lead) ───────────────────────────────────────────────────
TEMPLATES.append(
    tmpl(
        "real_estate",
        "Real Estate",
        "real_estate",
        "lead",
        "Buy/Rent interest → area → budget → agent callback.",
        icon="home",
        greeting_ur=(
            "Assalam o Alaikum! Property interest share karein — "
            "hum agent callback schedule kar denge."
        ),
        greeting_en="Share your property interest — we'll schedule an agent callback.",
        campaign="Property Inquiry",
        demo_slots=["Aaj 5pm", "Kal 12pm"],
        facts="Lead capture: type, area, budget, then agent callback.",
        messages_overlay={
            "lead": {
                "greeting_line": "Assalam o Alaikum! Property interest note karte hain.",
                "value_line": "Type choose karein — area/budget ke baad agent call.",
                "q_business_name": "Aapka naam?",
                "q_business_type": "Buy/Rent aur property type?",
                "q_locations": "Kaunsa area / city?",
                "q_current_system": "Budget range (approx)?",
                "q_scheduling": "Agent callback ke liye slot choose karein:",
                "q_custom_slot": "Preferred callback time likhein.",
            },
            "interactive": lead_interactive(
                [
                    {"id": "t_bh", "title": "Buy House", "description": "Purchase home", "value": "Buy House"},
                    {"id": "t_bp", "title": "Buy Plot", "description": "Plot", "value": "Buy Plot"},
                    {"id": "t_bc", "title": "Buy Shop", "description": "Commercial", "value": "Buy Commercial"},
                    {"id": "t_bf", "title": "Buy Flat", "description": "Apartment", "value": "Buy Flat"},
                    {"id": "t_rh", "title": "Rent House", "description": "Rental home", "value": "Rent House"},
                    {"id": "t_rf", "title": "Rent Flat", "description": "Apartment rent", "value": "Rent Flat"},
                    {"id": "t_rc", "title": "Rent Shop", "description": "Commercial rent", "value": "Rent Commercial"},
                    {"id": "t_inv", "title": "Investment", "description": "ROI focus", "value": "Investment"},
                ],
                [
                    {"id": "a1", "title": "DHA / Bahria", "value": "DHA/Bahria"},
                    {"id": "a2", "title": "City center", "value": "Center"},
                    {"id": "a3", "title": "Gulberg", "value": "Gulberg"},
                    {"id": "a4", "title": "Other area", "value": "Other"},
                ],
                [
                    {"id": "b1", "title": "Under 1 Cr", "sheet_value": "<1Cr"},
                    {"id": "b2", "title": "1-3 Cr", "sheet_value": "1-3Cr"},
                    {"id": "b3", "title": "3-5 Cr", "sheet_value": "3-5Cr"},
                    {"id": "b4", "title": "5 Cr+", "sheet_value": "5Cr+"},
                ],
            ),
        },
    )
)

# ── 21. beauty_cosmetics ─────────────────────────────────────────────────────
shade = [
    {
        "id": "mod_shade",
        "name": "Shade",
        "options": [
            {"id": "sh_f", "label": "Fair", "price_delta": 0},
            {"id": "sh_m", "label": "Medium", "price_delta": 0},
            {"id": "sh_d", "label": "Deep", "price_delta": 0},
        ],
    }
]
TEMPLATES.append(
    tmpl(
        "beauty_cosmetics",
        "Beauty / Cosmetics",
        "beauty",
        "order",
        "Skincare, makeup, haircare, fragrances — shade modifiers.",
        icon="sparkles",
        greeting_ur="Assalam o Alaikum! [Business] beauty — products order karein.",
        greeting_en="Shop beauty at [Business] — skincare, makeup, and more.",
        menu_v2=menu(
            "Assalam o Alaikum! [Business] beauty — products order karein.",
            [
                cat("c_skin", "Skincare", 0),
                cat("c_make", "Makeup", 1),
                cat("c_hair", "Haircare", 2),
                cat("c_frag", "Fragrances", 3),
            ],
            [
                item("i_clean", "c_skin", "Face Cleanser", 1200, 0),
                item("i_moist", "c_skin", "Moisturizer", 1500, 1),
                item("i_sun", "c_skin", "Sunscreen SPF50", 1800, 2),
                item("i_toner", "c_skin", "Face Toner", 1100, 3),
                item("i_found", "c_make", "Foundation", 2500, 0, modifiers=shade),
                item("i_lip", "c_make", "Lipstick", 900, 1, modifiers=shade),
                item("i_mascara", "c_make", "Mascara", 1100, 2),
                item("i_blush", "c_make", "Blush", 1300, 3, modifiers=shade),
                item("i_shamp", "c_hair", "Shampoo", 850, 0),
                item("i_cond", "c_hair", "Conditioner", 850, 1),
                item("i_serum", "c_hair", "Hair Serum", 1400, 2),
                item("i_oil", "c_hair", "Hair Oil", 650, 3),
                item("i_attar", "c_frag", "Attar 12ml", 800, 0),
                item("i_edt", "c_frag", "Body Mist", 1200, 1),
                item("i_perfume", "c_frag", "Perfume 50ml", 4500, 2),
                item("i_deo", "c_frag", "Deodorant", 650, 3),
            ],
            charge=100,
            free_above=3000,
        ),
    )
)

# ── 22. flower_gifts ─────────────────────────────────────────────────────────
occasion = [
    {
        "id": "mod_occ",
        "name": "Occasion",
        "options": [
            {"id": "oc_b", "label": "Birthday", "price_delta": 0},
            {"id": "oc_a", "label": "Anniversary", "price_delta": 0},
            {"id": "oc_c", "label": "Condolence", "price_delta": 0},
        ],
    }
]
TEMPLATES.append(
    tmpl(
        "flower_gifts",
        "Flowers & Gifts",
        "gifts",
        "order",
        "Bouquets & baskets with occasion modifier + message card note.",
        icon="flower",
        greeting_ur=(
            "Assalam o Alaikum! [Business] — flowers/gifts order karein. "
            "Delivery date/time aur card message batayein."
        ),
        greeting_en="Order flowers & gifts from [Business]. Share delivery time and card message.",
        notes="Capture delivery date/time + message-card text in chat after order.",
        menu_v2=menu(
            "Assalam o Alaikum! Flowers/gifts. Delivery date/time + card message batayein.",
            [
                cat("c_bouq", "Bouquets", 0),
                cat("c_bask", "Gift Baskets", 1),
                cat("c_cake", "Cakes add-on", 2),
            ],
            [
                item("i_rose", "c_bouq", "Rose Bouquet", 2500, 0, modifiers=occasion),
                item("i_mix", "c_bouq", "Mixed Bouquet", 2200, 1, modifiers=occasion),
                item("i_orch", "c_bouq", "Orchid Special", 4500, 2, modifiers=occasion),
                item("i_sunf", "c_bouq", "Sunflower Bunch", 1800, 3, modifiers=occasion),
                item("i_choc", "c_bask", "Chocolate Basket", 3500, 0, modifiers=occasion),
                item("i_fruit", "c_bask", "Fruit Basket", 3000, 1, modifiers=occasion),
                item("i_combo", "c_bask", "Gift Combo", 5000, 2, modifiers=occasion),
                item("i_dry", "c_bask", "Dry Fruit Box", 4200, 3, modifiers=occasion),
                item("i_half", "c_cake", "Half kg Cake", 1800, 0),
                item("i_one", "c_cake", "1 Pound Cake", 2500, 1),
                item("i_cupg", "c_cake", "Cupcakes (6)", 1200, 2),
                item("i_brown", "c_cake", "Brownies (6)", 900, 3),
            ],
            charge=200,
            free_above=5000,
            area_note="Same-day if ordered before 2pm",
            confirm="Confirm? Delivery time + card message likhein.",
        ),
    )
)

# ── 23. shoe_store ───────────────────────────────────────────────────────────
shoe_size = size_mod([("40", "Size 40", 0), ("42", "Size 42", 0), ("44", "Size 44", 0)])
TEMPLATES.append(
    tmpl(
        "shoe_store",
        "Shoe Store",
        "shoes",
        "order",
        "Men/Women/Kids footwear + accessories — size modifier, ask for other sizes.",
        icon="footprints",
        greeting_ur=(
            "Assalam o Alaikum! [Business] — shoes dekhein aur order karein. "
            "Size choose karein; aur sizes chat mein pooch sakte hain."
        ),
        greeting_en=(
            "Welcome to [Business]! Browse shoes below. Pick a size — "
            "ask in chat for other sizes."
        ),
        facts="Common sizes on buttons; other sizes confirmed in chat before delivery.",
        notes="Modifier shows 40/42/44 — customer can request other sizes in chat.",
        menu_v2=menu(
            "Assalam o Alaikum! [Business] shoes — size choose karein. Aur sizes chat mein pooch sakte hain.",
            [
                cat("c_men", "Men", 0),
                cat("c_wom", "Women", 1),
                cat("c_kid", "Kids", 2),
                cat("c_acc", "Accessories", 3),
            ],
            [
                item("i_sneak", "c_men", "Sneakers", 4500, 0, modifiers=shoe_size),
                item("i_formal", "c_men", "Formal Shoes", 5500, 1, modifiers=shoe_size),
                item("i_loaf", "c_men", "Loafers", 4800, 2, modifiers=shoe_size),
                item("i_sandal", "c_men", "Sandals", 2200, 3, modifiers=shoe_size),
                item("i_heels", "c_wom", "Heels", 4200, 0, modifiers=shoe_size),
                item("i_flats", "c_wom", "Flat Sandals", 2800, 1, modifiers=shoe_size),
                item("i_wsneak", "c_wom", "Women Sneakers", 4000, 2, modifiers=shoe_size),
                item("i_khussa", "c_wom", "Khussa / Jutti", 2500, 3, modifiers=shoe_size),
                item("i_ksneak", "c_kid", "Kids Sneakers", 2200, 0, modifiers=shoe_size),
                item("i_kschool", "c_kid", "School Shoes", 2800, 1, modifiers=shoe_size),
                item("i_ksand", "c_kid", "Kids Sandals", 1500, 2, modifiers=shoe_size),
                item("i_kboot", "c_kid", "Kids Boots", 3200, 3, modifiers=shoe_size),
                item("i_socks", "c_acc", "Socks (3-pack)", 450, 0),
                item("i_lace", "c_acc", "Shoe Laces", 150, 1),
                item("i_polish", "c_acc", "Shoe Polish", 280, 2),
                item("i_insole", "c_acc", "Insoles", 600, 3),
            ],
            charge=150,
            free_above=5000,
            area_note="City delivery — confirm size before dispatch",
            confirm="Confirm? Size theek hai? Aur size chahiye to likhein.",
        ),
    )
)

# ── 24. general_store ────────────────────────────────────────────────────────
TEMPLATES.append(
    tmpl(
        "general_store",
        "General Store",
        "general_store",
        "order",
        "Variety shop — snacks, household, personal care, stationery.",
        icon="store",
        greeting_ur=(
            "Assalam o Alaikum! [Business] general store — zarooriyat order karein. "
            "Menu neeche hai."
        ),
        greeting_en="Welcome to [Business] general store — browse and order below.",
        menu_v2=menu(
            "Assalam o Alaikum! [Business] general store — zarooriyat order karein.",
            [
                cat("c_snack", "Snacks", 0),
                cat("c_house", "Household", 1),
                cat("c_pcare", "Personal Care", 2),
                cat("c_stat", "Stationery", 3),
            ],
            [
                item("i_chips", "c_snack", "Chips Pack", 80, 0),
                item("i_biscuits", "c_snack", "Biscuits Pack", 120, 1),
                item("i_choc", "c_snack", "Chocolate Bar", 150, 2),
                item("i_nuts", "c_snack", "Mixed Nuts 250g", 450, 3),
                item("i_det", "c_house", "Detergent 1kg", 450, 0),
                item("i_tissue", "c_house", "Tissue Pack", 180, 1),
                item("i_bag", "c_house", "Garbage Bags", 220, 2),
                item("i_match", "c_house", "Match Box Pack", 60, 3),
                item("i_soap", "c_pcare", "Bath Soap", 120, 0),
                item("i_tooth", "c_pcare", "Toothpaste", 220, 1),
                item("i_shamp", "c_pcare", "Shampoo Sachet", 40, 2),
                item("i_cream", "c_pcare", "Face Cream", 350, 3),
                item("i_pen", "c_stat", "Pen Pack (10)", 200, 0),
                item("i_note", "c_stat", "Notebook", 150, 1),
                item("i_glue", "c_stat", "Glue Stick", 80, 2),
                item("i_tape", "c_stat", "Scotch Tape", 60, 3),
            ],
            charge=50,
            free_above=1500,
            area_note="Local delivery",
        ),
    )
)


def main() -> None:
    ids = []
    for t in TEMPLATES:
        path = OUT / f"{t['id']}.json"
        # Preserve hierarchical menu_v2 already on disk (category → sub-category trees)
        if path.exists():
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
                emv = (existing.get("config") or {}).get("menu_v2")
                if emv and any(c.get("parent_id") for c in (emv.get("categories") or [])):
                    t.setdefault("config", {})["menu_v2"] = emv
            except (OSError, json.JSONDecodeError):
                pass
        # Validate title lengths for menu items
        mv = (t.get("config") or {}).get("menu_v2")
        if mv:
            for it in mv.get("items") or []:
                assert len(it["name"]) <= 24, f"{t['id']}: {it['name']}"
                for mod in it.get("modifiers") or []:
                    for opt in mod.get("options") or []:
                        assert len(opt["label"]) <= 20, opt["label"]
            for c in mv.get("categories") or []:
                assert len(c["name"]) <= 24, c["name"]
            # Max ~10 items shown per list page — warn if category has >10
            from collections import Counter

            counts = Counter(i["category_id"] for i in mv["items"])
            for cid, n in counts.items():
                assert n <= 10, f"{t['id']} category {cid} has {n} items"
            roots = [c for c in mv.get("categories") or [] if not c.get("parent_id")]
            assert roots, f"{t['id']} needs root categories"
            for c in mv.get("categories") or []:
                kids = [x for x in mv["categories"] if x.get("parent_id") == c["id"]]
                if kids:
                    assert len(kids) >= 1
                    for k in kids:
                        n = counts.get(k["id"], 0)
                        assert n >= 4, f"{t['id']} sub {k['name']} has only {n}"
                else:
                    n = counts.get(c["id"], 0)
                    # leaf root allowed only if no parent — still need >=4 items
                    if not c.get("parent_id"):
                        # if this root has no kids, it must have items OR be transitional
                        pass
                    else:
                        assert n >= 4, f"{t['id']} leaf {c['name']} has only {n}"
            # Every root must have at least one sub-category
            for r in roots:
                kids = [x for x in mv["categories"] if x.get("parent_id") == r["id"]]
                assert kids, f"{t['id']} root {r['name']} needs sub-categories"

        path.write_text(json.dumps(t, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        ids.append(t["id"])
        print(f"wrote {path.name}")

    print(f"total={len(ids)}")
    expected = {
        "restaurant",
        "grocery_kiryana",
        "water_supplier",
        "pharmacy",
        "bakery",
        "clothing_retail",
        "salon_booking",
        "pos_lead",
        "generic_order",
        "generic_lead",
        "hardware_store",
        "mobile_accessories",
        "electronics_appliances",
        "meat_poultry",
        "fruits_vegetables",
        "dairy_milk",
        "gym_fitness",
        "clinic_doctor",
        "auto_workshop",
        "education_tuition",
        "real_estate",
        "beauty_cosmetics",
        "flower_gifts",
        "shoe_store",
        "general_store",
    }
    assert set(ids) == expected, set(ids) ^ expected


if __name__ == "__main__":
    main()
