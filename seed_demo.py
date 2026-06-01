#!/usr/bin/env python3
"""
BINNA — Demo Data Seeder
Populates all modules with realistic Auxiliary Pump Station data.

Usage:
    python seed_demo.py              # seeds first project found
    python seed_demo.py --id 3       # seeds project with id=3
    python seed_demo.py --list       # list available projects
    python seed_demo.py --clear --id 3  # wipe then re-seed project 3
"""
import argparse
import json
import sys
import os
from datetime import date, timedelta

# ── Bootstrap Flask app context ───────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import create_app, db
from app.models import (
    Project, DCLetter, Submittal, DailyReport,
    LabTest, FinancialData, GanttData
)

app = create_app('development')

# ── Helpers ───────────────────────────────────────────────────────────────────
TODAY = date.today()

def d(offset: int) -> date:
    """Return a date offset days from today."""
    return TODAY + timedelta(days=offset)

def ds(offset: int) -> str:
    """Return an ISO date string offset days from today."""
    return d(offset).isoformat()


# ── DC Letters ────────────────────────────────────────────────────────────────
def seed_dc(project_id: int, code: str):
    if DCLetter.query.filter_by(project_id=project_id).count():
        print('  DC: already has data — skipping')
        return

    letters = [
        dict(code=f'{code}-LetterIN-001', direction='incoming',
             subject='Request for Extension of Time — Delays Due to Flooding',
             from_party='Ministry of Water Resources', to_party='Al-Rasheed Construction Co.',
             letter_date=d(-112), received_date=d(-110),
             orig_no='MWR/CE/2025/4471', status='replied',
             notes='Ministry requesting explanation of 3-week delay on civil works due to heavy rain.'),
        dict(code=f'{code}-LetterIN-002', direction='incoming',
             subject='Site Meeting Minutes — Progress Meeting #4',
             from_party='AECOM Consulting Engineers', to_party='Al-Rasheed Construction Co.',
             letter_date=d(-98), received_date=d(-96),
             orig_no='AECOM/APS/MM-004', status='for-reference',
             notes='Minutes of 4th monthly progress meeting. Action items attached.'),
        dict(code=f'{code}-LetterIN-003', direction='incoming',
             subject='Instruction to Accelerate Mechanical Works',
             from_party='Ministry of Water Resources', to_party='Al-Rasheed Construction Co.',
             letter_date=d(-63), received_date=d(-61),
             orig_no='MWR/CE/2026/0112', status='received',
             notes='Client instruction to mobilise additional resources on mechanical installation.'),
        dict(code=f'{code}-LetterIN-004', direction='incoming',
             subject='Non-Conformance Report — Concrete Cube Test Failure (NCR-003)',
             from_party='AECOM Consulting Engineers', to_party='Al-Rasheed Construction Co.',
             letter_date=d(-45), received_date=d(-44),
             orig_no='AECOM/APS/NCR-003', status='replied',
             notes='One cube set from backfill blinding failed at 7-day test. Contractor to investigate.'),
        dict(code=f'{code}-LetterIN-005', direction='incoming',
             subject='Approval of Revised Pump Installation Method Statement',
             from_party='AECOM Consulting Engineers', to_party='Al-Rasheed Construction Co.',
             letter_date=d(-30), received_date=d(-29),
             orig_no='AECOM/APS/MS-APR-007', status='for-reference',
             notes='MS-007 Rev B approved with minor comments. Proceed with installation.'),
        dict(code=f'{code}-LetterOUT-001', direction='outgoing',
             subject='Monthly Progress Report — February 2026',
             from_party='Al-Rasheed Construction Co.', to_party='Ministry of Water Resources',
             cc='AECOM Consulting Engineers',
             letter_date=d(-87), orig_no=f'{code}-PR-Feb26',
             status='sent',
             notes='Overall progress 54%. Civil works 80% complete. Mechanical 44%. Electrical 52%.'),
        dict(code=f'{code}-LetterOUT-002', direction='outgoing',
             subject='Application for Extension of Time — 21 Calendar Days',
             from_party='Al-Rasheed Construction Co.', to_party='Ministry of Water Resources',
             cc='AECOM Consulting Engineers',
             letter_date=d(-105), orig_no=f'{code}-EOT-001',
             status='sent',
             notes='EOT claim for 21 days due to exceptionally adverse weather (Nov 2025). Supporting records enclosed.'),
        dict(code=f'{code}-LetterOUT-003', direction='outgoing',
             subject='Request for Variation Order — Additional Instrumentation Points',
             from_party='Al-Rasheed Construction Co.', to_party='Ministry of Water Resources',
             cc='AECOM Consulting Engineers',
             letter_date=d(-21), orig_no=f'{code}-VO-REQ-003',
             status='pending',
             notes='Additional 8 pressure/flow instrumentation points required per revised SCADA specification.'),
        dict(code=f'{code}-LetterOUT-004', direction='outgoing',
             subject='Response to NCR-003 — Concrete Cube Test Investigation',
             from_party='Al-Rasheed Construction Co.', to_party='AECOM Consulting Engineers',
             letter_date=d(-42), orig_no=f'{code}-NCR-003-RES',
             status='sent',
             notes='Investigation complete. Failure attributed to improper curing of sample. Core test of in-situ concrete confirmed strength >30 MPa. No remedial works required.'),
    ]

    for ltr in letters:
        obj = DCLetter(project_id=project_id, **ltr)
        db.session.add(obj)
    db.session.commit()
    print(f'  DC: inserted {len(letters)} letters ✓')


