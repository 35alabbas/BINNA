#!/usr/bin/env python3
"""
BINNA -- Create Demo Project + Seed All Modules
Creates a fresh "APS" project and fills every module with test data.

Usage:
    python create_demo_project.py
"""
import sys, os, json
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import create_app, db
from app.models import (
    Project, ProjectMember, User,
    DCLetter, Submittal, DailyReport,
    LabTest, FinancialData, GanttData
)

app = create_app('development')
TODAY = date.today()

def d(offset):  return TODAY + timedelta(days=offset)
def ds(offset): return d(offset).isoformat()


# ─────────────────────────────────────────────────────────────────────────────
#  CREATE PROJECT
# ─────────────────────────────────────────────────────────────────────────────
def create_project(owner_id):
    proj = Project(
        code       = 'APS',
        name       = 'Auxiliary Pump Station - Phase 2',
        client     = 'Ministry of Water Resources',
        consultant = 'Al-Furat Engineering Consultants',
        contractor = 'Al-Rasheed Construction Co.',
        created_by = owner_id,
    )
    db.session.add(proj)
    db.session.flush()

    db.session.add(ProjectMember(project_id=proj.id, user_id=owner_id, role='owner'))
    for u in User.query.filter(User.id != owner_id).all():
        db.session.add(ProjectMember(project_id=proj.id, user_id=u.id, role='member'))

    db.session.commit()
    print('  Created project [%d] APS - Auxiliary Pump Station - Phase 2' % proj.id)
    return proj


# ─────────────────────────────────────────────────────────────────────────────
#  DC LETTERS
# ─────────────────────────────────────────────────────────────────────────────
def seed_dc(pid, code):
    CONS = 'Al-Furat Engineering Consultants'
    MWR  = 'Ministry of Water Resources'
    ARC  = 'Al-Rasheed Construction Co.'

    letters = [
        dict(code=code+'-LTR-IN-001', direction='incoming',
             subject='Request for Extension of Time - Flooding Delays',
             from_party=MWR, to_party=ARC,
             letter_date=d(-112), received_date=d(-110),
             status='replied', notes='EOT formally requested -- 28 additional days claimed.'),

        dict(code=code+'-LTR-IN-002', direction='incoming',
             subject='Site Meeting Minutes - Progress Review No.4',
             from_party=CONS, to_party=ARC,
             letter_date=d(-89), received_date=d(-88),
             status='acknowledged', notes='Meeting minutes distributed. Action points assigned.'),

        dict(code=code+'-LTR-IN-003', direction='incoming',
             subject='Instruction to Accelerate Electrical Works',
             from_party=MWR, to_party=ARC,
             letter_date=d(-65), received_date=d(-64),
             status='replied', notes='Acceleration instruction issued citing 14-day programme slippage.'),

        dict(code=code+'-LTR-IN-004', direction='incoming',
             subject='Non-Conformance Report - Concrete Cube Failure',
             from_party=CONS, to_party=ARC,
             letter_date=d(-44), received_date=d(-43),
             status='replied', notes='NCR issued for pump chamber wall pour. Root cause analysis required.'),

        dict(code=code+'-LTR-IN-005', direction='incoming',
             subject='Approval of Method Statement - Pump Installation',
             from_party=CONS, to_party=ARC,
             letter_date=d(-21), received_date=d(-20),
             status='acknowledged', notes='MS-003 approved with comments. Proceed as instructed.'),

        dict(code=code+'-LTR-IN-006', direction='incoming',
             subject='Request for Updated Programme',
             from_party=MWR, to_party=ARC,
             letter_date=d(-9), received_date=d(-8),
             status='pending', notes='Client requests revised Baseline programme by end of week.'),

        dict(code=code+'-LTR-OUT-001', direction='outgoing',
             subject='Monthly Progress Report - Month 8',
             from_party=ARC, to_party=MWR,
             letter_date=d(-95), received_date=None,
             status='sent', notes='Overall progress 62%. Critical path item: SCADA delivery delayed.'),

        dict(code=code+'-LTR-OUT-002', direction='outgoing',
             subject='EOT Application - 28 Days for Flooding Event',
             from_party=ARC, to_party=MWR,
             letter_date=d(-104), received_date=None,
             status='replied', notes='Supporting records and weather data attached.'),

        dict(code=code+'-LTR-OUT-003', direction='outgoing',
             subject='Variation Order Request - Additional Rock Excavation',
             from_party=ARC, to_party=CONS,
             letter_date=d(-78), received_date=None,
             status='pending', notes='VO requested for 340m3 unexpected rock excavation. Quotation enclosed.'),

        dict(code=code+'-LTR-OUT-004', direction='outgoing',
             subject='Response to NCR - Concrete Cube Failure Investigation',
             from_party=ARC, to_party=CONS,
             letter_date=d(-38), received_date=None,
             status='sent', notes='Root cause: aggregate grading issue. Corrective action implemented.'),
    ]

    for ltr in letters:
        db.session.add(DCLetter(project_id=pid, **ltr))
    db.session.commit()
    print('  DC     -- %d letters seeded' % len(letters))


