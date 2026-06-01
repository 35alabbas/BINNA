#!/usr/bin/env python3
"""
Seed financial & gantt data for APS project (ID=3).
Run: python seed_financial.py
"""
import json, sys, os
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import create_app, db
from app.models import FinancialData, GanttData, Project

app = create_app('development')

TODAY = date.today()
def ds(offset):
    return (TODAY + timedelta(days=offset)).isoformat()


# ── Financial data ─────────────────────────────────────────────────────────────

FINANCIAL_DATA = {
    "contractDetails": {
        "contractor": "شركة الرشيد للإنشاءات",
        "client": "وزارة الموارد المائية",
        "project": "محطة الضخ المساعدة - المرحلة الثانية",
        "contract-no": "MWR-2025-APS-047",
        "date": ds(-272),
        "period": "18",
        "type": "عقد حكومي - معدلات وكميات",
        "insurance": "5",
        "tax": "3",
        "contract-end": ds(274),
        "penalty-rate": "0.1",
        "rules": "الشروط العامة لعقود المقاولات الحكومية العراقية. الغرامات محدودة بنسبة 10% من قيمة العقد الإجمالية."
    },
    "usdRate": 1310,

    # ── BOQ items (flat list, indices 0–14) ────────────────────────────────────
    "boq": [
        # 0
        {"desc": "تهيئة وتسوية الموقع ورفع النباتات وإزالة المنشآت القائمة وتكسير الأرضيات وفق توجيهات المهندس المشرف",
         "unit": "جملة", "qty": "1", "price": "20000000"},
        # 1
        {"desc": "الحفريات لأسس محطة الضخ والممرات الخارجية حسب الأبعاد المؤشرة في المخططات",
         "unit": "م3", "qty": "2450", "price": "20000"},
        # 2
        {"desc": "فرش طبقة من الزلط نوع B تحت الأسس سمك 20سم مع الحدل الجيد حتى 95% من كثافة بروكتور",
         "unit": "م3", "qty": "600", "price": "40000"},
        # 3
        {"desc": "صب خرسانة تعمية نظيفة 4:2:1 تحت الأسس سمك 10سم باستخدام السمنت المقاوم للأملاح",
         "unit": "م2", "qty": "1175", "price": "30000"},
        # 4
        {"desc": "صب خرسانة مسلحة بقابلية تحمل 35MPa للأسس والقواعد شاملاً التسليح والقوالب والعمالة",
         "unit": "م3", "qty": "840", "price": "550000"},
        # 5
        {"desc": "صب خرسانة مسلحة 30MPa للأعمدة الإنشائية شاملاً جميع الملحقات والعمالة",
         "unit": "م3", "qty": "250", "price": "750000"},
        # 6
        {"desc": "صب خرسانة مسلحة 30MPa للجدران الكونكريتية وجدران غرفة المضخات",
         "unit": "م3", "qty": "90", "price": "750000"},
        # 7
        {"desc": "صب خرسانة مسلحة 30MPa للسقوف والجسور والمردات الخرسانية",
         "unit": "م3", "qty": "1170", "price": "500000"},
        # 8
        {"desc": "أعمال البناء بالطابوق نوع B سمك 20سم للجدران الخارجية والداخلية شاملاً اللبخ والمونة",
         "unit": "م2", "qty": "1400", "price": "80000"},
        # 9
        {"desc": "تغليف الأرضيات بالكرانيت الهندي مقاس 60×60سم شاملاً المونة والتنظيف والتلميع",
         "unit": "م2", "qty": "1175", "price": "65000"},
        # 10
        {"desc": "تجهيز وتركيب طرمبات مركزية KSB Etanorm 125-250 مع المحركات والقواعد الفولاذية وجميع الملحقات",
         "unit": "عدد", "qty": "4", "price": "45000000"},
        # 11
        {"desc": "تجهيز ومد وتركيب أنابيب فولاذية مسربلة DN200/DN250 شاملاً الوصلات والحاملات والفلنجات",
         "unit": "م طول", "qty": "720", "price": "150000"},
        # 12
        {"desc": "تجهيز وتركيب اللوحات الكهربائية الرئيسية MDB وMCC ولوحات التوزيع الفرعية وفق المخططات",
         "unit": "جملة", "qty": "1", "price": "85000000"},
        # 13
        {"desc": "تجهيز وتركيب مولدة كهرباء ديزل منشأ غربي PRIME 1000KVA شاملاً قاطع دوري ATS وخزان وقود",
         "unit": "عدد", "qty": "1", "price": "194000000"},
        # 14
        {"desc": "تجهيز وتركيب محطة تحويل كهربائي ثانوية 11kV/0.4kV مع كافة المعدات والتوصيلات والفحوصات",
         "unit": "سيت", "qty": "1", "price": "55000000"},
    ],

    # ── Variation Orders ───────────────────────────────────────────────────────
    "vo": [
        {"vono": "VO-001",
         "desc": "نقاط قياس ضغط وتدفق إضافية لنظام SCADA (8 نقاط) حسب طلب تغيير رقم TC-003",
         "unit": "جملة", "qty": "1", "price": "12000000", "type": "add"},
        {"vono": "VO-002",
         "desc": "أعمال تصريف خارجية إضافية — وصلة الصرف الصحي للشبكة الخارجية",
         "unit": "جملة", "qty": "1", "price": "8500000", "type": "add"},
    ],

    # ── Payment Certificates (درعات) ──────────────────────────────────────────
    "payments": [

        # ── درعة 1 — Early civil (approved) ────────────────────────────────
        # Cumulative certified at end of درعة 1:
        #   Site prep 100%, Excavation 100%, Sub-base 80%, Blinding 50%, RC Found. 40%
        {
            "id": "pay_aps_001",
            "desc": "الدرعة الأولى — الأعمال الإنشائية المبكرة (التهيئة والحفريات والأسس)",
            "date": ds(-196),
            "status": "approved",
            "taxRate": "3",
            "penaltyDays": 0,
            "penaltyWaived": 0,
            "penaltyWaivedNote": "",
            "releaseInitial": False,
            "releaseFinal": False,
            "colVis": {},
            "surplusCredits": [],
            "deductionReversals": [],
            "extraDeductions": [
                {"label": "استرداد الدفعة المقدمة (10%)", "type": "pct", "value": "10", "reversals": []}
            ],
            "boqItems": [
                {"id": "boq0",  "qty": "1",    "engQty": "1",    "within20": "", "over20": "", "newPrice": "", "notes": ""},
                {"id": "boq1",  "qty": "2450", "engQty": "2450", "within20": "", "over20": "", "newPrice": "", "notes": ""},
                {"id": "boq2",  "qty": "480",  "engQty": "480",  "within20": "", "over20": "", "newPrice": "", "notes": ""},
                {"id": "boq3",  "qty": "587",  "engQty": "587",  "within20": "", "over20": "", "newPrice": "", "notes": ""},
                {"id": "boq4",  "qty": "336",  "engQty": "336",  "within20": "", "over20": "", "newPrice": "", "notes": ""},
            ]
        },

        # ── درعة 2 — Mid civil + mech (approved, 3 penalty days) ───────────
        # Cumulative certified at end of درعة 2:
        #   Civil items fully certified, columns 72%, walls 67%, block work 50%,
        #   2 of 4 pumps installed, 50% of pipework
        {
            "id": "pay_aps_002",
            "desc": "الدرعة الثانية — إكمال الأعمال الإنشائية والأعمال الميكانيكية الأولية",
            "date": ds(-91),
            "status": "approved",
            "taxRate": "3",
            "penaltyDays": 3,
            "penaltyWaived": 0,
            "penaltyWaivedNote": "",
            "releaseInitial": False,
            "releaseFinal": False,
            "colVis": {},
            "surplusCredits": [],
            "deductionReversals": [],
            "extraDeductions": [
                {"label": "استرداد الدفعة المقدمة (10%)", "type": "pct", "value": "10", "reversals": []},
                {"label": "خصم تكاليف الفحوصات المختبرية وفق البند (12) من الاتفاقية", "type": "fixed", "value": "2500000", "reversals": []}
            ],
            "boqItems": [
                {"id": "boq0",  "qty": "1",    "engQty": "1",    "within20": "", "over20": "", "newPrice": "", "notes": ""},
                {"id": "boq1",  "qty": "2450", "engQty": "2450", "within20": "", "over20": "", "newPrice": "", "notes": ""},
                {"id": "boq2",  "qty": "600",  "engQty": "600",  "within20": "", "over20": "", "newPrice": "", "notes": ""},
                {"id": "boq3",  "qty": "1175", "engQty": "1175", "within20": "", "over20": "", "newPrice": "", "notes": ""},
                {"id": "boq4",  "qty": "840",  "engQty": "840",  "within20": "", "over20": "", "newPrice": "", "notes": ""},
                {"id": "boq5",  "qty": "180",  "engQty": "180",  "within20": "", "over20": "", "newPrice": "", "notes": ""},
                {"id": "boq6",  "qty": "60",   "engQty": "60",   "within20": "", "over20": "", "newPrice": "", "notes": ""},
                {"id": "boq8",  "qty": "700",  "engQty": "700",  "within20": "", "over20": "", "newPrice": "", "notes": ""},
                {"id": "boq10", "qty": "2",    "engQty": "2",    "within20": "", "over20": "", "newPrice": "", "notes": ""},
                {"id": "boq11", "qty": "360",  "engQty": "360",  "within20": "", "over20": "", "newPrice": "", "notes": ""},
            ]
        },

        # ── درعة 3 — Advanced works (submitted, includes reversal) ──────────
        # Cumulative certified at end of درعة 3:
        #   All civil 100%, roof slabs 70%, floor 70%, block work 100%,
        #   3/4 pumps, 75% pipework, 50% electrical boards, generator 100%, substation 0%
        # Also includes: 50% reversal of درعة 2 lab deduction (sourcePayIdx=1, sourceEdIdx=1)
        {
            "id": "pay_aps_003",
            "desc": "الدرعة الثالثة — الأعمال الإنشائية المتقدمة والكهربائية والتجهيز",
            "date": ds(-7),
            "status": "submitted",
            "taxRate": "3",
            "penaltyDays": 0,
            "penaltyWaived": 0,
            "penaltyWaivedNote": "",
            "releaseInitial": False,
            "releaseFinal": False,
            "colVis": {},
            "surplusCredits": [],
            "deductionReversals": [
                {
                    "sourcePayIdx": 1,
                    "sourceEdIdx": 1,
                    "type": "pct",
                    "value": "50",
                    "amount": 1250000,
                    "note": "إعادة 50% من خصم الفحوصات المختبرية المستقطع في الدرعة الثانية"
                }
            ],
            "extraDeductions": [
                {"label": "استرداد الدفعة المقدمة (10%)", "type": "pct", "value": "10", "reversals": []}
            ],
            "boqItems": [
                {"id": "boq0",  "qty": "1",    "engQty": "1",    "within20": "", "over20": "", "newPrice": "", "notes": ""},
                {"id": "boq1",  "qty": "2450", "engQty": "2450", "within20": "", "over20": "", "newPrice": "", "notes": ""},
                {"id": "boq2",  "qty": "600",  "engQty": "600",  "within20": "", "over20": "", "newPrice": "", "notes": ""},
                {"id": "boq3",  "qty": "1175", "engQty": "1175", "within20": "", "over20": "", "newPrice": "", "notes": ""},
                {"id": "boq4",  "qty": "840",  "engQty": "840",  "within20": "", "over20": "", "newPrice": "", "notes": ""},
                {"id": "boq5",  "qty": "250",  "engQty": "250",  "within20": "", "over20": "", "newPrice": "", "notes": ""},
                {"id": "boq6",  "qty": "90",   "engQty": "90",   "within20": "", "over20": "", "newPrice": "", "notes": ""},
                {"id": "boq7",  "qty": "870",  "engQty": "820",  "within20": "", "over20": "", "newPrice": "", "notes": ""},
                {"id": "boq8",  "qty": "1400", "engQty": "1400", "within20": "", "over20": "", "newPrice": "", "notes": ""},
                {"id": "boq9",  "qty": "900",  "engQty": "820",  "within20": "", "over20": "", "newPrice": "", "notes": ""},
                {"id": "boq10", "qty": "3",    "engQty": "3",    "within20": "", "over20": "", "newPrice": "", "notes": ""},
                {"id": "boq11", "qty": "560",  "engQty": "540",  "within20": "", "over20": "", "newPrice": "", "notes": ""},
                {"id": "boq12", "qty": "1",    "engQty": "0.5",  "within20": "", "over20": "", "newPrice": "", "notes": ""},
                {"id": "boq13", "qty": "1",    "engQty": "1",    "within20": "", "over20": "", "newPrice": "", "notes": ""},
            ]
        },
    ],

    # ── Income records ─────────────────────────────────────────────────────────
    "income": [
        {"desc": "استلام الدفعة المقدمة — وزارة الموارد المائية", "date": ds(-265), "cur": "IQD", "amount": "224062500", "rate": ""},
        {"desc": "استلام قيمة الدرعة الأولى (صافي بعد الخصومات)", "date": ds(-175), "cur": "IQD", "amount": "238000000", "rate": ""},
        {"desc": "استلام قيمة الدرعة الثانية (صافي بعد الخصومات)", "date": ds(-55),  "cur": "IQD", "amount": "740000000", "rate": ""},
    ],

    # ── Expense categories ─────────────────────────────────────────────────────
    "expenseCategories": [
        {
            "id": "cat1", "name": "اليد العاملة",
            "rows": [
                {"desc": "رواتب ومكافآت المهندسين (9 أشهر)",    "date": ds(-180), "cur": "IQD", "amount": "135000000", "rate": ""},
                {"desc": "أجور عمال البناء والفنيين (6 أشهر)",  "date": ds(-90),  "cur": "IQD", "amount": "72000000",  "rate": ""},
                {"desc": "إشراف ومتابعة الموقع — مهندس مقيم",   "date": ds(-45),  "cur": "IQD", "amount": "18000000",  "rate": ""},
            ]
        },
        {
            "id": "cat2", "name": "المواد",
            "rows": [
                {"desc": "خرسانة جاهزة 35MPa — توريد أول (أسس)", "date": ds(-245), "cur": "IQD", "amount": "185000000", "rate": ""},
                {"desc": "حديد تسليح B500B Ø8-Ø32 — دفعة أولى", "date": ds(-230), "cur": "IQD", "amount": "78000000",  "rate": ""},
                {"desc": "خرسانة جاهزة 30MPa — توريد ثاني (هيكل)", "date": ds(-150), "cur": "IQD", "amount": "210000000", "rate": ""},
                {"desc": "طابوق نوع B + مونة بناء",               "date": ds(-120), "cur": "IQD", "amount": "42000000",  "rate": ""},
                {"desc": "أنابيب فولاذية DN200/DN250 — دفعة أولى", "date": ds(-80),  "cur": "IQD", "amount": "56000000",  "rate": ""},
            ]
        },
        {
            "id": "cat3", "name": "المعدات",
            "rows": [
                {"desc": "إيجار حفار CAT 320 (4 أشهر)",      "date": ds(-265), "cur": "IQD", "amount": "56000000", "rate": ""},
                {"desc": "إيجار رافعة 25 طن (3 أشهر)",       "date": ds(-180), "cur": "IQD", "amount": "27000000", "rate": ""},
                {"desc": "إيجار خلاطة خرسانة + بمبة (شهرين)", "date": ds(-150), "cur": "IQD", "amount": "14000000", "rate": ""},
            ]
        },
        {
            "id": "cat4", "name": "أخرى",
            "rows": [
                {"desc": "تأمينات الموقع والتصاريح الرسمية",    "date": ds(-270), "cur": "IQD", "amount": "9500000",  "rate": ""},
                {"desc": "الفحوصات المختبرية — خرسانة وحديد",   "date": ds(-200), "cur": "IQD", "amount": "6800000",  "rate": ""},
                {"desc": "استئجار الموقع المؤقت (كراج + مستودع)", "date": ds(-270), "cur": "IQD", "amount": "12000000", "rate": ""},
                {"desc": "نفقات السلامة والصحة المهنية",         "date": ds(-150), "cur": "IQD", "amount": "4200000",  "rate": ""},
            ]
        }
    ]
}