# ── Submittals (DWG, FIR, MIR, MS, RFI) ──────────────────────────────────────
def seed_submittals(project_id: int, code: str):
    existing = {
        t: Submittal.query.filter_by(project_id=project_id, module_type=t).count()
        for t in ('dwg', 'fir', 'mir', 'ms', 'rfi')
    }

    # ── Drawings ─────────────────────────────────────────────────────────────
    if existing['dwg']:
        print('  DWG: already has data — skipping')
    else:
        drawings = [
            dict(doc_number=1, revision='C', title='Site Plan, Earthworks & Setting Out',
                 description='Overall site boundary, access roads, grid lines and benchmark locations.',
                 submittal_date=d(-240), location='Entire Site', engineer='Eng. Khalid Mahmoud',
                 related_refs='', submitted_to='AECOM', cc_party='Ministry',
                 status='approved', notes='Rev C approved. Previous revisions archived.',
                 response_status='approved', response_date=d(-235), response_by='Dr. Samir Al-Ani',
                 response_notes='Approved for construction. Ensure BM-01 is protected throughout works.'),
            dict(doc_number=2, revision='B', title='Foundation Layout & Pile Cap Details',
                 description='Pad foundations F1–F18, pile caps, blinding layout and setting-out coordinates.',
                 submittal_date=d(-218), location='Pump House — Substructure', engineer='Eng. Khalid Mahmoud',
                 related_refs=f'{code}-DWG-001-C', submitted_to='AECOM', cc_party='Ministry',
                 status='approved', notes='Rev B issued following geotechnical update.',
                 response_status='approved', response_date=d(-213), response_by='Dr. Samir Al-Ani',
                 response_notes='Approved for construction.'),
            dict(doc_number=3, revision='A', title='RC Columns & Walls — Reinforcement Details',
                 description='Grade C30 reinforced concrete columns, walls and beam elevations.',
                 submittal_date=d(-175), location='Pump House — Superstructure', engineer='Eng. Khalid Mahmoud',
                 related_refs=f'{code}-DWG-002-B', submitted_to='AECOM', cc_party='',
                 status='approved', notes='',
                 response_status='approved', response_date=d(-168), response_by='Dr. Samir Al-Ani',
                 response_notes='Approved. Confirm lap lengths comply with BS 8110.'),
            dict(doc_number=4, revision='B', title='Pump Room Floor Plan, Sections & Equipment Layout',
                 description='Final pump arrangement, access walkways, drain channels and hatch locations.',
                 submittal_date=d(-90), location='Pump Room', engineer='Eng. Yusuf Al-Rashidi',
                 related_refs=f'{code}-DWG-002-B', submitted_to='AECOM', cc_party='Ministry',
                 status='notes', notes='Rev B submitted following pump vendor confirmed dimensions.',
                 response_status='notes', response_date=d(-83), response_by='Dr. Samir Al-Ani',
                 response_notes='Approved with comments: (1) Increase drain channel width to 300mm. (2) Add safety notice signage to drawing. Resubmit Rev C.'),
            dict(doc_number=5, revision='A', title='Steel Pipework General Arrangement — DN200/DN250',
                 description='Pipework routing, support locations, expansion joints and valve positions.',
                 submittal_date=d(-55), location='Pump Room & External', engineer='Eng. Yusuf Al-Rashidi',
                 related_refs=f'{code}-DWG-004-B', submitted_to='AECOM', cc_party='',
                 status='pending', notes='Awaiting consultant review.'),
            dict(doc_number=6, revision='A', title='Electrical Single Line Diagram & Load Schedule',
                 description='11kV incoming, MV switchgear, LV distribution, motor control centres.',
                 submittal_date=d(-110), location='Electrical Room', engineer='Eng. Ahmed Saleh',
                 related_refs='', submitted_to='AECOM', cc_party='Ministry',
                 status='approved', notes='',
                 response_status='approved', response_date=d(-104), response_by='Eng. Lara Hassan',
                 response_notes='Approved for construction. Confirmed fault level at 11kV bus = 350 MVA.'),
            dict(doc_number=7, revision='A', title='Control Panel Layout, Wiring Diagram & I/O List',
                 description='PLC panel arrangement, terminal designations, SCADA I/O schedule.',
                 submittal_date=d(-28), location='Control Room', engineer='Eng. Ahmed Saleh',
                 related_refs=f'{code}-DWG-006-A', submitted_to='AECOM', cc_party='',
                 status='corrections', notes='Initial submission for review.',
                 response_status='corrections', response_date=d(-21), response_by='Eng. Lara Hassan',
                 response_notes='Corrections required: (1) Update I/O list for revised SCADA spec v2.1. (2) Clarify fail-safe positions for all valve actuators. Resubmit.'),
        ]
        for i, d_ in enumerate(drawings, 1):
            obj = Submittal(project_id=project_id, module_type='dwg',
                            code=f'{code}-DWG-{i:03d}-{d_["revision"]}', **d_)
            db.session.add(obj)
        db.session.commit()
        print(f'  DWG: inserted {len(drawings)} drawings ✓')

    # ── FIR ───────────────────────────────────────────────────────────────────
    if existing['fir']:
        print('  FIR: already has data — skipping')
    else:
        firs = [
            dict(doc_number=1, revision='A', title='Excavation to Formation Level — Grid A–D',
                 description='Inspect excavation depth, side slopes and formation cleanliness before blinding.',
                 submittal_date=d(-242), location='Foundation Area — Grid A–D', engineer='Eng. Khalid Mahmoud',
                 submitted_to='AECOM', status='approved',
                 response_status='approved', response_date=d(-241), response_by='Dr. Samir Al-Ani',
                 response_notes='Formation level accepted. Proceed with blinding concrete.'),
            dict(doc_number=2, revision='A', title='Blinding Concrete & Reinforcement — Pad Footing F1–F8',
                 description='Inspect reinforcement placement, cover, bar sizes and spacers before pour.',
                 submittal_date=d(-215), location='Pad Footings F1–F8', engineer='Eng. Khalid Mahmoud',
                 submitted_to='AECOM', status='approved',
                 response_status='approved', response_date=d(-214), response_by='Dr. Samir Al-Ani',
                 response_notes='Approved to pour. Ensure vibration poker available on site.'),
            dict(doc_number=3, revision='A', title='Reinforcement Inspection — RC Columns Grid A & B',
                 description='Inspect starter bars, column cage, ties, cover and kicker before formwork.',
                 submittal_date=d(-168), location='Columns A1–A6 & B1–B6', engineer='Eng. Khalid Mahmoud',
                 submitted_to='AECOM', status='approved',
                 response_status='approved', response_date=d(-167), response_by='Dr. Samir Al-Ani',
                 response_notes='Approved. Increase kicker height to 150mm minimum on next phase.'),
            dict(doc_number=4, revision='A', title='Concrete Pour Inspection — Pump Chamber Walls',
                 description='Final check of wall reinforcement, formwork alignment and pour sequence.',
                 submittal_date=d(-100), location='Pump Chamber — East & West Walls', engineer='Eng. Yusuf Al-Rashidi',
                 submitted_to='AECOM', status='notes',
                 response_status='notes', response_date=d(-98), response_by='Dr. Samir Al-Ani',
                 response_notes='Approved to pour with comment: Ensure water stop at construction joint is correctly lapped and secured before concrete placement.'),
            dict(doc_number=5, revision='A', title='Pump Bedplate Grouting — Pump Unit P-01',
                 description='Inspect baseplate alignment, levelling and pocket preparation before grouting.',
                 submittal_date=d(-14), location='Pump Room — Pump P-01 Position', engineer='Eng. Yusuf Al-Rashidi',
                 submitted_to='AECOM', status='pending'),
            dict(doc_number=6, revision='A', title='Cable Tray Installation Inspection — Zone A (Ground Floor)',
                 description='Inspect tray support spacing, earthing continuity and cable separation before cable pull.',
                 submittal_date=d(-7), location='Ground Floor — Zones A & B', engineer='Eng. Ahmed Saleh',
                 submitted_to='AECOM', status='pending'),
        ]
        for i, d_ in enumerate(firs, 1):
            obj = Submittal(project_id=project_id, module_type='fir',
                            code=f'{code}-FIR-{i:03d}-{d_["revision"]}', **d_)
            db.session.add(obj)
        db.session.commit()
        print(f'  FIR: inserted {len(firs)} field inspection requests ✓')

    # ── MIR ───────────────────────────────────────────────────────────────────
    if existing['mir']:
        print('  MIR: already has data — skipping')
    else:
        mirs = [
            dict(doc_number=1, revision='A', title='Ready Mix Concrete — Grade C30/37 Mix Design',
                 description='Mix design submission for structural RC: foundations, walls and columns.',
                 submittal_date=d(-230), location='Concrete Batching Plant — Kadhimiya', engineer='Eng. Khalid Mahmoud',
                 submitted_to='AECOM', status='approved',
                 response_status='approved', response_date=d(-225), response_by='Dr. Samir Al-Ani',
                 response_notes='Mix approved. Max W/C = 0.45. Cube testing every 50 m³.'),
            dict(doc_number=2, revision='A', title='Deformed Steel Reinforcement — Grade B500B (Ø8 to Ø32mm)',
                 description='Mill certificates, tensile test results and bend test for all bar diameters.',
                 submittal_date=d(-225), location='Site Storage — Rebar Yard', engineer='Eng. Khalid Mahmoud',
                 submitted_to='AECOM', status='approved',
                 response_status='approved', response_date=d(-221), response_by='Dr. Samir Al-Ani',
                 response_notes='Approved. Certificates verified against EN 10080. Store on racks off ground.'),
            dict(doc_number=3, revision='A', title='Main Centrifugal Pump Set — Unit P-01 (KSB Etanorm 125-250)',
                 description='Factory data sheets, performance curves, FAT report and ITP.',
                 submittal_date=d(-140), location='Manufacturer — KSB Germany (via local agent)', engineer='Eng. Yusuf Al-Rashidi',
                 submitted_to='AECOM', status='approved',
                 response_status='approved', response_date=d(-133), response_by='Dr. Samir Al-Ani',
                 response_notes='Approved. Performance curves verified against design duty point 250 l/s @ 28m TDH.'),
            dict(doc_number=4, revision='A', title='Main Centrifugal Pump Set — Unit P-02 (KSB Etanorm 125-250)',
                 description='Factory data sheets, performance curves, FAT report and ITP.',
                 submittal_date=d(-135), location='Manufacturer — KSB Germany (via local agent)', engineer='Eng. Yusuf Al-Rashidi',
                 submitted_to='AECOM', status='notes',
                 response_status='notes', response_date=d(-128), response_by='Dr. Samir Al-Ani',
                 response_notes='Comment: FAT report references incorrect impeller diameter (288mm shown, 295mm required per spec). Resubmit with corrected FAT data sheet. Do not dispatch until resolved.'),
            dict(doc_number=5, revision='A', title='Steel Pipe — DN200 PN16, ERW, API 5L Grade B',
                 description='Mill certs, wall thickness, hydrostatic test pressure and coating spec.',
                 submittal_date=d(-95), location='Site — Pipe Storage Area', engineer='Eng. Yusuf Al-Rashidi',
                 submitted_to='AECOM', status='approved',
                 response_status='approved', response_date=d(-90), response_by='Dr. Samir Al-Ani',
                 response_notes='Approved. Confirm internal cement lining thickness prior to installation.'),
            dict(doc_number=6, revision='A', title='11kV Metal-Clad Switchgear — Schneider Electric RM6',
                 description='Type test certificates, factory test reports, drawings and nameplate data.',
                 submittal_date=d(-45), location='Manufacturer — Schneider Electric (Jordan)', engineer='Eng. Ahmed Saleh',
                 submitted_to='AECOM', status='pending',
                 notes='Awaiting consultant review. Equipment on site pending MIR approval.'),
            dict(doc_number=7, revision='A', title='Anti-Slip Ceramic Floor Tiles — 300×300mm, R11 Rating',
                 description='Product data sheet, slip resistance test (EN 13845), sample board.',
                 submittal_date=d(-18), location='Supplier Showroom — Al-Mansour, Baghdad', engineer='Eng. Yusuf Al-Rashidi',
                 submitted_to='AECOM', status='pending'),
        ]
        for i, d_ in enumerate(mirs, 1):
            obj = Submittal(project_id=project_id, module_type='mir',
                            code=f'{code}-MIR-{i:03d}-{d_["revision"]}', **d_)
            db.session.add(obj)
        db.session.commit()
        print(f'  MIR: inserted {len(mirs)} material inspections ✓')

    # ── MS ────────────────────────────────────────────────────────────────────
    if existing['ms']:
        print('  MS: already has data — skipping')
    else:
        mss = [
            dict(doc_number=1, revision='A', title='Method Statement — Bulk Excavation & Earthworks',
                 description='Excavation sequence, plant selection, slope stability, groundwater control and spoil disposal.',
                 submittal_date=d(-255), location='Entire Site', engineer='Eng. Khalid Mahmoud',
                 submitted_to='AECOM', status='approved',
                 response_status='approved', response_date=d(-250), response_by='Dr. Samir Al-Ani',
                 response_notes='Approved. Ensure daily groundwater level monitoring. Max side slope 1:1 in granular.'),
            dict(doc_number=2, revision='B', title='Method Statement — Reinforced Concrete Works (Walls & Columns)',
                 description='Formwork system, reinforcement placement, concrete placement and curing procedure.',
                 submittal_date=d(-185), location='Pump House Superstructure', engineer='Eng. Khalid Mahmoud',
                 submitted_to='AECOM', status='approved',
                 response_status='approved', response_date=d(-180), response_by='Dr. Samir Al-Ani',
                 response_notes='Rev B approved. Key requirement: 7-day minimum curing with wet hessian under polythene.'),
            dict(doc_number=3, revision='B', title='Method Statement — Pump Installation & Precision Alignment',
                 description='Equipment receiving, setting to base, grouting, shaft alignment procedure, coupling installation.',
                 submittal_date=d(-62), location='Pump Room', engineer='Eng. Yusuf Al-Rashidi',
                 submitted_to='AECOM', status='approved',
                 response_status='approved', response_date=d(-56), response_by='Dr. Samir Al-Ani',
                 response_notes='Rev B approved. Laser alignment equipment to be used. Alignment records to be submitted for approval before motor connection.'),
            dict(doc_number=4, revision='A', title='Method Statement — HV/LV Cable Installation',
                 description='Cable drum handling, pulling tensions, termination, IR testing and commissioning sequence.',
                 submittal_date=d(-35), location='All Electrical Routes', engineer='Eng. Ahmed Saleh',
                 submitted_to='AECOM', status='notes',
                 response_status='notes', response_date=d(-28), response_by='Eng. Lara Hassan',
                 response_notes='Comment: Section 4.3 pulling tension limits not specified for 11kV cable. Add cable manufacturer pulling eye load limits. Resubmit Rev B.'),
            dict(doc_number=5, revision='A', title='Method Statement — Pre-Commissioning, Testing & Commissioning',
                 description='System flushing, pressure testing, electrical testing, no-load run, load test and performance verification.',
                 submittal_date=d(-7), location='Complete Station', engineer='Eng. Yusuf Al-Rashidi',
                 submitted_to='AECOM', status='pending',
                 notes='Submitted for approval ahead of commissioning phase in approx. 5 weeks.'),
        ]
        for i, d_ in enumerate(mss, 1):
            obj = Submittal(project_id=project_id, module_type='ms',
                            code=f'{code}-MS-{i:03d}-{d_["revision"]}', **d_)
            db.session.add(obj)
        db.session.commit()
        print(f'  MS: inserted {len(mss)} method statements ✓')

    # ── RFI ───────────────────────────────────────────────────────────────────
    if existing['rfi']:
        print('  RFI: already has data — skipping')
    else:
        rfis = [
            dict(doc_number=1, revision='A', title='RFI-001: Foundation Bearing Capacity — Grid C Anomaly',
                 description='Ground investigation log shows softer stratum at -2.8m in Grid C. Request confirmation of bearing capacity or redesign.',
                 submittal_date=d(-235), location='Foundation — Grid C', engineer='Eng. Khalid Mahmoud',
                 submitted_to='AECOM', status='approved',
                 response_status='approved', response_date=d(-229), response_by='Dr. Samir Al-Ani',
                 response_notes='Extend pad depth by 0.3m in Grid C only. No changes to reinforcement required. Revised drawing issued (DWG-002 Rev B).'),
            dict(doc_number=2, revision='A', title='RFI-002: C30 Concrete Mix Design — Sulfate Resistance',
                 description='Site soils show high sulfate content (Class DS-3). Requesting confirmation of cement type required.',
                 submittal_date=d(-228), location='Foundation Area', engineer='Eng. Khalid Mahmoud',
                 submitted_to='AECOM', status='approved',
                 response_status='approved', response_date=d(-224), response_by='Dr. Samir Al-Ani',
                 response_notes='Confirm use of SRPC (Sulphate Resisting Portland Cement) for all below-ground concrete. OPC acceptable for superstructure above DPC level.'),
            dict(doc_number=3, revision='A', title='RFI-003: Pump Shaft Alignment Tolerance Specification',
                 description='Spec references DIN 15450 but pump vendor IOM manual specifies ISO 10816. Requesting clarification of governing standard.',
                 submittal_date=d(-70), location='Pump Room', engineer='Eng. Yusuf Al-Rashidi',
                 submitted_to='AECOM', status='approved',
                 response_status='approved', response_date=d(-63), response_by='Dr. Samir Al-Ani',
                 response_notes='Govern by pump vendor IOM manual (KSB Doc. No. 7898.6/3). Target angular misalignment ≤ 0.05mm TIR.'),
            dict(doc_number=4, revision='A', title='RFI-004: HV Cable Routing Through Pump Room',
                 description='Clash identified between 11kV cable route and proposed pipework support steelwork at elevation +1.2m.',
                 submittal_date=d(-28), location='Pump Room — East Wall', engineer='Eng. Ahmed Saleh',
                 submitted_to='AECOM', status='notes',
                 response_status='notes', response_date=d(-22), response_by='Eng. Lara Hassan',
                 response_notes='11kV cable to be re-routed below slab via cable duct. Structural engineer to confirm duct opening size. Revised routing sketch attached (SK-E-004).'),
            dict(doc_number=5, revision='A', title='RFI-005: SCADA Communication Protocol — Modbus vs PROFIBUS',
                 description='Specification states Modbus RTU but project SCADA system tender spec requires PROFIBUS DP. Requesting clarification.',
                 submittal_date=d(-14), location='Control Room', engineer='Eng. Ahmed Saleh',
                 submitted_to='AECOM', status='pending',
                 notes='Urgent — affects PLC hardware selection currently on order.'),
            dict(doc_number=6, revision='A', title='RFI-006: External Paving — Permitted Expansion Joint Spacing',
                 description='Spec states 6m max joint spacing but site conditions (>45°C summer) may require 4m. Request approval to use 4m.',
                 submittal_date=d(-7), location='External Hardstanding Areas', engineer='Eng. Yusuf Al-Rashidi',
                 submitted_to='AECOM', status='pending'),
        ]
        for i, d_ in enumerate(rfis, 1):
            obj = Submittal(project_id=project_id, module_type='rfi',
                            code=f'{code}-RFI-{i:03d}-{d_["revision"]}', **d_)
            db.session.add(obj)
        db.session.commit()
        print(f'  RFI: inserted {len(rfis)} RFIs ✓')