# ─────────────────────────────────────────────────────────────────────────────
#  SUBMITTALS  (DWG / FIR / MIR / MS / RFI)
# ─────────────────────────────────────────────────────────────────────────────
def seed_submittals(pid, code):
    CONS = 'Al-Furat Engineering Consultants'

    def sub(num, mtype, rev, title, date_offset, status, notes):
        has_response = status in ('approved', 'notes', 'rejected', 'corrections')
        return dict(
            doc_number    = num,
            module_type   = mtype,
            revision      = rev,
            code          = '%s-%s-%03d' % (code, mtype.upper(), num),
            title         = title,
            submittal_date= d(date_offset),
            submitted_to  = CONS,
            status        = status,
            notes         = notes,
            response_status = status if has_response else None,
            response_by   = CONS if has_response else None,
            response_date = d(date_offset + 10) if has_response else None,
        )

    drawings = [
        sub(1,'dwg','C','Site Layout and Setting Out Plan',              -180,'approved','Approved. Use for construction.'),
        sub(2,'dwg','B','Foundation Layout - Pump Chamber',              -155,'approved','Approved after revision B.'),
        sub(3,'dwg','A','RC Details - Walls and Columns',                -130,'approved','Good for construction.'),
        sub(4,'dwg','B','Pump Room Plan and Sections',                   -105,'notes',   'Approved with comments - update pipe clearances.'),
        sub(5,'dwg','A','Pipework General Arrangement DN200/DN250',       -60,'pending', 'Under review.'),
        sub(6,'dwg','B','11kV Single Line Diagram',                       -95,'approved','Approved Rev B.'),
        sub(7,'dwg','A','Control Panel Schematic - SCADA Interface',      -30,'rejected','Resubmit - SCADA protocol not to spec.'),
    ]

    firs = [
        sub(1,'fir','0','Earthworks - Excavation Completion',             -220,'approved','Levels checked and accepted.'),
        sub(2,'fir','0','Blinding Concrete and Rebar - Foundations',      -195,'approved','Rebar spacing and cover approved.'),
        sub(3,'fir','0','Column Rebar - Ground Level',                    -160,'approved','Starter bars and couplers checked OK.'),
        sub(4,'fir','0','Pump Chamber Walls - Rebar and Formwork',        -120,'notes',   'Approved - verify waterstop continuity before pour.'),
        sub(5,'fir','0','Pump Grouting and Base Plate Setting',            -40,'pending', 'Inspection scheduled.'),
        sub(6,'fir','0','Cable Tray Installation - Level 1',               -15,'pending', 'Awaiting engineer visit.'),
    ]

    mirs = [
        sub(1,'mir','0','Concrete C30/37 - Batch Plant Approval',         -200,'approved','Mix design and trial mix results accepted.'),
        sub(2,'mir','0','Reinforcement Bar B500B - Mill Certificates',     -190,'approved','All certs verified. Approved.'),
        sub(3,'mir','0','Submersible Pump Set P-01 Grundfos SP250-7',      -140,'approved','FAT witnessed. Approved for installation.'),
        sub(4,'mir','A','Submersible Pump Set P-02 Grundfos SP250-7',      -125,'notes',   'FAT borderline on efficiency - retest during SAT.'),
        sub(5,'mir','0','Ductile Iron Pipe DN200/DN250 Class K9',          -100,'approved','Material certs and hydro test results accepted.'),
        sub(6,'mir','0','11kV Switchgear Panel - Type Test Certificates',   -55,'pending', 'Type test certificates under review.'),
        sub(7,'mir','0','Floor and Wall Tiles - Pump Room Finishing',       -20,'pending', 'Sample submitted. Decision pending.'),
    ]

    methods = [
        sub(1,'ms','A','Excavation and Earthworks',                       -230,'approved','Approved Rev A.'),
        sub(2,'ms','B','Reinforced Concrete Works',                       -170,'approved','Rev B approved after addressing waterstop detail.'),
        sub(3,'ms','A','Pump Installation and Alignment',                  -60,'approved','Approved with comments - see incoming letter 005.'),
        sub(4,'ms','A','HV and LV Cable Installation',                     -35,'notes',   'Approved - segregation between HV and LV to be maintained.'),
        sub(5,'ms','0','System Commissioning and Performance Testing',      -10,'pending', 'Under review prior to commissioning phase.'),
    ]

    rfis = [
        sub(1,'rfi','0','Foundation Bearing Capacity Confirmation',        -210,'approved','Confirmed 150 kPa bearing capacity. Proceed as designed.'),
        sub(2,'rfi','0','Concrete Mix Design - Sulfate Resistance',        -185,'approved','SR cement confirmed. C30/37 XS2 approved.'),
        sub(3,'rfi','0','Pump Centreline Alignment Tolerance',              -90,'approved','+/- 2mm tolerance accepted for this application.'),
        sub(4,'rfi','A','HV Cable Routing Through Structural Wall',         -50,'notes',   '150mm sleeve approved. Fire-stop detail to be confirmed.'),
        sub(5,'rfi','0','SCADA Communication Protocol Modbus vs IEC 61850',-22,'pending', 'Awaiting client IT department confirmation.'),
        sub(6,'rfi','0','External Paving Joint Width Clarification',         -8,'pending', 'Query raised on joint spacing at pump forecourt.'),
    ]

    all_submittals = drawings + firs + mirs + methods + rfis
    for s in all_submittals:
        db.session.add(Submittal(project_id=pid, **s))
    db.session.commit()
    print('  DWG    -- %d drawings seeded'          % len(drawings))
    print('  FIR    -- %d inspections seeded'        % len(firs))
    print('  MIR    -- %d material approvals seeded' % len(mirs))
    print('  MS     -- %d method statements seeded'  % len(methods))
    print('  RFI    -- %d RFIs seeded'               % len(rfis))