# ── Gantt data ─────────────────────────────────────────────────────────────────

def p(*ids): return [{"id": i, "lag": 0} for i in ids]

GANTT_TASKS = [
    # ── 1. Pre-Construction (group, level 0) ─────────────────────────────────
    {"id":"g1",  "type":"group", "level":0, "color":"#1a56db",
     "name":"Pre-Construction",
     "start":ds(-285), "end":ds(-258), "pct":100, "preds":[], "person":"", "notes":""},
    {"id":"t1",  "type":"task",  "level":1, "color":"#1a56db",
     "name":"Site Mobilisation & Temporary Works",
     "start":ds(-285), "end":ds(-272), "pct":100, "preds":[], "person":"Site Manager", "notes":""},
    {"id":"t2",  "type":"task",  "level":1, "color":"#1a56db",
     "name":"Setting Out & Survey Control",
     "start":ds(-275), "end":ds(-258), "pct":100, "preds":p("t1"), "person":"Survey Team", "notes":""},

    # ── 2. Civil — Substructure (group, level 0) ─────────────────────────────
    {"id":"g2",  "type":"group", "level":0, "color":"#027a48",
     "name":"Civil — Substructure",
     "start":ds(-272), "end":ds(-140), "pct":100, "preds":p("t2"), "person":"", "notes":""},
    {"id":"t3",  "type":"task",  "level":1, "color":"#027a48",
     "name":"Bulk Excavation (2,450 m³)",
     "start":ds(-272), "end":ds(-245), "pct":100, "preds":p("t2"), "person":"Civil Team", "notes":""},
    {"id":"t4",  "type":"task",  "level":1, "color":"#027a48",
     "name":"Granular Sub-base & Blinding",
     "start":ds(-248), "end":ds(-225), "pct":100, "preds":p("t3"), "person":"Civil Team", "notes":""},
    {"id":"t5",  "type":"task",  "level":1, "color":"#027a48",
     "name":"RC Foundations & Bases — 35MPa (840 m³)",
     "start":ds(-228), "end":ds(-175), "pct":100, "preds":p("t4"), "person":"Civil Team", "notes":""},
    {"id":"t6",  "type":"task",  "level":1, "color":"#027a48",
     "name":"Waterproofing & Backfill",
     "start":ds(-178), "end":ds(-150), "pct":100, "preds":p("t5"), "person":"Civil Team", "notes":""},

    # ── 3. Civil — Superstructure (group, level 0) ───────────────────────────
    {"id":"g3",  "type":"group", "level":0, "color":"#027a48",
     "name":"Civil — Superstructure",
     "start":ds(-172), "end":ds(-35), "pct":75, "preds":p("t5"), "person":"", "notes":""},
    {"id":"t7",  "type":"task",  "level":1, "color":"#027a48",
     "name":"RC Columns & Walls — 30MPa (340 m³)",
     "start":ds(-172), "end":ds(-120), "pct":100, "preds":p("t5"), "person":"Civil Team", "notes":""},
    {"id":"t8",  "type":"task",  "level":1, "color":"#027a48",
     "name":"Concrete Block Work (1,400 m²)",
     "start":ds(-145), "end":ds(-40), "pct":100, "preds":p("t7"), "person":"Civil Team", "notes":""},
    {"id":"t9",  "type":"task",  "level":1, "color":"#027a48",
     "name":"RC Roof Slabs & Beams — 30MPa (1,170 m³)",
     "start":ds(-118), "end":ds(-35), "pct":70, "preds":p("t7"), "person":"Civil Team", "notes":""},

    # ── 4. Architectural Finishes (group, level 0) ───────────────────────────
    {"id":"g4",  "type":"group", "level":0, "color":"#b54708",
     "name":"Architectural Finishes",
     "start":ds(-80), "end":ds(42), "pct":35, "preds":p("t8"), "person":"", "notes":""},
    {"id":"t10", "type":"task",  "level":1, "color":"#b54708",
     "name":"Internal Plastering & Screeds",
     "start":ds(-80), "end":ds(-14), "pct":60, "preds":p("t8"), "person":"Finishing Team", "notes":""},
    {"id":"t11", "type":"task",  "level":1, "color":"#b54708",
     "name":"Floor & Wall Tiling — Granite/Ceramic",
     "start":ds(-35), "end":ds(42), "pct":15, "preds":p("t10"), "person":"Finishing Team", "notes":""},

    # ── 5. Mechanical Works (group, level 0) ─────────────────────────────────
    {"id":"g5",  "type":"group", "level":0, "color":"#6941c6",
     "name":"Mechanical Works",
     "start":ds(-145), "end":ds(35), "pct":68, "preds":p("t5"), "person":"", "notes":""},
    {"id":"t12", "type":"task",  "level":1, "color":"#6941c6",
     "name":"Steel Pipework DN200/DN250 (720 m)",
     "start":ds(-145), "end":ds(14), "pct":75, "preds":p("t5"), "person":"Mech Team", "notes":""},
    {"id":"t13", "type":"task",  "level":1, "color":"#6941c6",
     "name":"Pump Set Installation — KSB P-01 to P-04",
     "start":ds(-100), "end":ds(7), "pct":75, "preds":p("t12"), "person":"KSB Engineer", "notes":""},
    {"id":"t14", "type":"task",  "level":1, "color":"#6941c6",
     "name":"Valves, Fittings & Pump Manifold",
     "start":ds(-35), "end":ds(35), "pct":20, "preds":p("t12"), "person":"Mech Team", "notes":""},

    # ── 6. Electrical & Instrumentation (group, level 0) ────────────────────
    {"id":"g6",  "type":"group", "level":0, "color":"#0e9f6e",
     "name":"Electrical & Instrumentation",
     "start":ds(-120), "end":ds(56), "pct":52, "preds":[], "person":"", "notes":""},
    {"id":"t15", "type":"task",  "level":1, "color":"#0e9f6e",
     "name":"HV/LV Cable Installation",
     "start":ds(-120), "end":ds(-7), "pct":85, "preds":[], "person":"Elec Team", "notes":""},
    {"id":"t16", "type":"task",  "level":1, "color":"#0e9f6e",
     "name":"Distribution Boards & MCC",
     "start":ds(-65), "end":ds(21), "pct":55, "preds":p("t15"), "person":"Elec Team", "notes":""},
    {"id":"t17", "type":"task",  "level":1, "color":"#0e9f6e",
     "name":"Diesel Generator 1000KVA & ATS",
     "start":ds(-45), "end":ds(14), "pct":85, "preds":[], "person":"Elec Team", "notes":""},
    {"id":"t18", "type":"task",  "level":1, "color":"#0e9f6e",
     "name":"11kV Power Substation",
     "start":ds(-28), "end":ds(42), "pct":10, "preds":[], "person":"Substation Team", "notes":""},
    {"id":"t19", "type":"task",  "level":1, "color":"#0e9f6e",
     "name":"SCADA / Instrumentation",
     "start":ds(-14), "end":ds(56), "pct":20, "preds":p("t16"), "person":"SCADA Engineer", "notes":""},

    # ── 7. Pre-Commissioning & Testing (group, level 0) ─────────────────────
    {"id":"g7",  "type":"group", "level":0, "color":"#b42318",
     "name":"Pre-Commissioning & Testing",
     "start":ds(35), "end":ds(112), "pct":0, "preds":p("t13","t14","t16"), "person":"", "notes":""},
    {"id":"t20", "type":"task",  "level":1, "color":"#b42318",
     "name":"Hydraulic Pressure Tests",
     "start":ds(35), "end":ds(49), "pct":0, "preds":p("t14"), "person":"Mech Team", "notes":""},
    {"id":"t21", "type":"task",  "level":1, "color":"#b42318",
     "name":"Electrical Tests & Energisation",
     "start":ds(49), "end":ds(70), "pct":0, "preds":p("t18","t19"), "person":"Elec Team", "notes":""},
    {"id":"t22", "type":"task",  "level":1, "color":"#b42318",
     "name":"Pump Commissioning & Performance Test",
     "start":ds(70), "end":ds(98), "pct":0, "preds":p("t20","t21"), "person":"KSB Engineer", "notes":""},
    {"id":"t23", "type":"task",  "level":1, "color":"#b42318",
     "name":"SCADA Integration & Trial Operation",
     "start":ds(91), "end":ds(112), "pct":0, "preds":p("t22"), "person":"SCADA Engineer", "notes":""},

    # ── 8. Completion Milestone ───────────────────────────────────────────────
    {"id":"ms1", "type":"milestone", "level":0, "color":"#101828",
     "name":"Project Completion & Handover",
     "start":ds(112), "end":ds(112), "pct":0, "preds":p("t23"), "person":"", "notes":""},
]


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    with app.app_context():
        proj = db.session.get(Project, 3)
        if not proj:
            print("ERROR: Project ID 3 not found.")
            sys.exit(1)

        # --- Financial ---
        fd = FinancialData.query.filter_by(project_id=3).first()
        if fd:
            print(f"Replacing existing financial data for project {proj.id} ({proj.code})")
        else:
            fd = FinancialData(project_id=3, updated_by=2)
            db.session.add(fd)
            print(f"Creating financial data for project {proj.id} ({proj.code})")

        fd.data = json.dumps(FINANCIAL_DATA, ensure_ascii=False)
        fd.updated_by = 2
        db.session.commit()
        print(f"  Financial: {len(FINANCIAL_DATA['boq'])} BOQ items, "
              f"{len(FINANCIAL_DATA['payments'])} payments, "
              f"{len(FINANCIAL_DATA['vo'])} VOs saved.")

        # --- Gantt ---
        gd = GanttData.query.filter_by(project_id=3).first()
        if gd:
            print(f"Replacing existing Gantt data")
        else:
            gd = GanttData(project_id=3, updated_by=2)
            db.session.add(gd)
            print(f"Creating Gantt data")

        gd.tasks = json.dumps(GANTT_TASKS, ensure_ascii=False)
        gd.updated_by = 2
        db.session.commit()
        print(f"  Gantt: {len(GANTT_TASKS)} tasks saved.")

        print("\nDone! Navigate to http://192.168.0.105:5000 to test.")
        print("  Finance:  /legacy/financial")
        print("  Gantt:    /legacy/gantt")


if __name__ == '__main__':
    main()