# ── Daily Reports ─────────────────────────────────────────────────────────────
def seed_dr(project_id: int, code: str):
    if DailyReport.query.filter_by(project_id=project_id).count():
        print('  DR: already has data — skipping')
        return

    reports = [
        dict(doc_number=1, date=d(-18), weather='cloudy',
             weather_notes='Overcast, 22°C, light breeze. No rain.',
             engineers=3, laborers=28, technicians=6, other_workers=4,
             works=json.dumps([
                 'Block work — North elevation, courses 12–18, 1,400 m² cumulative now 68%',
                 'Pipework — DN200 suction header, 3 spools welded and pressure-tested',
                 'Electrical — Cable tray installation Ground Floor Zone A, 40 lineal metres installed',
                 'Pump P-01 base plate final levelling and shimming completed',
             ]),
             visitors=json.dumps([
                 {'name': 'Dr. Samir Al-Ani', 'org': 'AECOM Consulting — Resident Engineer'},
                 {'name': 'Mr. Tariq Hussain', 'org': 'Ministry of Water Resources — Site Inspector'},
             ]),
             next_plan='Complete block work North elevation. Begin DN250 discharge header installation. Continue cable tray Zone B.',
             notes='RE visited and reviewed block work. Minor horizontal joint variation noted — corrected by afternoon.',
             prepared_by='Eng. Yusuf Al-Rashidi', reviewed_by='Eng. Khalid Mahmoud'),

        dict(doc_number=2, date=d(-15), weather='sunny',
             weather_notes='Clear sky, 31°C. Hot afternoon — concrete and block work started at 06:00 and stopped at 13:00.',
             engineers=3, laborers=32, technicians=5, other_workers=4,
             works=json.dumps([
                 'Block work — North elevation completed to roof level (courses 12–22)',
                 'East elevation block work begun — courses 1–8 complete',
                 'Pump P-02 delivered to site and offloaded to pump room laydown area',
                 'Electrical — LV distribution board DB-02 installed and bolted to wall',
                 'Pipework welding — 4 spools complete on DN200 suction header',
             ]),
             visitors=json.dumps([]),
             next_plan='East elevation block work continue. Pump P-02 to be set on baseplate. DB-02 termination work to begin.',
             notes='Pump P-02 delivery note signed. Preliminary inspection — minor surface corrosion on coupling guard. Rust treated on site.',
             prepared_by='Eng. Yusuf Al-Rashidi', reviewed_by='Eng. Khalid Mahmoud'),

        dict(doc_number=3, date=d(-12), weather='sunny',
             weather_notes='Clear, 34°C. Extreme heat — all work between 12:00 and 15:00 suspended.',
             engineers=2, laborers=24, technicians=6, other_workers=3,
             works=json.dumps([
                 'East elevation block work — courses 9–16 complete',
                 'Pump P-02 baseplate installed, grouted and levelled ±0.1mm — grouting cube taken',
                 'Cable tray Zone B — 30 lineal metres installed and bonded to earthing grid',
                 'SCADA panel delivery inspection — panels accepted in good condition',
             ]),
             visitors=json.dumps([
                 {'name': 'Mr. Jassim Al-Saadi', 'org': 'KSB Pumps — Service Engineer'},
             ]),
             next_plan='Complete East elevation block work. Commence pump P-01 installation. Cable tray Zone C.',
             notes='KSB service engineer attended to witness P-02 baseplate grouting. Alignment work to commence once grout achieves 24hr strength.',
             prepared_by='Eng. Ahmed Saleh', reviewed_by='Eng. Khalid Mahmoud'),

        dict(doc_number=4, date=d(-9), weather='partly_cloudy',
             weather_notes='Partly cloudy, 27°C. Good working conditions all day.',
             engineers=4, laborers=35, technicians=8, other_workers=5,
             works=json.dumps([
                 'Pump P-01 installed on baseplate — pre-alignment check complete, within tolerance',
                 'Pump P-02 alignment commenced — angular 0.08mm TIR (target <0.05mm, correction ongoing)',
                 'East & South elevation block work — East 100%, South 60% complete',
                 'HV Cable 11kV XLPE pulling commenced — 180m pulled in Cable Route CR-01',
                 'DB-01 and DB-03 terminations complete and meggered',
             ]),
             visitors=json.dumps([
                 {'name': 'Dr. Samir Al-Ani', 'org': 'AECOM Consulting — RE'},
                 {'name': 'Mr. Jassim Al-Saadi', 'org': 'KSB Pumps — Service Engineer'},
             ]),
             next_plan='Continue P-02 alignment corrections. Complete 11kV cable pull CR-01. South elevation block work to finish.',
             notes='RE witnessed alignment and agreed to allow P-01 coupling to be made up. P-02 requires one shim adjustment — to be completed tomorrow.',
             prepared_by='Eng. Yusuf Al-Rashidi', reviewed_by='Eng. Khalid Mahmoud'),

        dict(doc_number=5, date=d(-6), weather='sunny',
             weather_notes='Sunny, 30°C. Normal site hours.',
             engineers=3, laborers=30, technicians=7, other_workers=4,
             works=json.dumps([
                 'Pump P-02 alignment — final check 0.03mm TIR ✓ coupling made up',
                 'South elevation block work — 100% complete. All external block work now complete.',
                 '11kV cable pull — CR-01 complete (320m). Drum end seals applied.',
                 'Cable tray Zone C — 25m installed. All ground floor tray installation now 100% complete.',
                 'Pump P-01 coupling guard installed. Motor connections made.',
             ]),
             visitors=json.dumps([
                 {'name': 'Dr. Samir Al-Ani', 'org': 'AECOM Consulting — RE'},
             ]),
             next_plan='Begin roof block work. Commence 11kV cable termination at switchgear. Submit FIR for P-01 baseplate grouting.',
             notes='Major milestone: all 4 external elevations of block work complete. RE signed inspection record ITP-MAS-003.',
             prepared_by='Eng. Yusuf Al-Rashidi', reviewed_by='Eng. Khalid Mahmoud'),

        dict(doc_number=6, date=d(-3), weather='sunny',
             weather_notes='Clear, 28°C. Excellent conditions.',
             engineers=3, laborers=26, technicians=8, other_workers=3,
             works=json.dumps([
                 '11kV cable terminations at Switchgear SW-01 and SW-02 — crimping complete',
                 'LV cabling — motor cables for P-01 and P-02 pulled and terminated at MCC',
                 'Internal plasterwork commenced — Pump Room wall base coat applied',
                 'SCADA control panel installed in control room and bolted to floor rails',
                 'Instrumentation — 4 No. pressure transmitters installed on manifold',
             ]),
             visitors=json.dumps([
                 {'name': 'Ms. Noor Al-Fahad', 'org': 'Ministry of Water Resources — Project Manager'},
                 {'name': 'Dr. Samir Al-Ani', 'org': 'AECOM Consulting — RE'},
             ]),
             next_plan='HV terminations to be witnessed by RE. Commence PLC programming. Continue plastering works.',
             notes='Ministry PM site visit — overall positive. Concern raised about SCADA commissioning timeline given RFI-005 outstanding. Action: expedite RFI-005 response.',
             prepared_by='Eng. Ahmed Saleh', reviewed_by='Eng. Khalid Mahmoud'),
    ]

    for r in reports:
        code_str = f'{code}-DR-{r["doc_number"]:03d}'
        obj = DailyReport(project_id=project_id, code=code_str, **r)
        db.session.add(obj)
    db.session.commit()
    print(f'  DR: inserted {len(reports)} daily reports ✓')