# ─────────────────────────────────────────────────────────────────────────────
#  DAILY REPORTS
# ─────────────────────────────────────────────────────────────────────────────
def seed_dr(pid, code):
    def dr(num, date_offset, weather_short, weather_desc, eng, lab, tech, other, works, visitors, next_plan, notes=''):
        return dict(
            code=code+'-DR-%04d' % num,
            doc_number=num,
            date=d(date_offset),
            weather=weather_short,
            weather_notes=weather_desc,
            engineers=eng,
            laborers=lab,
            technicians=tech,
            other_workers=other,
            works=json.dumps(works),
            visitors=json.dumps(visitors),
            next_plan=next_plan,
            notes=notes,
        )

    reports = [
        dr(41, -18, 'cloudy',
           'Partly cloudy, 34C, light NW wind 15 km/h',
           3, 42, 6, 4,
           [
               'RC wall formwork - pump chamber east wall, grid lines C-D (60% complete)',
               'Rebar fixing - columns C3 and C4 completed, starter bars set',
               'Cable tray installation - Level 1 corridor, 38m installed today',
           ],
           [
               {'name': 'Eng. Kareem Saleh', 'org': 'Al-Furat Engineering'},
           ],
           'Complete east wall formwork and prepare for concrete pour. Continue cable tray to substation room.',
           'Concrete pump breakdown -- 2h delay to morning pour.',
        ),
        dr(42, -17, 'sunny',
           'Clear, 36C, calm',
           2, 32, 4, 3,
           [
               'Concrete pour - east wall pump chamber, 42m3 C30/37, 14:00-18:30',
               'Curing compound applied to previous day pour (north wall)',
               'Earthing cable laying - external perimeter, 120m completed',
           ],
           [],
           'Strip east wall formwork after 24h. Commence west wall formwork.',
        ),
        dr(43, -14, 'sunny',
           'Hot and sunny, 39C, dust haze in afternoon',
           3, 46, 5, 4,
           [
               'Pump P-03 lifted into pump chamber - alignment ongoing',
               'Formwork stripping - east wall completed, surfaces acceptable',
               'Block work - admin block north elevation, 3 courses completed',
           ],
           [
               {'name': 'Eng. Hind Mahmoud',  'org': 'Ministry of Water Resources'},
               {'name': 'Mr. Tariq Abbas',     'org': 'Grundfos Iraq'},
           ],
           'Complete P-03 alignment and grouting. Continue block work west elevation.',
           'Dust haze required early stoppage of outdoor works at 15:30.',
        ),
        dr(44, -11, 'rain',
           'Overcast, 31C, light rain 06:00-08:00',
           2, 26, 7, 3,
           [
               'LV distribution board DB-02 installed and fixed - substation room',
               'Grouting - pump P-03 base plate, non-shrink grout applied',
               'Plastering - admin block internal walls, 210m2 completed',
           ],
           [],
           'Terminate LV cables to DB-02. Commence P-04 installation.',
           'Morning rain delayed site mobilisation by 90 minutes.',
        ),
        dr(45, -7, 'sunny',
           'Clear, 37C, moderate SE wind 25 km/h',
           3, 50, 14, 5,
           [
               'Pump P-04 lifted and aligned - alignment tolerance +/-1.5mm achieved',
               'HV cable pulling - 11kV cable Runs C1 and C2, 340m pulled',
               'External block work - south elevation completed',
               'Tiling - pump room floor, 85m2 laid',
           ],
           [
               {'name': 'Eng. Kareem Saleh', 'org': 'Al-Furat Engineering'},
           ],
           'Grout P-04 base plate. Terminate HV cables at switchgear. Continue tiling.',
        ),
        dr(46, -4, 'sunny',
           'Sunny, 38C, calm',
           2, 38, 10, 4,
           [
               '11kV switchgear cable terminations - bays 1 and 2 completed',
               'SCADA panel delivered to site and placed in control room',
               'External cladding - east facade, 180m2 installed',
               'Door frames - 8 frames fixed in block work openings',
           ],
           [
               {'name': 'Eng. Hind Mahmoud', 'org': 'Ministry of Water Resources'},
               {'name': 'Eng. Ali Hassan',   'org': 'Schneider Electric'},
           ],
           'Begin SCADA panel installation and earthing. Continue cladding north facade.',
           'SCADA delivery 3 days late -- contractor to update programme accordingly.',
        ),
    ]

    for r in reports:
        db.session.add(DailyReport(project_id=pid, **r))
    db.session.commit()
    print('  DR     -- %d daily reports seeded' % len(reports))

