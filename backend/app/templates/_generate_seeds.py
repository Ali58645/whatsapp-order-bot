#!/usr/bin/env python3
"""One-shot generator for vertical starter templates under app/templates/."""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent

# Keep titles <= 24, option labels <= 20, <=6 items/cat, modifiers <=3 opts


def cat(cid: str, name: str, sort: int) -> dict:
    assert len(name) <= 24, name
    return {"id": cid, "name": name, "sort": sort, "visible": True}


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
                item("i_milk", "c_dairy", "Milk Pack 1L", 280, 0),
                item("i_eggs", "c_dairy", "Eggs (Dozen)", 420, 1),
                item("i_yogurt", "c_dairy", "Yogurt 1kg", 350, 2),
                item("i_butter", "c_dairy", "Butter 200g", 380, 3),
                item("i_tea", "c_bev", "Tea Whitener", 250, 0),
                item("i_juice", "c_bev", "Juice 1L", 220, 1),
                item("i_cola", "c_bev", "Soft Drink 1.5L", 180, 2),
                item("i_det", "c_house", "Detergent 1kg", 450, 0),
                item("i_soap", "c_house", "Bath Soap", 120, 1),
                item("i_tissue", "c_house", "Tissue Pack", 180, 2),
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
            [cat("c_water", "Water Orders", 0)],
            [
                item("i_19new", "c_water", "19L Bottle (new)", 350, 0, "With bottle"),
                item("i_19ref", "c_water", "19L Refill", 150, 1, "Empty exchange"),
                item("i_pack6", "c_water", "6-Bottle Pack", 800, 2, "Small bottles"),
                item("i_disp", "c_water", "Dispenser", 4500, 3, "Purchase"),
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
                item("i_shamp", "c_pc", "Shampoo 200ml", 450, 0),
                item("i_tooth", "c_pc", "Toothpaste", 220, 1),
                item("i_san", "c_pc", "Hand Sanitizer", 180, 2),
                item("i_diaper", "c_baby", "Diapers M (pack)", 1200, 0),
                item("i_wipes", "c_baby", "Baby Wipes", 350, 1),
                item("i_feed", "c_baby", "Feeding Bottle", 650, 2),
                item("i_vitc", "c_supp", "Vitamin C", 400, 0),
                item("i_multi", "c_supp", "Multivitamin", 850, 1),
                item("i_omega", "c_supp", "Omega-3", 1100, 2),
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
                item("i_patties", "c_sav", "Chicken Patty", 120, 0),
                item("i_roll", "c_sav", "Chicken Roll", 200, 1),
                item("i_samosa_b", "c_sav", "Aloo Samosa", 60, 2),
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
                item("i_lawn", "c_wom", "Lawn Suit", 4500, 0, modifiers=size),
                item("i_abaya", "c_wom", "Abaya", 3200, 1, modifiers=size),
                item("i_dupatta", "c_wom", "Dupatta", 900, 2),
                item("i_kidset", "c_kid", "Kids Suit", 1800, 0, modifiers=size),
                item("i_kidt", "c_kid", "Kids T-Shirt", 650, 1, modifiers=size),
                item("i_cotton", "c_fab", "Cotton (meter)", 450, 0),
                item("i_lawnf", "c_fab", "Lawn (meter)", 380, 1),
                item("i_silk", "c_fab", "Silk (meter)", 1200, 2),
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
                    {"id": "svc_col", "title": "Hair Color", "description": "Coloring", "value": "Color"},
                    {"id": "svc_oth", "title": "Other", "description": "Something else", "value": "Other"},
                ],
                [
                    {"id": "loc_main", "title": "Main branch", "value": "Main"},
                    {"id": "loc_mall", "title": "Mall outlet", "value": "Mall"},
                    {"id": "loc_home", "title": "Home service", "value": "Home"},
                ],
                [
                    {"id": "vis_new", "title": "Pehli baar", "sheet_value": "New"},
                    {"id": "vis_ret", "title": "Wapas aa rahe", "sheet_value": "Returning"},
                    {"id": "vis_ref", "title": "Referral", "sheet_value": "Referral"},
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
            }
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
            [cat("c_items", "Items", 0)],
            [
                item("i_a", "c_items", "Item A", 100, 0, "Edit in Settings"),
                item("i_b", "c_items", "Item B", 200, 1),
                item("i_c", "c_items", "Item C", 300, 2),
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
                item("i_pipe", "c_plumb", "PVC Pipe 1in", 180, 0, "Per length"),
                item("i_tap", "c_plumb", "Basin Mixer", 2200, 1),
                item("i_elbow", "c_plumb", "Elbow Joint", 60, 2),
                item("i_switch", "c_elec", "Switch Board", 450, 0),
                item("i_wire", "c_elec", "Wire 1.5mm (coil)", 2800, 1),
                item("i_bulb", "c_elec", "LED Bulb 12W", 350, 2),
                item("i_screw2", "c_fast", "Screw Pack", 150, 0),
                item("i_nail", "c_fast", "Nail Pack", 120, 1),
                item("i_nut", "c_fast", "Nut Bolt Assort", 200, 2),
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
                item("i_cover", "c_cov", "Silicon Cover", 400, 0),
                item("i_glass", "c_cov", "Tempered Glass", 350, 1),
                item("i_wallet", "c_cov", "Wallet Case", 900, 2),
                item("i_buds", "c_aud", "Wireless Earbuds", 2500, 0),
                item("i_bt", "c_aud", "BT Speaker Mini", 1800, 1),
                item("i_pb10", "c_pb", "Power Bank 10k", 2200, 0),
                item("i_pb20", "c_pb", "Power Bank 20k", 3500, 1),
                item("i_scr", "c_rep", "Screen Repair", 1, 0, "Quote after model"),
                item("i_bat", "c_rep", "Battery Replace", 1, 1, "Quote after model"),
                item("i_diag", "c_rep", "Diagnosis", 500, 2),
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
                item("i_micro", "c_kit", "Microwave", 22000, 0),
                item("i_blend", "c_kit", "Blender", 6500, 1),
                item("i_kettle", "c_kit", "Electric Kettle", 4200, 2),
                item("i_fan", "c_fan", "Pedestal Fan", 8500, 0),
                item("i_ac", "c_fan", "AC 1.5 Ton", 145000, 1, "Inverter"),
                item("i_cooler", "c_fan", "Room Cooler", 18000, 2),
                item("i_trim", "c_sm", "Trimmer", 2800, 0),
                item("i_scale", "c_sm", "Kitchen Scale", 1500, 1),
                item("i_ext", "c_sm", "Extension Board", 900, 2),
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
                item("i_mutkg", "c_mut", "Mutton (per kg)", 2200, 0),
                item("i_mutk", "c_mut", "Mutton Karahi Cut", 2300, 1),
                item("i_beefkg", "c_beef", "Beef (per kg)", 1600, 0),
                item("i_keema", "c_beef", "Beef Keema (kg)", 1700, 1),
                item("i_fishkg", "c_fish", "Rohu (per kg)", 900, 0),
                item("i_prawn", "c_fish", "Prawns (kg)", 1800, 1),
                item("i_qorma", "c_cut", "Qorma Cut (kg)", 600, 0),
                item("i_boticut", "c_cut", "Boti Cut (kg)", 650, 1),
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
            [cat("c_dairy", "Dairy", 0)],
            [
                item("i_milk1", "c_dairy", "Fresh Milk 1L", 220, 0),
                item("i_milk2", "c_dairy", "Fresh Milk 2L", 420, 1),
                item("i_yog", "c_dairy", "Yogurt 1kg", 300, 2),
                item("i_but", "c_dairy", "Butter 200g", 380, 3),
                item("i_ghee", "c_dairy", "Desi Ghee 1kg", 2200, 4),
                item("i_cream", "c_dairy", "Fresh Cream", 250, 5),
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
                ],
                [
                    {"id": "b1", "title": "Main gym", "value": "Main"},
                    {"id": "b2", "title": "Ladies", "value": "Ladies"},
                    {"id": "b3", "title": "Branch 2", "value": "Branch2"},
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
                    {"id": "c_oth", "title": "Other", "description": "Other", "value": "Other"},
                ],
                [
                    {"id": "m_on", "title": "Online", "value": "Online"},
                    {"id": "m_camp", "title": "Campus", "value": "Campus"},
                    {"id": "m_home", "title": "Home tutor", "value": "Home"},
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
                    {"id": "t_rh", "title": "Rent House", "description": "Rental home", "value": "Rent House"},
                    {"id": "t_rc", "title": "Rent Shop", "description": "Commercial rent", "value": "Rent Commercial"},
                ],
                [
                    {"id": "a1", "title": "DHA / Bahria", "value": "DHA/Bahria"},
                    {"id": "a2", "title": "City center", "value": "Center"},
                    {"id": "a3", "title": "Other area", "value": "Other"},
                ],
                [
                    {"id": "b1", "title": "Under 1 Cr", "sheet_value": "<1Cr"},
                    {"id": "b2", "title": "1-3 Cr", "sheet_value": "1-3Cr"},
                    {"id": "b3", "title": "3 Cr+", "sheet_value": "3Cr+"},
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
                item("i_found", "c_make", "Foundation", 2500, 0, modifiers=shade),
                item("i_lip", "c_make", "Lipstick", 900, 1, modifiers=shade),
                item("i_mascara", "c_make", "Mascara", 1100, 2),
                item("i_shamp", "c_hair", "Shampoo", 850, 0),
                item("i_cond", "c_hair", "Conditioner", 850, 1),
                item("i_serum", "c_hair", "Hair Serum", 1400, 2),
                item("i_attar", "c_frag", "Attar 12ml", 800, 0),
                item("i_edt", "c_frag", "Body Mist", 1200, 1),
                item("i_perfume", "c_frag", "Perfume 50ml", 4500, 2),
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
                item("i_choc", "c_bask", "Chocolate Basket", 3500, 0, modifiers=occasion),
                item("i_fruit", "c_bask", "Fruit Basket", 3000, 1, modifiers=occasion),
                item("i_combo", "c_bask", "Gift Combo", 5000, 2, modifiers=occasion),
                item("i_half", "c_cake", "Half kg Cake", 1800, 0),
                item("i_one", "c_cake", "1 Pound Cake", 2500, 1),
                item("i_cupg", "c_cake", "Cupcakes (6)", 1200, 2),
            ],
            charge=200,
            free_above=5000,
            area_note="Same-day if ordered before 2pm",
            confirm="Confirm? Delivery time + card message likhein.",
        ),
    )
)


def main() -> None:
    ids = []
    for t in TEMPLATES:
        path = OUT / f"{t['id']}.json"
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
    }
    assert set(ids) == expected, set(ids) ^ expected


if __name__ == "__main__":
    main()