# ── Lab Tests ─────────────────────────────────────────────────────────────────
def seed_lbt(project_id: int, code: str):
    if LabTest.query.filter_by(project_id=project_id).count():
        print('  LBT: already has data — skipping')
        return

    # LBTOUT records first (sent samples), then LBTIN (results)
    sent = [
        dict(doc_number=1, direction='out', date=d(-214),
             material='Ready Mix Concrete — Grade C30 SRPC', test_type='Compressive Strength (28-day cube)',
             lab='Baghdad Central Materials Laboratory', location='Footing F1–F4 Pour Batch #1',
             sample_ref='APS-CUB-001', qty='6 No. 150mm cubes',
             notes='Batching plant batch card no. BP-2025-1147. Slump 85mm at point of discharge.'),
        dict(doc_number=2, direction='out', date=d(-175),
             material='Ready Mix Concrete — Grade C30 SRPC', test_type='Compressive Strength (28-day cube)',
             lab='Baghdad Central Materials Laboratory', location='RC Columns A1–A6 Pour',
             sample_ref='APS-CUB-002', qty='6 No. 150mm cubes',
             notes='Batch card BP-2025-1389. Slump 90mm.'),
        dict(doc_number=3, direction='out', date=d(-150),
             material='Deformed Rebar — B500B Ø16mm', test_type='Tensile Strength, Yield Strength & Bend Test',
             lab='Iraqi Standards & Quality Control Org.', location='Site Rebar Yard — Lot R-003',
             sample_ref='APS-STL-001', qty='3 No. 1.5m samples',
             notes='Random selection from delivery note DN-2025-0882.'),
        dict(doc_number=4, direction='out', date=d(-140),
             material='Compacted Fill — Granular Sub-base Type 1', test_type='In-Situ Dry Density (Sand Replacement)',
             lab='On-Site — Nuclear Densometer', location='Backfill Layer 1 — External to North Wall',
             sample_ref='APS-COMP-001', qty='5 test locations',
             notes='First 300mm compacted layer. Target 95% MDD (Proctor).'),
        dict(doc_number=5, direction='out', date=d(-130),
             material='Compacted Fill — Granular Sub-base Type 1', test_type='In-Situ Dry Density (Sand Replacement)',
             lab='On-Site — Nuclear Densometer', location='Backfill Layer 2 — External to North & East Walls',
             sample_ref='APS-COMP-002', qty='5 test locations',
             notes='Second 300mm compacted layer.'),
        dict(doc_number=6, direction='out', date=d(-98),
             material='Ready Mix Concrete — Grade C30 SRPC', test_type='Compressive Strength (28-day cube)',
             lab='Baghdad Central Materials Laboratory', location='Pump Chamber Walls — East & West',
             sample_ref='APS-CUB-003', qty='6 No. 150mm cubes',
             notes='Batch card BP-2026-0214. Slump 80mm.'),
        dict(doc_number=7, direction='out', date=d(-10),
             material='Steel Pipework — DN200 LSAW Butt Welds', test_type='Hydrostatic Pressure Test (1.5× WP = 24 bar)',
             lab='On-Site Witnessed Test', location='Suction Header — Section SH-01 to SH-04',
             sample_ref='APS-HYD-001', qty='Section length 45m',
             notes='Test pressure 24 bar, hold time 30 minutes. Pressure gauge calibrated — cert. attached.'),
    ]

    inserted_ids = []
    for s in sent:
        obj = LabTest(project_id=project_id,
                      code=f'{code}-LBTOUT-{s["doc_number"]:03d}', **s)
        db.session.add(obj)
        db.session.flush()   # get the ID
        inserted_ids.append(obj.id)
    db.session.commit()

    # LBTIN (results) — link back to LBTOUT
    results = [
        dict(doc_number=1, direction='in', date=d(-186),
             related_out_id=inserted_ids[0],
             result='pass', req_val='30', act_val='36.4', unit='MPa',
             result_notes='7-day: 27.1 MPa. 28-day: 36.4 MPa ✓ Exceeds characteristic strength. Batch PASS.'),
        dict(doc_number=2, direction='in', date=d(-147),
             related_out_id=inserted_ids[1],
             result='pass', req_val='30', act_val='34.8', unit='MPa',
             result_notes='28-day: 34.8 MPa ✓ Compliant.'),
        dict(doc_number=3, direction='in', date=d(-136),
             related_out_id=inserted_ids[2],
             result='pass', req_val='500 / 550', act_val='518 / 625', unit='MPa (Fy / Fu)',
             result_notes='Yield 518 MPa ✓ | Ultimate 625 MPa ✓ | Bend test — no cracking ✓. PASS.'),
        dict(doc_number=4, direction='in', date=d(-138),
             related_out_id=inserted_ids[3],
             result='pass', req_val='95% MDD (2,020 kg/m³)', act_val='98.2% (1,980 kg/m³ avg)', unit='% MDD',
             result_notes='All 5 test locations ≥ 95% MDD. PASS.'),
        dict(doc_number=5, direction='in', date=d(-128),
             related_out_id=inserted_ids[4],
             result='fail', req_val='95% MDD (2,020 kg/m³)', act_val='91.3% (min result)', unit='% MDD',
             result_notes='2 of 5 test locations below 95%: Location C = 91.3%, Location E = 93.1%. FAIL — rework and retest required. Rework completed and layer re-tested (APS-COMP-002B) — PASS.'),
        dict(doc_number=6, direction='in', date=d(-70),
             related_out_id=inserted_ids[5],
             result='pass', req_val='30', act_val='33.2', unit='MPa',
             result_notes='28-day: 33.2 MPa ✓ Compliant. 7-day: 22.5 MPa (slightly low — noted, 28-day acceptable).'),
        dict(doc_number=7, direction='in', date=d(-10),
             related_out_id=inserted_ids[6],
             result='pending', req_val='24 bar for 30 min', act_val='', unit='bar',
             result_notes='Test in progress. Pressure gauge readings at 0, 10 and 30 minutes to be recorded.'),
    ]

    for r in results:
        obj = LabTest(project_id=project_id,
                      code=f'{code}-LBTIN-{r["doc_number"]:03d}',
                      material='', test_type='', lab='', location='', sample_ref='', qty='', **r)
        db.session.add(obj)
    db.session.commit()
    print(f'  LBT: inserted {len(sent)} sent-sample + {len(results)} result records ✓')


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description='BINNA demo data seeder')
    parser.add_argument('--id',    type=int, help='Project ID to seed')
    parser.add_argument('--list',  action='store_true', help='List projects and exit')
    parser.add_argument('--clear', action='store_true', help='Delete existing demo data before seeding')
    args = parser.parse_args()

    with app.app_context():
        projects = Project.query.order_by(Project.id).all()

        if args.list:
            if not projects:
                print('No projects found in database.')
            else:
                print(f'{"ID":>4}  {"Code":<10}  Name')
                print('-' * 50)
                for p in projects:
                    print(f'{p.id:>4}  {p.code:<10}  {p.name}')
            return

        if not projects:
            print('ERROR: No projects found. Create a project first via the app.')
            sys.exit(1)

        if args.id:
            proj = Project.query.get(args.id)
            if not proj:
                print(f'ERROR: Project ID {args.id} not found.')
                sys.exit(1)
        else:
            proj = projects[0]
            print(f'No --id specified. Using first project: [{proj.id}] {proj.code} — {proj.name}')

        code = proj.code

        if args.clear:
            print(f'Clearing existing data for project {proj.id} ({code})...')
            DCLetter.query.filter_by(project_id=proj.id).delete()
            Submittal.query.filter_by(project_id=proj.id).delete()
            DailyReport.query.filter_by(project_id=proj.id).delete()
            LabTest.query.filter_by(project_id=proj.id).delete()
            db.session.commit()
            print('  Cleared.')

        print(f'\nSeeding demo data → Project [{proj.id}] {code} — {proj.name}\n')
        seed_dc(proj.id, code)
        seed_submittals(proj.id, code)
        seed_dr(proj.id, code)
        seed_lbt(proj.id, code)

        print(f'\n✅  Done! Open http://localhost:5000 and navigate to the project.')
        print('   Financial & Gantt demo data loads automatically on first page visit.')


if __name__ == '__main__':
    main()