def seed_lbt(pid, code):
    BCL = 'Baghdad Central Testing Laboratory'
    GSI = 'Geotechnical Services Iraq'

    def lout(num, test_type, material, date_offset, lab, notes=''):
        return dict(
            code=code+'-LBTOUT-%03d' % num,
            doc_number=num,
            direction='out',
            date=d(date_offset),
            test_type=test_type,
            material=material,
            lab=lab,
            notes=notes,
        )

    def lin(num, test_type, material, date_offset, result, req, act, unit, out_id, notes=''):
        return dict(
            code=code+'-LBTIN-%03d' % num,
            doc_number=num,
            direction='in',
            date=d(date_offset),
            test_type=test_type,
            material=material,
            result=result,
            req_val=str(req),
            act_val=str(act),
            unit=unit,
            related_out_id=out_id,
            result_notes=notes,
        )

    tests_out = [
        lout(1,'Concrete Cube Compression','Concrete C30/37 - Pump Chamber Foundation',  -195, BCL, 'Samples sent to lab for 28-day testing.'),
        lout(2,'Concrete Cube Compression','Concrete C30/37 - Pump Chamber Walls',       -145, BCL, 'Samples sent to lab for 28-day testing.'),
        lout(3,'Concrete Cube Compression','Concrete C30/37 - Columns and Beams',        -118, BCL, 'Samples sent to lab for 28-day testing.'),
        lout(4,'Tensile and Bend Test',    'Rebar B500B - 16mm diameter',                -180, BCL, 'Samples sent for tensile and bend per BS 4449.'),
        lout(5,'Soil Compaction Proctor',  'Backfill - Pump Chamber Surround Layer 1',   -160, GSI, 'Field density test - Layer 1.'),
        lout(6,'Soil Compaction Proctor',  'Backfill - Pump Chamber Surround Layer 2',   -140, GSI, 'Field density test - Layer 2.'),
        lout(7,'Hydrostatic Pressure Test','Pipework System - Pump Manifold DN200',       -35, 'On-site (witnessed by Al-Furat)', 'Pressure test at 1.5x working pressure.'),
    ]

    for t in tests_out:
        db.session.add(LabTest(project_id=pid, **t))
    db.session.flush()

    out_recs = LabTest.query.filter_by(project_id=pid, direction='out').order_by(LabTest.id).all()

    tests_in = [
        lin(1,'Concrete Cube Compression','Concrete C30/37 - Pump Chamber Foundation', -167, 'pass', 30, 38.5, 'MPa', out_recs[0].id, 'Cert No. BCL-2025-4412. PASS.'),
        lin(2,'Concrete Cube Compression','Concrete C30/37 - Pump Chamber Walls',      -117, 'pass', 30, 35.2, 'MPa', out_recs[1].id, 'Cert No. BCL-2025-5891. PASS.'),
        lin(3,'Concrete Cube Compression','Concrete C30/37 - Columns and Beams',        -90, 'pass', 30, 41.0, 'MPa', out_recs[2].id, 'Cert No. BCL-2025-6234. PASS.'),
        lin(4,'Tensile and Bend Test',    'Rebar B500B - 16mm diameter',               -166, 'pass', 500, 540, 'MPa', out_recs[3].id, 'Cert No. BCL-2025-4215. PASS.'),
        lin(5,'Soil Compaction Proctor',  'Backfill - Layer 1',                        -154, 'pass', 95, 97.2, '% MDD', out_recs[4].id, 'Report No. GSI-2025-0881. PASS.'),
        lin(6,'Soil Compaction Proctor',  'Backfill - Layer 2 FAIL rework',            -134, 'fail', 95, 91.3, '% MDD', out_recs[5].id, 'Report No. GSI-2025-0934. FAIL. Area to be reworked.'),
        lin(7,'Hydrostatic Pressure Test','Pipework System - Pump Manifold DN200',      -28, 'pass', 12, 12,   'bar',   out_recs[6].id, 'Test cert signed by Al-Furat resident engineer. PASS.'),
    ]

    for t in tests_in:
        db.session.add(LabTest(project_id=pid, **t))
    db.session.commit()
    print('  LBT    -- %d test-out + %d test-in seeded' % (len(tests_out), len(tests_in)))

# ─────────────────────────────────────────────────────────────────────────────
def seed_financial(pid):
    if FinancialData.query.filter_by(project_id=pid).first():
        print('  Financial: already has data -- skipping')
        return

    # Flat BOQ list — this is the schema the contract page reads:
    #   data.boq = [{desc, unit, qty, price}], item ids assigned by row index
    #   (boq0..boqN) in binna-contract.html. A sectioned shape renders blank
    #   rows, so keep it flat to match the frontend / seed_financial.py.
    boq = [
        # Civil Works
        {'desc':'Excavation in all materials',                      'unit':'m3', 'qty':'2500','price':'4500'},
        {'desc':'Reinforced concrete C30/37 - foundations',        'unit':'m3', 'qty':'850', 'price':'90000'},
        {'desc':'Reinforced concrete C30/37 - walls and columns',  'unit':'m3', 'qty':'380', 'price':'105000'},
        {'desc':'Concrete block work 200mm',                       'unit':'m2', 'qty':'1400','price':'11500'},
        {'desc':'External civil works (paving, drainage, fencing)','unit':'LS', 'qty':'1',   'price':'8200000'},
        # Mechanical Works
        {'desc':'Submersible pump sets Grundfos SP250-7 supply',   'unit':'No.','qty':'4',   'price':'3200000'},
        {'desc':'Ductile iron pipework DN200/DN250',               'unit':'m',  'qty':'720', 'price':'42000'},
        {'desc':'Valves, fittings and pump manifold',              'unit':'LS', 'qty':'1',   'price':'9500000'},
        {'desc':'Mechanical ancillaries and supports',             'unit':'LS', 'qty':'1',   'price':'4800000'},
        # Electrical Works
        {'desc':'11kV switchgear panels 2 No.',                    'unit':'No.','qty':'2',   'price':'5500000'},
        {'desc':'LV distribution boards 6 No.',                    'unit':'No.','qty':'6',   'price':'680000'},
        {'desc':'Power and control cabling',                       'unit':'m',  'qty':'2200','price':'9000'},
        {'desc':'SCADA and control and instrumentation system',    'unit':'LS', 'qty':'1',   'price':'14500000'},
        {'desc':'Earthing and lightning protection system',        'unit':'LS', 'qty':'1',   'price':'3200000'},
        # Finishing Works
        {'desc':'Internal plastering and rendering',               'unit':'m2', 'qty':'1800','price':'7500'},
        {'desc':'External cladding and insulation',                'unit':'m2', 'qty':'920', 'price':'16500'},
        {'desc':'Floor and wall tiling - pump room and admin',     'unit':'m2', 'qty':'650', 'price':'21000'},
        {'desc':'Doors, windows and ironmongery',                  'unit':'No.','qty':'18',  'price':'450000'},
    ]

    contract_details = {
        'contractor':   'Al-Rasheed Construction Co.',
        'client':       'Ministry of Water Resources',
        'project':      'Auxiliary Pump Station - Phase 2',
        'contract-no':  'MWR-2025-APS-047',
        'date':         '2025-09-01',
        'period':       '12 Months',
        'type':         'Government - Unit Rate Contract',
        'insurance':    '5',
        'tax':          '3',
        'contract-end': '2026-08-31',
        'penalty-rate': '0.1',
        'rules':        'Iraqi Government Standard Conditions of Contract. Cumulative penalties capped at 10% of contract value.',
    }

    data = {
        'contractDetails': contract_details,
        'usdRate': 1310,
        'boq': boq,
        'vo': [],
        'payments': [],
        'income': [],
        'expenseCategories': [],
    }

    db.session.add(FinancialData(project_id=pid, data=json.dumps(data, ensure_ascii=False)))
    db.session.commit()
    print('  Financial -- BOQ (%d items, flat schema) seeded' % len(boq))


# ─────────────────────────────────────────────────────────────────────────────
#  GANTT (JSON blob)
# ─────────────────────────────────────────────────────────────────────────────
def seed_gantt(pid):
    if GanttData.query.filter_by(project_id=pid).first():
        print('  Gantt: already has data -- skipping')
        return

    def start(o):  return (TODAY + timedelta(days=o)).isoformat()
    def end(o, dur): return (TODAY + timedelta(days=o+dur)).isoformat()

    tasks = [
        {'id':'g0', 'type':'group',     'name':'Mobilization',                              'start':start(-268),'end':end(-255,9),  'pct':100,'color':'#6941C6'},
        {'id':'t01','type':'task','parent':'g0','name':'Site Mobilization and Setup',        'start':start(-268),'end':end(-268,14), 'pct':100,'color':'#7F56D9'},
        {'id':'t02','type':'task','parent':'g0','name':'Survey and Setting Out',             'start':start(-255),'end':end(-255,10), 'pct':100,'color':'#7F56D9'},

        {'id':'g1', 'type':'group',     'name':'Civil Works',                               'start':start(-248),'end':end(-48,0),   'pct':82, 'color':'#C4320A'},
        {'id':'t11','type':'task','parent':'g1','name':'Earthworks and Excavation 2500m3',  'start':start(-248),'end':end(-248,28), 'pct':100,'color':'#F97066'},
        {'id':'t12','type':'task','parent':'g1','name':'RC Foundations C30/37 850m3',       'start':start(-220),'end':end(-220,42), 'pct':100,'color':'#F97066'},
        {'id':'t13','type':'task','parent':'g1','name':'RC Walls and Columns 380m3',        'start':start(-178),'end':end(-178,70), 'pct':100,'color':'#F97066'},
        {'id':'t14','type':'task','parent':'g1','name':'Block Work 1400m2',                 'start':start(-108),'end':end(-108,45), 'pct':84, 'color':'#F97066'},
        {'id':'t15','type':'task','parent':'g1','name':'External Civil Works',              'start':start(-63), 'end':end(-63,42),  'pct':40, 'color':'#F97066'},

        {'id':'g2', 'type':'group',     'name':'Mechanical Works',                          'start':start(-145),'end':end(-21,56),  'pct':46, 'color':'#067647'},
        {'id':'t21','type':'task','parent':'g2','name':'Pump Sets Supply 4 No. Grundfos',   'start':start(-145),'end':end(-145,84), 'pct':100,'color':'#32D583'},
        {'id':'t22','type':'task','parent':'g2','name':'Pipework DN200/DN250 720m',         'start':start(-88), 'end':end(-88,70),  'pct':68, 'color':'#32D583'},
        {'id':'t23','type':'task','parent':'g2','name':'Pump Installation and Alignment',   'start':start(-56), 'end':end(-56,56),  'pct':35, 'color':'#32D583'},
        {'id':'t24','type':'task','parent':'g2','name':'Valves Fittings and Manifold',      'start':start(-21), 'end':end(-21,56),  'pct':12, 'color':'#32D583'},

        {'id':'g3', 'type':'group',     'name':'Electrical Works',                          'start':start(-115),'end':end(-15,56),  'pct':54, 'color':'#B54708'},
        {'id':'t31','type':'task','parent':'g3','name':'11kV Switchgear Supply and Install','start':start(-115),'end':end(-115,42), 'pct':100,'color':'#F79009'},
        {'id':'t32','type':'task','parent':'g3','name':'LV Distribution Boards 6 No.',      'start':start(-80), 'end':end(-80,35),  'pct':95, 'color':'#F79009'},
        {'id':'t33','type':'task','parent':'g3','name':'Power and Control Cabling 2200m',   'start':start(-73), 'end':end(-73,70),  'pct':58, 'color':'#F79009'},
        {'id':'t34','type':'task','parent':'g3','name':'SCADA and C&I System',              'start':start(-15), 'end':end(-15,56),  'pct':8,  'color':'#F79009'},

        {'id':'g4', 'type':'group',     'name':'Finishing and Commissioning',               'start':start(5),   'end':end(5,95),    'pct':0,  'color':'#1D2939'},
        {'id':'t41','type':'task','parent':'g4','name':'Finishing Works Tiling Cladding',   'start':start(5),   'end':end(5,35),    'pct':0,  'color':'#475467'},
        {'id':'t42','type':'task','parent':'g4','name':'Pre-Commissioning and Testing',     'start':start(40),  'end':end(40,35),   'pct':0,  'color':'#475467'},
        {'id':'t43','type':'task','parent':'g4','name':'Commissioning and Performance Test','start':start(75),  'end':end(75,22),   'pct':0,  'color':'#475467'},

        {'id':'m1', 'type':'milestone', 'name':'Practical Completion',                      'start':start(97),  'end':start(97),    'pct':0,  'color':'#9E77ED'},
    ]

    db.session.add(GanttData(project_id=pid, tasks=json.dumps(tasks)))
    db.session.commit()
    print('  Gantt  -- 20 tasks (5 groups + milestone) seeded')


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    with app.app_context():
        owner = User.query.filter_by(email='mohamadalabasi2001@gmail.com').first() \
             or User.query.first()

        if not owner:
            print('ERROR: No users found. Register first via http://localhost:5000/register')
            sys.exit(1)

        print('Creating demo project for user: %s (%s)\n' % (owner.username, owner.email))

        proj = create_project(owner.id)

        print('\nSeeding all modules...\n')
        seed_dc(proj.id, proj.code)
        seed_submittals(proj.id, proj.code)
        seed_dr(proj.id, proj.code)
        seed_lbt(proj.id, proj.code)
        seed_financial(proj.id)
        seed_gantt(proj.id)

        print('\n' + '='*55)
        print('  Project created:  [%d] APS - Auxiliary Pump Station' % proj.id)
        print('  Owner:            %s' % owner.username)
        print('='*55)
        print('  1. Open http://localhost:5000/dashboard')
        print('  2. Click "APS - Auxiliary Pump Station - Phase 2"')
        print('  3. Use the sidebar to open any module')
        print('='*55 + '\n')


if __name__ == '__main__':
    main()
