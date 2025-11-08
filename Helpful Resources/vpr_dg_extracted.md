# Extracted VPR Guide (source: Helpful Resources\vpr_dg.pdf)

_Extracted at 2025-11-08T01:54:51.895392Z_

Virtual Patient Record (VPR) 1.0

Developer’s Guide

July 2022

Department of Veterans Affairs (VA)

Office of Information and Technology (OIT)

Development, Security, and Operations (DSO)

Author

Virtual Patient
Record (VPR)
Development Team

Virtual Patient
Record (VPR)
Development Team

Revision History

Date

Revision  Description

07/05/2022  1.5

11/03/2021  1.4

Updates:
•  Table 56: Updated "Display Name" and
"Primary Source Sub/File#" columns for
these entries: VPR DEL FAMILY HX,
VPR DEL HF VACC REFUSAL, VPR
DEL ICR (new), VPR DEL PTF, VPR
DEL SOCIAL HX, VPR DEL TIU
DOCUMENT, VPR DEL V CPT, VPR
DEL V EXAM, VPR DEL V POV, VPR
DEL VACCINATION, VPR ELIGIBILITY
(new), VPR ICR ADMINISTRATION
(new), VPR ICR CONTRAINDICATION
(new), VPR ICR EVENT (new), VPR ICR
EXTENSION (new), VPR ICR
OBSERVATION (new), VPR ICR
REFUSAL (new), and VPR IMM
MANUFACTURER (new).

•  Updated Section 5.2.3.2, "Encounters

(PCE):" XTMP check times.

•  Updated Figure 5: Added VPR ICR

EVENT.

•  Updated Section 5.5.2, "Inquire to Entity

File Option:" Figure 6.

•  Added Section 5.7, "Call To Populate:"

Added sub-sections and figures.

Updates:
•  Table 34: Added the locationName and

locationUid entries.

•  Table 36: Added the displayOrder and

vuid entries.

•  Table 37: Added the instructions and

orderUid entries.

•  Table 46: Added the parent entry.
•  Table 47: Added the service entry.
•  Table 52: Deleted cpt entry.
•  Table 56: Added the VPR DEL FAMILY

HX, VPR DEL HF VACC REFUSAL, VPR
DEL PTF, VPR DEL SOCIAL HX, VPR
DEL TIU DOCUMENT, VPR DEL V CPT,
VPR DEL V EXAM, VPR DEL V POV,
VPR DEL VACCINATION, and VPR

Virtual Patient Record (VPR) 1.0
Developer’s Guide

ii

July 2022

Date

Revision  Description

Author

03/26/2021  1.3

Virtual Patient
Record (VPR)
Development Team

TEXT ONLY entries.

•  Table 58: Added the TIU DOCUMENT

ACTION EVENT entry.

•  Added Sections 5.2.3, “Tasked Events,”
and 5.5.1, “VPR CONTAINER (#560.1)
File.”

•  Updated Sections 5.2: Added second

paragraph, 5.2.2: Clarified first sentence,
5.3, 5.4, 5.4.1, and 5.5.2: Added option
names.

•  Updated Figure 6.
•  Section 5.4: Added API details.
•  Updated Section 5.5: Intro text.
•  Added Section 5.6, “Monitoring and

Troubleshooting.”

Updates:
•  Updated “How to Use this Manual”

section.

•  Section 5: VPR is currently populating 21

of the 30 SDA containers
•  Section 5.1: Add intro text.
•  Table 56: Corrected column title, delete
some entries and added the following
entries: VPR ADMISSION MOVEMENT,
VPR EDP CODE, VPR EDP
EXTENSION, VPR EDP LOG, VPR LAB
FACILITY, VPR MAS MOVEMENT
TYPE, VPR MAS TRANSACTION TYPE,
VPR MDD PROCEDURE, VPR
PACKAGE, VPR PRF DBRS RECORD,
VPR PRF HISTORY, VPR REFERRING
PROVIDER, VPR SCH ADM
EXTENSION, VPR VACC HF ADMIN,
VPR VACC HF EXT, VPR VACC HF
REFUSAL, VPR VCPT EXTENSION,
VPR VFILE DELETE, VPR VISIT STUB,
and VPR WARD LOCATION.

•  Table 57: Deleted an entry.
•  Table 58: Added the following entries: DG
PTF ICD DIAGNOSIS NOTIFIER, DG SA
FILE ENTRY NOTIFIER, DGPF PRF
EVENT, GMRA VERIFY DATA, and WV
PREGNANCY STATUS CHANGE
EVENT.

Virtual Patient Record (VPR) 1.0
Developer’s Guide

iii

July 2022

Date

Revision  Description

Author

06/13/2019  1.2

04/24/2019  1.1

VPR Development
Team

VPR Development
Team

•  Section 5.3: added link to Section 5.2.
•  Section 5.3.2: Updated intro text.
•  Section 5.3.3: Updated bulleted list and

example.

•  Deleted some content and an entry.
•  Section 5.5, “Generating Online

Documentation:” Updated intro text.
•  Section 5.5.1: Updated title and intro text.

Updates for Patch VPR*1.0*10 and
VPR*1.0*14:
•  Section 5, “HealthShare Interface.”
•  Section 5.1, “Entity File VPR Entries.”
•  Renamed/Updated Section 5.2, “Data

Update Events.”

•  Renamed/Updated Section 5.3, “VPR

Subscription File and Indexes.”

•  Renamed/Updated Section 5.4, “VPRHS

Utilities.”

•  Renumbered/Updated Section 5.4.1, “
•

.”

Updates for Patch VPR*1.0*8 and
VPR*1.0*14:
•  Updated stakeholders in the “Intended

Audience” section.

•  Added Section 1.1, “Purpose.”
•  Updated Section 1.2.
•  Moved Section 1.5, “Formatted Data,” to

follow Section 1.4.

•  Added explanatory text to Section 2.
•  Updated Sections 2.1 and 2.2.
•  Added the following “placeholder”

sections for future content:

o  Section 5, “HealthShare Interface.”
o  Section 5.1, “Entity (#1.5) File

VPR Entries.”

o  Section 5.2, “File 560 and AVPR

and ANEW Indices.”

o  Section 5.3, “Protocol Events.”
o  Section 5.4, “Generating Online

Documentation.”

Virtual Patient Record (VPR) 1.0
Developer’s Guide

iv

July 2022

Date

Revision  Description

Author

09/25/2018  1.0

Updates for Patch VPR*1.0*8:
•  Created a new, separate Developer’s

VPR Development
Team

08/21/2018  0.13

08/03/2015  0.12

06/29/2015  0.11

01/16/2015  0.10

Guide (this manual).

•  Moved other content to a new, separate

Technical Manual.

•  Updated document to follow current
documentation standards and style
guidelines.

Updates for Patch VPR*1.0*7:
Added new data elements to tables.
Pages: 25, 31-32, 51-52, 60, 63-64, 67, 78-
80.

Updates for Patch VPR*1.0*5:
Moved ICRs to end, and data element lists
from Routine section to new Appendix A & B.
Pages: 7, 10, 21-87.

Updates for Patch VPR*1.0*5:
•  Removed Patch descriptions.
•  Updated Data Domains, ICRs, and

Checksums.

Pages: 4-5, 8-9, 11-56.

Updates for Patch VPR*1.0*4:
•  Updated the VPR*1.0*4 Data Domain

section to include Consults.

•  Updated Routines section to include

VPRDGMRC and VPRDPSO.
•  Updated the External Relationships

section with changes to the ^USC(8932.1
ICB number

•  Updated checksums for VPRDGMRC and

VPRDPSO.
Pages: 6, 12, 43-44.

VPR Development
Team

VPR Development
Team

VPR Development
Team

VPR Development
Team

01/07/2015  0.09

0.08

01/02/2015
to
01/06/2015

Updates for Patch VPR*1.0*4:
Updated the checksum for VPRDTST to
reflect a last-minute change; Page: 45.

VPR Development
Team

Updates for Patch VPR*1.0*4:
•  Updated dates in page footers and on the

VPR Development
Team

cover page; Pages: All.

•  Added a prerequisite instruction for
installing VPR*1.0*4; Page: 4.

Virtual Patient Record (VPR) 1.0
Developer’s Guide

v

July 2022

Date

Revision  Description

Author

0.07

09/11/2013
to
10/11/2013

07/24/2013  0.06

•  Added a section describing VPR*1.0*4;

Pages: 7-8.

•  Added two new ICRs to the External
Relationships section; Page: 13.
•  Added a new routine (VPRTST) to the

routine table; Page 41.

•  Updated checksums; Pages: 45-46.
•  Added a new option (VPR TEST XML)
and new examples for VPR TEST XML
and VPR TEST JSON; Pages: 47–50.

Updates for Patch VPR*1.0*2:
•  Updated Title-page fonts to meet end-

user documentation standards.

•  Updated revision date.
•  Updated footer to include package name
(re end-user documentation standards).

•  Addressed reviewer suggestions and

comments.

•  Added an installation and a software-

availability section to provide information
about how to retrieve software and
documentation (re end-user
documentation standards).

•  Added a legal-disclaimers section (re end-

user documentation standards).

•  Corrected errors in the routines section;

updated checksums.

Pages: All.

Updates for Patch VPR*1.0*2:
•  Updated title to reflect new patch.
•  Updated Overview to add JSON

information.

•  Added a new (Formatted Data) section to

discuss data formatting.

•  Added patch information for VPR*1.0*2.
•  Added JSON remote procedure call

information.

•  Added JSON routines.
•  Corrected capitalization in routines table.
•  Added a JSON example placeholder.
•  Added JSON checksums.

VPR Development
Team

VPR Development
Team

Virtual Patient Record (VPR) 1.0
Developer’s Guide

vi

July 2022

Date

Revision  Description

Author

07/30/2012  0.05

06/13/2012  0.04

05/18/2012  0.03

•  Updated the glossary section.
Pages: All.

Updates for Patch VPR*1.0*1:
Updated checksum for VPRDPSOR; Page
27.

Updates for Patch VPR*1.0*1:
•  Updated Clinical Procedures ICRs in
Relationships, renumbered the table,
increased row height when necessary;
Pages 5-7.

•  Changed revised date; Pages 5-7.
•  Fixed typo; Page 11.

Updates for Patch VPR*1.0*1:
Added a paragraph about the VPR proxy;
Page 2.

VPR Development
Team

VPR Development
Team

VPR Development
Team

05/15/2012  0.02

Updates for Patch VPR*1.0*1:
•  Changed header colors from blue to

VPR Development
Team

black.

•  Corrected formatting issues.
•  Added hyperlinks to revision history.
•  Updated Overview to reflect changes with

NwHIN.

•  Added new extract routines for Clinical
Observations, Clinical Procedures,
Insurance, Exams, Skin Tests, Patient
Education.

•  Renamed Pharmacy Extract Medications.
•  Renamed Pharmacy Inpatient extract to

Inpatient Meds.

•  Renamed Pharmacy Outpatient Extract

Outpatient Meds.

•  Added Non-VA Meds and IV
Fluids/Infusions extracts.

•  Added section for Implementation &

Maintenance.

•  Added section for patch description.
•  Modified list of new routines.
•  Updated Routines List with new and

modified extract routines.

•  Added section for Security Keys.

Virtual Patient Record (VPR) 1.0
Developer’s Guide

vii

July 2022

Date

Revision  Description

Author

•  Updated External relationships table.
•  Added section for Files.
•  Updated Routine List table with

new/changed routines and reordered
elements alphabetically.

•  Removed elements predecessor,

successor, code from VPRDPL routine
because they were never populated.
Added elements acknowledgement [m],
provider, and service to VPRDOR routine.

•  Added element category to VPRDPXHF.
•  Added element encounter to VPRDXIM

routine.

•  Added elements clinicStop, provider,
and type to VPRDSDAM routine
(clinicStop was inadvertently missed in
the previous version of this TM).

•  Added elements category, images and

parent to VPRDTIU routine.
•  Updated Checksums table.
•  Added Options section.
•  Added a Glossary section.
Pages: All.

08/08/2011  0.01

VPR Version 1.0 Release. Initial document.

VPR Development
Team

Virtual Patient Record (VPR) 1.0
Developer’s Guide

viii

July 2022

Table of Contents

Revision History ............................................................................................................... ii

List of figures ................................................................................................................. xiii

List of Tables ................................................................................................................. xiii

Orientation ..................................................................................................................... xvi

1

2.4

2.4.1

2.3.1

2.1
2.2
2.3

Introduction ......................................................................................... 1
Purpose .......................................................................................................... 1
1.1
System Overview .......................................................................................... 1
1.2
1.3
Enhancements ............................................................................................... 1
1.4  Background ................................................................................................... 1
Formatted Data .............................................................................................. 2
1.5
2  Remote Procedure Calls ..................................................................... 3
VPR GET CHECKSUM ................................................................................... 4
VPR DATA VERSION ..................................................................................... 4
VPR GET PATIENT DATA ............................................................................. 4
VPR TEST XML Option ........................................................................... 8
VPR GET PATIENT DATA JSON .................................................................. 9
VPR TEST JSON Option ...................................................................... 11
3  XML Tables ........................................................................................ 14
3.1  Allergy/Adverse Reaction Tracking (GMRA) ............................................. 14
3.2  Clinical Observations (MDC) ...................................................................... 15
3.3  Clinical Procedures (MC) ............................................................................ 16
3.4  Clinical Reminders (PXRM) ........................................................................ 18
3.5  Consult/Request Tracking (GMRC) ........................................................... 19
Functional Independence Measurements (RMIM) .................................... 21
3.6
Integrated Billing (IB) .................................................................................. 23
3.7
Laboratory (LR) ........................................................................................... 24
3.8
Accessions ............................................................................................ 26
Panels ................................................................................................... 28
3.9  Orders (OR) .................................................................................................. 30
3.10  Patient Care Encounter (PX) ...................................................................... 32
3.10.1  Exams ................................................................................................... 32
3.10.2  Education Topics .................................................................................. 33
3.10.3  Health Factors ....................................................................................... 34
3.10.4
Immunizations ....................................................................................... 35
3.10.5  Skin Tests ............................................................................................. 37

3.8.1
3.8.2

Virtual Patient Record (VPR) 1.0
Developer’s Guide

ix

July 2022

4

3.11  Patient Record Flags (DGPF) ..................................................................... 38
3.12  Pharmacy (PS) ............................................................................................. 39
Inpatient (Unit Dose) Medications ......................................................... 39
3.12.1
IV Fluids (Infusions) .............................................................................. 42
3.12.2
3.12.3  Outpatient Medications ......................................................................... 44
3.12.4  Non-VA Medications ............................................................................. 47
3.13  Problem List (GMPL) ................................................................................... 50
3.14  Radiology/Nuclear Medicine (RA) .............................................................. 51
3.15  Registration (DPT) ....................................................................................... 53
3.16  Scheduling (SDAM) ..................................................................................... 57
3.17  Surgery (SR) ................................................................................................ 59
3.18  Text Integration Utilities (TIU) .................................................................... 60
3.19  Visits/PCE (PX) ............................................................................................ 63
3.20  Vital Measurements (GMV) ......................................................................... 66
JSON Tables ...................................................................................... 67
4.1  Allergy/Adverse Reaction Tracking (GMRA) ............................................. 67
4.2  Clinical Observations (MDC) ...................................................................... 68
4.3  Clinical Procedures (MDC) ......................................................................... 69
4.4  Consult/Request Tracking (GMRC) ........................................................... 70
4.5
Laboratory (LR) ........................................................................................... 72
4.6  Orders (OR) .................................................................................................. 74
Patient Care Encounter (PX) ...................................................................... 75
4.7
4.7.1  CPT Procedures ................................................................................... 75
Exams ................................................................................................... 76
4.7.2
4.7.3
Education Topics .................................................................................. 77
4.7.4  Health Factors ....................................................................................... 78
Immunizations ....................................................................................... 79
4.7.5
Purpose of Visit ..................................................................................... 80
4.7.6
Skin Tests ............................................................................................. 81
4.7.7
Pharmacy (PS) ............................................................................................. 82
4.8.1  Medications ........................................................................................... 82
Infusions ................................................................................................ 85
4.8.2

4.8

Virtual Patient Record (VPR) 1.0
Developer’s Guide

x

July 2022

5.3

Problem List (GMPL) ................................................................................... 87
4.9
4.10  PTF (DG) ....................................................................................................... 88
4.11  Radiology/Nuclear Medicine (RA) .............................................................. 89
4.12  Registration (DPT) ....................................................................................... 90
4.13  Scheduling (SDAM) ..................................................................................... 93
4.14  Surgery (SR) ................................................................................................ 94
4.15  Text Integration Utilities (TIU) .................................................................... 96
4.16  Visits/PCE (PX) ............................................................................................ 98
4.17  Vital Measurements (GMV) ....................................................................... 100
5  HealthShare Interface ..................................................................... 102
5.1
Entity File VPR Entries .............................................................................. 103
5.2  Data Update Events .................................................................................. 110
Protocol Events ................................................................................... 110
5.2.1
5.2.2  MUMPS Index ..................................................................................... 112
Tasked Events .................................................................................... 112
5.2.3
5.2.3.1  Patient Demographics ........................................................... 112
5.2.3.2  Encounters (PCE) .................................................................. 112
5.2.3.3  Documents (TIU) ................................................................... 113
VPR Subscription File and Indexes ......................................................... 113
VPR Subscription File ......................................................................... 113
ANEW Index ....................................................................................... 114
AVPR Index ........................................................................................ 114
VPRHS Utilities .......................................................................................... 115
$$ON^VPRHS: System Monitoring On/Off.......................................... 115
5.4.1.1  Example ................................................................................. 115
EN^VPRHS(): Subscribe a Patient ...................................................... 115
5.4.2.1  Example ................................................................................. 116
5.4.3  UN^VPRHS(): Unsubscribe a Patient ................................................. 116
5.4.3.1  Example ................................................................................. 116
$$SUBS^VPRHS(): Subscription Status of a Patient .......................... 117
5.4.4.1  Example ................................................................................. 117
$$VALID^VPRHS(): Validation of a Patient for HealthShare .............. 118
5.4.5.1  Example ................................................................................. 118
POST^VPRHS(): Add Record to AVPR Index for Uploading .............. 119
5.4.6.1  Example ................................................................................. 120
5.4.7  NEW^VPRHS(): Add Patient to ANEW Index for Subscribing ............ 120
5.4.7.1  Example ................................................................................. 120
5.4.8  DEL^VPRHS(): Remove Nodes from ANEW or AVPR Upload Index . 121
5.4.8.1  Example ................................................................................. 121
5.4.9  GET^VPRHS(): Retrieve Patient Data for ECR ................................... 122

5.3.1
5.3.2
5.3.3

5.4.1

5.4.2

5.4.4

5.4.5

5.4.6

5.4

Virtual Patient Record (VPR) 1.0
Developer’s Guide

xi

July 2022

5.4.9.1  Examples ............................................................................... 123
5.4.10  TEST^VPRHS(): Test SDA Extract ..................................................... 125
5.4.10.1 Example ................................................................................. 126
5.5  Generating Online Documentation .......................................................... 127
VPR CONTAINER (#560.1) File ......................................................... 127
Inquire to Entity File Option ................................................................. 130
5.6  Monitoring and Troubleshooting ............................................................. 132
VPR HealthShare Utilities [VPR HS MENU] Menu ............................. 133
5.6.1.1  Encounter Transmission Task Monitor [VPR HS TASK

5.5.1
5.5.2

5.6.1

5.6.2

MONITOR] Option ................................................................. 134
5.6.1.2  SDA Upload List Monitor [VPR HS SDA MONITOR] Option.. 136
5.6.1.3  Add Records to Upload List [VPR HS PUSH] Option ............ 137
5.6.1.4  Enable Data Monitoring [VPR HS ENABLE] Option .............. 138
Test/Audit VPR Functions [VPR HS TESTER] Menu .......................... 138
5.6.2.1  Test SDA Extracts [VPR HS TEST] Option............................ 140
5.6.2.2  SDA Upload List Monitor [VPR HS SDA MONITOR] Option.. 141
5.6.2.3  Data Upload List Log [VPR HS LOG] Option ......................... 141
5.6.2.4  Encounter Transmission Task Monitor [VPR HS TASK

MONITOR] Option ................................................................. 142
5.6.2.5  Inquire to Patient Subscriptions [VPR HS PATIENTS] Option143
5.7  Call To Populate ........................................................................................ 144
VPRZCTP ........................................................................................... 144
5.7.1.1  Examples ............................................................................... 146

5.7.1

Virtual Patient Record (VPR) 1.0
Developer’s Guide

xii

July 2022

List of figures

Figure 1: VPR GET PATIENT DATA RPC—Sample Returned XML-Formatted Data .... 6
Figure 2: VPR TEST XML Option—Sample Returned Output ......................................... 8
Figure 3: VPR GET PATIENT DATA JSON RPC—Sample Returned JSON-Formatted

Data ...................................................................................................................... 10
Figure 4: VPR TEST JSON Option—Sample Returned Output .................................... 11
Figure 5: Print File Entries Option—Displaying the VPR CONTAINER (#560.1) File

Contents .............................................................................................................. 128
Figure 6: Print an Entity Option—Displaying Entities in a Readable Format ............... 130
Figure 7: HealthShare Interface Manager [VPR HS MGR] Menu ................................ 132
Figure 8: VPR HealthShare Utilities [VPR HS MENU] Menu ....................................... 133
Figure 9: Encounter Transmission Task Monitor [VPR HS TASK MONITOR] Option—

System Prompts and User Entries ...................................................................... 135

Figure 10: SDA Upload List Monitor [VPR HS SDA MONITOR] Option—System

Prompts and User Entries ................................................................................... 136

Figure 11: Add Records to Upload List [VPR HS PUSH] Option—System Prompts and

User Entries ........................................................................................................ 137

Figure 12: Enable Data Monitoring [VPR HS ENABLE] Option—System Prompts and

User Entries ........................................................................................................ 138
Figure 13: Test/Audit VPR Functions [VPR HS TESTER] Menu ................................. 138
Figure 14: Test SDA Extracts [VPR HS TEST] Option—System Prompts and User

Entries ................................................................................................................. 140

Figure 15: Data Upload List Log [VPR HS LOG] Option—System Prompts and User

Entries ................................................................................................................. 142

Figure 16: Inquire to Patient Subscriptions [VPR HS PATIENTS] Option—System

Prompts and User Entries ................................................................................... 143
Figure 17: CTP by Domain Utility―Sample Results ................................................... 147
Figure 18: CTP by Domain: CNT Utility―Sample Results .......................................... 148
Figure 19: CTP by Patient Utility―Sample Results ..................................................... 149
Figure 20: CTP by ID Utility―Sample Results ............................................................ 150
Figure 21: Sample CTP Routine―Finding Documents in the TIU DOCUMENT (#8925)

File affected by the Patch .................................................................................... 151

List of Tables

Table 1: Documentation Symbol Descriptions ............................................................. xviii
Table 2: VPR Remote Procedure Calls ........................................................................... 3
Table 3: RPC: VPR GET PATIENT DATA —Allergy/Adverse Reaction Tracking (GMRA)
Elements Returned ............................................................................................... 14

Virtual Patient Record (VPR) 1.0
Developer’s Guide

xiii

July 2022

Table 4: RPC: VPR GET PATIENT DATA—Clinical Observations (MDC) Elements

Returned ............................................................................................................... 15

Table 5: RPC: VPR GET PATIENT DATA—Clinical Procedures (MC) Elements

Returned ............................................................................................................... 16

Table 6: RPC: VPR GET PATIENT DATA—Clinical Reminders (PXRM) Elements

Returned ............................................................................................................... 18

Table 7: RPC: VPR GET PATIENT DATA—Consult/Request Tracking (GMRC)

Elements Returned ............................................................................................... 19

Table 8: RPC: VPR GET PATIENT DATA—Functional Independence Measurements

(RMIM) Elements Returned .................................................................................. 21
Table 9: RPC: VPR GET PATIENT DATA—Integrated Billing (IB) Elements Returned 23
Table 10: RPC: VPR GET PATIENT DATA—Laboratory (LR) Elements Returned ...... 24
Table 11: RPC: VPR GET PATIENT DATA—Accessions Elements Returned ............. 26
Table 12: RPC: VPR GET PATIENT DATA—Panels Elements Returned .................... 28
Table 13: VPR GET PATIENT DATA—Orders (OR) Elements Returned ..................... 30
Table 14: VPR GET PATIENT DATA—Exams Elements Returned .............................. 32
Table 15: VPR GET PATIENT DATA—Education Topics Elements Returned ............. 33
Table 16: VPR GET PATIENT DATA—Health Factors Elements Returned .................. 34
Table 17: VPR GET PATIENT DATA—Immunizations Elements Returned .................. 35
Table 18: VPR GET PATIENT DATA—Skin Tests Elements Returned ........................ 37
Table 19: VPR GET PATIENT DATA—Patient Record Flags (DGPF) Elements

Returned ............................................................................................................... 38

Table 20: VPR GET PATIENT DATA—Inpatient (Unit Dose) Medications Elements

Returned ............................................................................................................... 39
Table 21: VPR GET PATIENT DATA—IV Fluids (Infusions) Elements Returned ......... 42
Table 22: VPR GET PATIENT DATA—Outpatient Medications Elements Returned .... 44
Table 23: VPR GET PATIENT DATA—Non-VA Medications Elements Returned ........ 47
Table 24: VPR GET PATIENT DATA—Problem List (GMPL) Elements Returned ....... 50
Table 25: VPR GET PATIENT DATA—Radiology/Nuclear Medicine (RA) Elements

Returned ............................................................................................................... 51
Table 26: VPR GET PATIENT DATA—Registration (DPT) Elements Returned ........... 53
Table 27: VPR GET PATIENT DATA—Scheduling (SDAM) Elements Returned ......... 57
Table 28: VPR GET PATIENT DATA—Surgery (SR) Elements Returned .................... 59
Table 29: VPR GET PATIENT DATA—Text Integration Utilities (TIU) Elements

Returned ............................................................................................................... 61
Table 30: VPR GET PATIENT DATA—Visits/PCE (PX) Elements Returned ................ 63
Table 31: VPR GET PATIENT DATA—Vital Measurements (GMV) Elements Returned66
Table 32: RPC: VPR GET PATIENT DATA JSON—Allergy/Adverse Reaction Tracking

(GMRA) Elements Returned ................................................................................. 67

Table 33 RPC: VPR GET PATIENT DATA JSON—Clinical Observations (MDC)

Elements Returned ............................................................................................... 68

Virtual Patient Record (VPR) 1.0
Developer’s Guide

xiv

July 2022

Table 34: RPC: VPR GET PATIENT DATA JSON—Clinical Procedures (MDC)

Elements Returned ............................................................................................... 69

Table 35: RPC: VPR GET PATIENT DATA JSON—Consult/Request Tracking (GMRC)

Elements Returned ............................................................................................... 70

Table 36: RPC: VPR GET PATIENT DATA JSON—Laboratory (LR) Elements Returned72
Table 37: RPC: VPR GET PATIENT DATA JSON—Orders (OR) Elements Returned . 74
Table 38: RPC: VPR GET PATIENT DATA JSON—CPT Procedures Elements

Returned ............................................................................................................... 75
Table 39: RPC: VPR GET PATIENT DATA JSON—Exams Elements Returned .......... 76
Table 40: RPC: VPR GET PATIENT DATA JSON—Education Topics Elements

Returned ............................................................................................................... 77
Table 41: RPC: VPR GET PATIENT DATA JSON—Health Factors Elements Returned78
Table 42: RPC: VPR GET PATIENT DATA JSON—Immunizations Elements Returned79
Table 43: RPC: VPR GET PATIENT DATA JSON—Purpose of Visit Elements Returned80
Table 44: RPC: VPR GET PATIENT DATA JSON—Skin Tests Elements Returned .... 81
Table 45: RPC: VPR GET PATIENT DATA JSON—Medications Elements Returned .. 82
Table 46: RPC: VPR GET PATIENT DATA JSON—Infusions Elements Returned ...... 85
Table 47: RPC: VPR GET PATIENT DATA JSON—Problem List (GMPL) Elements

Returned ............................................................................................................... 87
Table 48: RPC: VPR GET PATIENT DATA JSON—PTF (DG) Elements Returned ..... 88
Table 49: RPC: VPR GET PATIENT DATA JSON—Radiology/Nuclear Medicine (RA)

Elements Returned ............................................................................................... 89

Table 50: RPC: VPR GET PATIENT DATA JSON—Registration (DPT) Elements

Returned ............................................................................................................... 90

Table 51: RPC: VPR GET PATIENT DATA JSON—Scheduling (SDAM) Elements

Returned ............................................................................................................... 93
Table 52: RPC: VPR GET PATIENT DATA JSON—Surgery (SR) Elements Returned 94
Table 53: RPC: VPR GET PATIENT DATA JSON—Text Integration Utilities (TIU)

Elements Returned ............................................................................................... 96

Table 54: RPC: VPR GET PATIENT DATA JSON—Visits/PCE (PX) Elements Returned98
Table 55: RPC: VPR GET PATIENT DATA JSON—Vital Measurements (GMV)

Elements Returned ............................................................................................. 100
Table 56: VPR Entities ................................................................................................ 103
Table 57: VPR HL7 Event Protocols and Associated Listeners .................................. 110
Table 58: VPR Non-HL7 Event Protocols and Associated Listeners ........................... 111
Table 59: VPR MUMPS Cross Reference Listeners ................................................... 112
Table 60: VPR HS MGR Menu Options ...................................................................... 132
Table 61: VPR HealthShare Utilities Menu Options .................................................... 133
Table 62: Test/Audit VPR Functions [VPR HS TESTER] Menu Options ..................... 139

Virtual Patient Record (VPR) 1.0
Developer’s Guide

xv

July 2022

Orientation

How to Use this Manual
The Virtual Patient Record (VPR) Developer’s Guide provides advice and instruction about the
use of the following RPCs:

•  VPR GET PATIENT DATA

•  VPR GET PATIENT DATA JSON

This manual also describes the VPR interface with HealthShare.

  REF: For VPR installation instructions in the VistA environment see the Virtual Patient
Record (VPR) Installation Guide and any national patch description of the patch being
released.

Intended Audience
The intended audience of this manual is all key stakeholders. The stakeholders include the
following:

•  Development, Security, and Operations (DSO)—VistA legacy development teams who
use the VPR RPCs; specifically, Veterans Health Information Exchange (VHIE) and
Joint Legacy Viewer (JLV).

•  System Administrators—System administrators at Department of Veterans Affairs (VA)
sites who are responsible for computer management and system security on the VistA M
Servers.

•

Information Security Officers (ISOs)—Personnel at VA sites responsible for system
security.

•  Product Support (PS).

Virtual Patient Record (VPR) 1.0
Developer’s Guide

xvi

July 2022

Disclaimers
Software Disclaimer
This software was developed at the Department of Veterans Affairs (VA) by employees of the
Federal Government in the course of their official duties. Pursuant to title 17 Section 105 of the
United States Code this software is not subject to copyright protection and is in the public
domain. VA assumes no responsibility whatsoever for its use by other parties, and makes no
guarantees, expressed or implied, about its quality, reliability, or any other characteristic. We
would appreciate acknowledgement if the software is used. This software can be redistributed
and/or modified freely provided that any derivative works bear some notice that they are derived
from it, and any modified versions bear some notice that they have been modified.

  CAUTION: To protect the security of VistA systems, distribution of this software
for use on any other computer system by VistA sites is prohibited. All requests
for copies of Kernel for non-VistA use should be referred to the VistA site’s local
Office of Information Field Office (OIFO).

Documentation Disclaimer
This manual provides an overall explanation of and the functionality contained in Virtual Patient
Record (VPR) 1.0; however, no attempt is made to explain how the overall VistA programming
system is integrated and maintained. Such methods and procedures are documented elsewhere.
We suggest you look at the various VA Internet and Intranet Websites for a general orientation to
VistA. For example, visit the Office of Information and Technology (OIT) VistA Development
Intranet website.

  DISCLAIMER: The appearance of any external hyperlink references in this

manual does not constitute endorsement by the Department of Veterans Affairs
(VA) of this Website or the information, products, or services contained therein.
The VA does not exercise any editorial control over the information you find at
these locations. Such links are provided and are consistent with the stated
purpose of this VA Intranet Service.

Virtual Patient Record (VPR) 1.0
Developer’s Guide

xvii

July 2022

Documentation Conventions
This manual uses several methods to highlight different aspects of the material:

•  Various symbols are used throughout the documentation to alert the reader to special

information. Table 1 gives a description of each of these symbols:

Table 1: Documentation Symbol Descriptions

Symbol

Description

NOTE / REF: Used to inform the reader of general information including
references to additional reading material.

CAUTION / RECOMMENDATION / DISCLAIMER: Used to caution the
reader to take special notice of critical information.

•  Descriptive text is presented in a proportional font (as represented by this font).

•  Conventions for displaying TEST data in this document are as follows:

o  The first three digits (prefix) of any Social Security Numbers (SSN) begin with either

“000” or “666”.

o  Patient and user names are formatted as follows:

  <Application Name/Abbreviation/Namespace>PATIENT,<N>
  <Application Name/Abbreviation/Namespace>USER,<N>

Where:
  <Application Name/Abbreviation/Namespace> is defined in the Approved

Application Abbreviations document.

  <N> represents the first name as a number spelled out and incremented with each

new entry.

For example, in Virtual Patient Record (VPR) test patient and user names would be
documented as follows:

  VPRPATIENT,ONE; VPRPATIENT,TWO; VPRPATIENT,THREE; …

VPRPATIENT,14; etc.

  VPRUSER,ONE; VPRUSER,TWO; VPRUSER,THREE; … VPRUSER,14; etc.

Virtual Patient Record (VPR) 1.0
Developer’s Guide

xviii

July 2022

•  “Snapshots” of computer online displays (i.e., screen captures/dialogues) and computer
source code, if any, are shown in a non-proportional font and enclosed within a box:
o  User’s responses to online prompts are bold typeface and sometimes highlighted in

yellow (e.g., <Enter>).

o  Emphasis within a dialogue box is bold typeface and highlighted in blue

(e.g., STANDARD LISTENER: RUNNING).

o  Some software code reserved/key words are bold typeface with alternate color font.
o  References to “<Enter>” within these snapshots indicate that the user should press
the Enter key on the keyboard. Other special keys are sometimes represented within
< > angle brackets. For example, pressing the PF1 key can be represented as pressing
<PF1>.

o  Author’s comments are displayed in italics or as “callout” boxes.

  NOTE: Callout boxes refer to labels or descriptions usually enclosed within a

box, which point to specific areas of a displayed image.

•  This manual refers to the MUMPS (M) programming language. Under the 1995

American National Standards Institute (ANSI) standard, M is the primary name of the
MUMPS programming language, and MUMPS is considered an alternate name. This
manual uses the name M.

•  All uppercase is reserved for the representation of M code, variable names, or the formal
name of options, field/file names, security keys, and RPCs (e.g., VPR GET PATIENT
DATA).

  NOTE: Other software code (e.g., Delphi/Pascal and Java) variable names and

file/folder names can be written in lower or mixed case.

Documentation Navigation
This document uses Microsoft® Word’s built-in navigation for internal hyperlinks. To add Back
and Forward navigation buttons to your toolbar, do the following:

1.  Right-click anywhere on the customizable Toolbar in Word (not the Ribbon section).

2.  Select Customize Quick Access Toolbar from the secondary menu.

3.  Select the drop-down arrow in the “Choose commands from:” box.

4.  Select All Commands from the displayed list.

5.  Scroll through the command list in the left column until you see the Back command

(green circle with arrow pointing left).

Virtual Patient Record (VPR) 1.0
Developer’s Guide

xix

July 2022

6.  Select/Highlight the Back command and select Add to add it to your customized toolbar.

7.  Scroll through the command list in the left column until you see the Forward command

(green circle with arrow pointing right).

8.  Select/Highlight the Forward command and select Add to add it to your customized

toolbar.

9.  Select OK.

You can now use these Back and Forward command buttons in your Toolbar to navigate back
and forth in your Word document when clicking on hyperlinks within the document.

  NOTE: This is a one-time setup and is automatically available in any other Word

document once you install it on the Toolbar.

How to Obtain Technical Information Online
Exported VistA M Server-based software file, routine, and global documentation can be
generated through the use of Kernel, MailMan, and VA FileMan utilities.

  NOTE: Methods of obtaining specific technical information online is indicated where

applicable under the appropriate topic.

REF: For further information, see the VA FileMan Technical Manual.

Help at Prompts
VistA M Server-based software provides online help and commonly used system default
prompts. Users are encouraged to enter question marks at any response prompt. At the end of the
help display, you are immediately returned to the point from which you started. This is an easy
way to learn about any aspect of the software.

Obtaining Data Dictionary Listings
Technical information about VistA M Server-based files and the fields in files is stored in data
dictionaries (DD). You can use the List File Attributes [DILIST] option on the Data
Dictionary Utilities [DI DDU] menu in VA FileMan to print formatted data dictionaries.

  REF: For details about obtaining data dictionaries and about the formats available, see
the “List File Attributes” section in the “File Management” section in the VA FileMan
Advanced User Manual.

Virtual Patient Record (VPR) 1.0
Developer’s Guide

xx

July 2022

Assumptions
This manual is written with the assumption that the reader is familiar with the following:

•  VistA computing environment:

o  Kernel—VistA M Server software
o  VA FileMan data structures and terminology—VistA M Server software

•  Microsoft Windows environment

•  M programming language

Reference Materials
 Readers who wish to learn more about Virtual Patient Record (VPR) should consult the
following:

•  Virtual Patient Record (VPR) Installation Guide

•  Virtual Patient Record (VPR) Technical Manual

•  Virtual Patient Record (VPR) Developer’s Guide (this manual)

VistA documentation is made available online in Microsoft Word format and in Adobe Acrobat
Portable Document Format (PDF). The PDF documents must be read using the Adobe Acrobat
Reader, which is freely distributed by Adobe® Systems Incorporated at: http://www.adobe.com/

VistA software documentation can be downloaded from the VA Software Document Library
(VDL) at: http://www.va.gov/vdl/

  REF: VPR manuals are located on the VDL at:

https://www.va.gov/vdl/application.asp?appid=197

VistA documentation and software can also be downloaded from the Product Support (PS)
Anonymous Directories.

Virtual Patient Record (VPR) 1.0
Developer’s Guide

xxi

July 2022

Introduction

1
1.1  Purpose
The purpose of this document is to provide technical information about the Virtual Patient
Record (VPR) 1.0 software, specifically for developer use.

1.2  System Overview
VPR 1.0 was originally developed as a part of the Health Informatics Initiative’s (hi2’s). It has
been expanded to support VA’s interfaces to InterSystems’ Health Connect (HC) and
HealthShare (HS).

VPR extracts patient data from domains at a local Veterans Health Information Systems and
Technology Architecture (VistA) site to provide a cached view of the patient chart. It provides
normalized fields with common field names and data structures across domains.

VPR includes four remote procedure calls (RPCs) that do the following:

•  Extract data from VistA in Extensible Markup Language (XML) format.

•  Extract VistA data in JavaScript Object Notation (JSON) format.

•  Calculates checksums for data returned via the XML or JSON RPC.

•  Returns the current VPR RPC version number.

1.3  Enhancements
VPR Patch VPR*1*8 extends the Virtual Patient Record (VPR) application, to provide a new
method of retrieving patient health data from a VistA database.

VA FileMan Patch DI*22.2*9 released a new VA FileMan utility that provides the ability to map
VistA files and fields to other data models and extract that data as XML or JSON objects. Patch
VPR*1*8 populates the ENTITY (#1.5) file to map VistA data elements to InterSystems'
Summary Data Architecture (SDA) model and use the supported calls to retrieve the requested
data.

Patch VPR*1*8 also installs a mechanism to monitor clinical data events in VistA, to enable
retrieval of updated information as a patient's data changes. This patch adds new PROTOCOL
(#101) file entries and links to appropriate clinical application events; the file and record
numbers modified will be collected in the VPR SUBSCRIPTION (#560) file until retrieved and
updated.

1.4  Background
The VPR RPC for XML-formatted data extraction was initially installed in the Nationwide
Health Information Network (NwHIN) namespace, which was called NHIN. The NwHIN client
used most of the VPR’s extract routines in production to get and share data. After this initial
installation, VPR RPCs were installed in the VPR’s own (VPR) namespace and renumbered as
VPR Version 1.0. NwHIN could continue to use the extract routines in its NHIN namespace, but

Virtual Patient Record (VPR) 1.0
Developer’s Guide

1

July 2022

would need to access VPR 1.0, or subsequent versions, to take advantage of future extract
routine enhancements.

  NOTE: After the VPR package installed its RPCs in its own (VPR) namespace with
VPR 1.0, NwHIN began to use VPR 1.0 to take advantage of future extract-routine
enhancements. The Virtual Lifetime Electronic Record (VLER) and Joint Legacy Viewer
(JLV) are currently the primary users of the RPCs.

1.5  Formatted Data
VPR provides XML- and JSON-formatted data to support web applications that transmit data
between themselves, servers, and users’ browsers.

As its name suggests, XML uses markup to structure and serialize data. This human- and
machine-readable format enjoys widespread use as a means of exchanging both text-based
documents and structured data.

  REF: Figure 1 contains a snippet of XML-formatted data.

JSON is also a human- and machine-readable data-interchange format; however, its creator
focused on making it a vehicle for transmitting structured data, rather than narrative documents.
Although it uses several JavaScript notation rules to represent structured data, JSON is
programming-language agnostic: JSON parser libraries are available for programming languages
that range from ActionScript to Visual Basic.

  REF: You can find a comprehensive list of available parser libraries on the JSON.org

website.

JSON supports four primitive and two structured data types:

•  Primitive data types:

o  Text strings (quotation-mark delimiters)
o  Numbers
o  Booleans
o  Null

•  Structured data types:

o  Objects
o  Arrays

Virtual Patient Record (VPR) 1.0
Developer’s Guide

2

July 2022

These data types provide a fluid (free-form) way to serialize data transmissions. For example,
developers can represent objects that encompass arrays and arrays that encompass objects. They
can also include non-significant white space around JSON’s structural elements (curly and block
brackets, colons, and commas) to enhance human readability.

  REF: Figure 3 contains a snippet of JSON-formatted data.

Like XML, JSON supports asynchronous JavaScript and XML (Ajax), which allows web
applications to send and receive data to and from web pages. As a result, both formats are viable
options for data interchanges involving web applications. Two notable cases in point are HMP,
which uses JSON-formatted data, and NwHIN, which uses XML-formatted data.

2  Remote Procedure Calls
Table 2 lists the RPCs released with VPR 1.0:

Table 2: VPR Remote Procedure Calls

Remote Procedure Call

M Entry Point

Category

VPR GET CHECKSUM

VPR DATA VERSION

CHECK^VPRDCRC  Supporting RPC

VERSION^VPRD

Supporting RPC

VPR GET PATIENT DATA

GET^VPRD

Data Extract RPC

VPR GET PATIENT DATA JSON

GET^VPRDJ

Data Extract RPC

The purpose of the VPR application is to serve VistA data to developers for use in GUI or Web
applications, formatted as XML or JSON. Because it does not store or manage any data of its
own, VPR has no direct user interface; its user interface consists of these RPCs. A developer can
call either the VPR GET PATIENT DATA or VPR GET PATIENT DATA JSON RPC to
retrieve data as XML or JSON respectively, based on the input parameters described below.
Specific input values and data returned for each clinical domain and format are described in
Sections 0, “

Virtual Patient Record (VPR) 1.0
Developer’s Guide

3

July 2022

XML Tables,” and 4 “JSON Tables.”

2.1  VPR GET CHECKSUM
The VPR GET CHECKSUM is a supporting RPC that retrieves data from VistA via
GET^VPRD or GET^VPRDJ and calls the VPRDCRC routine to perform CRC32
calculations. VPRDCRC then returns the calculations as checksum values. Use this RPC to
determine if patient data has changed since the last extract was performed.

2.2  VPR DATA VERSION
The VPR DATA VERSION is a supporting RPC that gets the value of the current VPR RPC
version and returns it as a string. Any application with the appropriate Integration Control
Registration (ICR) can use this RPC to extract the RPC version from VPR software.

2.3  VPR GET PATIENT DATA
The VPR GET PATIENT DATA is a data extract RPC that retrieves data from VistA and
returns it as XML in a ^TMP global. Applications with the appropriate ICRs can use this RPC to
extract data from VistA. Developers can specify input parameters to determine the types and
amounts of data the RPC will extract from VistA. Parameters include:

•

Internal entry number (IEN) from PATIENT (#2) file (optionally data file number [DFN]
or integration control number [ICN] for remote calls) [required parameter]

•  The kinds of data to extract, which may include:

o  Allergies and reactions
o  Appointments
o  Clinical Procedures (medicine and cardiology)
o  Consults
o  Demographics
o  Documents
o  Education topics
o  Exams
o  Flags (Patient Record Flags)
o  Functional Independence Measurements
o  Health Factors
o  Immunizations
o  Insurance policies
o  Labs (by accession, order or panel, or individual result)
o  Medications
o  Observations (CLiO)

Virtual Patient Record (VPR) 1.0
Developer’s Guide

4

July 2022

o  Orders
o  Problems
o  Procedures (includes Radiology, Surgery, and Clinical Procedures)
o  Radiology exams
o  Skin tests
o  Surgical procedures
o  Visits and encounters
o  Vitals
o  Wellness Reminders

(optional) The date and time from which to begin searching for data.

(optional) The date and time at which to end searching for data.

(optional) The maximum number of items to return per data type.

(optional, but TYPE must also be defined when used) The identifier of a single item to
return.

•

•

•

•

•  List of name-value pairs, further refining the search.

The output from this RPC is a text array formatted as XML in the temporary global
^TMP(“VPR”,$J,n).

Virtual Patient Record (VPR) 1.0
Developer’s Guide

5

July 2022

The text in Figure 1 contains a snippet of XML data returned in response to a VPR GET
PATIENT DATA RPC call for vitals measurements for VPRTestPatient, One:

Figure 1: VPR GET PATIENT DATA RPC—Sample Returned XML-Formatted Data

<vital>
<entered value='3050316.115625' />
<facility code='998' name='ABILENE (CAA)' />
<location code='158' name='7A GEN MED' />
<measurements>
<measurement id='14871' vuid='4500634' name='BLOOD PRESSURE' value='168/68'
high='210/110' low='100/60' />
<measurement id='14869' vuid='4500636' name='PULSE' value='72' high='120'
low='60' >
<qualifiers>
<qualifier name='RADIAL' vuid='4688678' />
</qualifiers>
</measurement>
<measurement id='14872' vuid='4500635' name='PAIN' value='1' />
<measurement id='14870' vuid='4688725' name='RESPIRATION' value='18'
high='30' low='8' >
<qualifiers>
<qualifier name='SPONTANEOUS' vuid='4688706' />
</qualifiers>
</measurement>
<measurement id='14868' vuid='4500638' name='TEMPERATURE' value='99'
units='F' metricValue='37.2' metricUnits='C' high='102' low='95' >
<qualifiers>
<qualifier name='ORAL' vuid='4500642' />
</qualifiers>
</measurement>
</measurements
<taken value='3050316.1' />
</vital>

  REF: To review the lists of data elements returned by the VPR GET PATIENT DATA

RPC, see the “

Virtual Patient Record (VPR) 1.0
Developer’s Guide

6

July 2022

XML Tables” section.

Virtual Patient Record (VPR) 1.0
Developer’s Guide

7

July 2022

2.3.1  VPR TEST XML Option
The View XML results [VPR TEST XML] option loops around its DOMAIN and PATIENT
prompts, making it easy for testers to display data for successive patients and domains. The
option asks for a start date, if the data domain supports date filtering; if testers provide a start
date, it also asks for a stop date. The option’s start and stop parameters enable testers to limit
data displays to a time-bound subset of available data. If testers do not provide a start date, the
option does not ask for a stop date and displays all available data for the patient and domain
testers specify.

Additional search filters may be entered, for domains that support them. If one of those domains
is selected, testers may also see “FILTER” and “VALUE” prompts. An “ID” prompt may also
appear, allowing a specific data item to be extracted and displayed. Testers can simply press
Enter through any of these filters they do not wish to apply, and execution falls through to the
extract and display.

Figure 2 is an example of the View XML results [VPR TEST XML] option, showing the data it
returns (the results are truncated, with extra spaces removed).

Figure 2: VPR TEST XML Option—Sample Returned Output

Select OPTION NAME: VPR TEST XML <Enter> View XML results
 View XML results
 Select PATIENT NAME: AVIVAPATIENT,TWENTYONE <Enter>       2-14-34
666000001
  YES     SC VETERAN                    PROVIDER,EIGHTEEN  PRIMARY CARE
TEAM2
  Enrollment Priority: GROUP 3   Category: IN PROCESS    End Date:
 Select DOMAIN: VITALS
 Select START DATE: 11-1-2014 <Enter> (NOV 01, 2014)
 Select STOP DATE: 11-1-2014 <Enter> (NOV 01, 2014)
 Select TOTAL #items: <Enter>
 <results version='1.02' timeZone='-0700' >
 <vitals total='1' >
 <vital>
 <entered value='3141103.143428' />
 <facility code='500D' name='SLC-FO HMP DEV' />
 <location code='23' name='GENERAL MEDICINE' />
 <measurements>
 <measurement id='53157' vuid='4500634' name='BLOOD PRESSURE'
value='128/66'
 units='mm[Hg]' high='210/110' low='100/60' />
 <measurement id='53161' vuid='4688724' name='HEIGHT' value='71'
units='in'
 metricValue='180.34' metricUnits='cm' />
 <measurement id='53160' vuid='4500636' name='PULSE' value='92'
units='/min'
 high='120' low='60' />
 <measurement id='53164' vuid='4500635' name='PAIN' value='2' />
 <measurement id='53163' vuid='4500637' name='PULSE OXIMETRY' value='95'
 units='%' high='100' low='50' />
 <measurement id='53159' vuid='4688725' name='RESPIRATION' value='16'
 units='/min' high='30' low='8' />
 <measurement id='53158' vuid='4500638' name='TEMPERATURE' value='98.5'

Virtual Patient Record (VPR) 1.0
Developer’s Guide

8

July 2022

 units='F' metricValue'53162' vuid='4500639' name='WEIGHT'

2.4  VPR GET PATIENT DATA JSON
The VPR GET PATIENT DATA JSON is a data extract RPC that retrieves data from VistA
and returns it as JSON-formatted documents in a ^TMP global. Applications with appropriate
ICRs can use this RPC to extract data from VistA. Developers can specify input parameters to
determine the types and amounts of data the RPC will extract from VistA by entering the
parameters as a list of name-value pairs. Some of the most commonly used parameters include:

•

IEN from PATIENT (#2) file (optionally DFN; ICN for remote calls) [required]

•  The kinds of data to extract, which may include:

o  Allergies and reactions
o  Appointments
o  Clinical Procedures (medicine and cardiology)
o  Consults
o  CPT procedures
o  Demographics
o  Documents
o  Education topics
o  Exams
o  Health Factors
o  Immunizations
o  Lab results
o  Medications
o  Observations (CLiO)
o  Orders
o  Problems
o  Purpose of visit (POV)
o  Radiology exams
o  Skin tests
o  Surgical procedures
o  Visits and admissions
o  Vitals

•  The date and time from which to begin searching for data [optional].

Virtual Patient Record (VPR) 1.0
Developer’s Guide

9

July 2022

•  The date and time at which to stop searching for data [optional].

•  The maximum number of items to return per data type [optional].

•  The identifier of a single item to return [optional, but TYPE must also be defined when

used].

•  Additional name-value pairs, further refining the search [optional].

The RPC’s output is a text array formatted as JSON in the temporary global
^TMP(“VPR”,$J,n).

Figure 3 contains a snippet of data returned in response to a VPR GET PATIENT DATA
JSON RPC call for vitals measurements for VPRTestPatient, One—the same patient and data
returned in the XML example (Figure 1).

Figure 3: VPR GET PATIENT DATA JSON RPC—Sample Returned JSON-Formatted Data

{"apiVersion":"1.01","params":{"domain":"DEV.HMPDEV.VAINNOVATIONS.US","sys
temId":"F484"},"data":{"updated":"20130718143517","totalItems":5,"items":[
{"displayName":"BP","facilityCode":"500D","facilityName":"SLC-FO HMP
DEV","high":"210\/110","kind":"Vital
Sign","localId":14871,"locationName":"7 WEST MEDICINE",
"locationUid":"urn:va:location:F484:158","low":"100\/60","observed":200503
161000,"result":"168\/68","resulted":20050316115625,"summary":"BLOOD
PRESSURE 168\/68mm[Hg]","typeCode":"urn:va:vuid:4500634","typeName":"BLOOD
PRESSURE","uid":"urn:va:F484:229:vital:14871","units":"mm[Hg]"}
,
{"displayName":"P","facilityCode":"500D","facilityName":"SLC-FO HMP
DEV","high":120,"kind":"Vital sign","localId":14869,"locationName":"7 WEST
MEDICINE","locationUid":"urn:va:location:F484:158","low":60,"observed":200
503161000,"qualifiers":[{"name":"RADIAL","vuid":4688678}],"result":72,"res
ulted":20050316115625,"summary":"PULSE 72
\/min","typeCode":"urn:va:vuid:4500636","typeName":"PULSE","uid":"urn:va:F
484:229:vital:14869","units":"\/min"}
,
{"displayName":"PN","facilityCode":"500D","facilityName":"SLC-FO HMP
DEV","kind":"Vital Sign","localId":14872,"locationName":"7 WEST
MEDICINE","locationUid":"urn:va:location:F484:158","observed":200503161000
,"result":1,"resulted":20050316115625,"summary":"PAIN 1
","typeCode":"urn:va:vuid:4500635","typeName":"PAIN","uid":"urn:va:F484:22
9:vital:14872","units":""}
,
{"displayName":"R","facilityCode":"500D","facilityName":"SLC-FO HMP
DEV","high":30,"kind":"Vital Sign","localId":14870,"locationName":"7 WEST
MEDICINE","locationUid":"urn:va:location:F484:158","low":8,"observed":2005
03161000,"qualifiers":[{"name":"SPONTANEOUS","vuid":4688706}],"result":18,
"resulted":20050316115625,"summary":"RESPIRATION 18
\/min","typeCode":"urn:va:vuid:4688725","typeName":"RESPIRATION","uid":"ur
n:va:F484:229:vital:14870","units":"\/min"}

Virtual Patient Record (VPR) 1.0
Developer’s Guide

10

July 2022

  REF: To review the lists of data elements returned by the VPR GET PATIENT DATA

JSON RPC, see the “JSON Tables” section.

2.4.1  VPR TEST JSON Option
The View JSON results [VPR TEST JSON] option loops around its DOMAIN and PATIENT
prompts, making it easy for testers to display data for successive patients and domains. The
option asks for a start date. If testers provide a start date, it also asks for a stop date. The option’s
start and stop parameters enable testers to limit data displays to a time-bound subset of available
data. If testers do not provide a start date, the option does not ask for a stop date and displays all
available data for the patient and domain testers specify.

Figure 4 is an example of the View JSON results [VPR TEST JSON] option, showing the data it
returns (the results are truncated, with extra spaces removed).

Figure 4: VPR TEST JSON Option—Sample Returned Output

Select OPTION NAME: VPR TEST JSON <Enter> View JSON results
View JSON results
Select PATIENT NAME: AVIVAPATIENT,TWENTYONE      2-14-
34    666000001    YES    SC VETERAN    PROVIDER,EIGHTEEN  PRIMARY CARE
TEAM2
Enrollment Priority: GROUP 3 Category: IN PROCESS    End Date:
Select DOMAIN: VITAL
Select START DATE: 11-1-2014 <Enter> (NOV 01, 2014)
Select STOP DATE: 11-1-2014 <Enter> (NOV 01, 2014)
Select TOTAL #items: <Enter>
{"apiVersion":"1.03","params":{"domain":"DEV.HMPDEV.VAINNOVATIONS.US","sys
temId":"F484"},
"data":{"updated":"20150106112207","totalItems":8,"items":[
{"displayName":"BP","facilityCode":"500D","facilityName":"SLC-FO HMP
DEV","high"
:"210\/110","kind":"Vital Sign","localId":53157,"locationName":"GENERAL
MEDICINE
","locationUid":"urn:va:location:F484:23","low":"100\/60","observed":20141
101190
3,"result":"128\/66","resulted":20141103143428,"summary":"BLOOD PRESSURE
128\/66
mm[Hg]","typeCode":"urn:va:vuid:4500634","typeName":"BLOOD
PRESSURE","uid":"urn
:va:vital:F484:237:53157","units":"mm[Hg]"}
,
{"displayName":"HT","facilityCode":"500D","facilityName":"SLC-FO HMP
DEV","kind"
:"Vital Sign","localId":53161,"locationName":"GENERAL
MEDICINE","locationUid":"u
rn:va:location:F484:23","metricResult":180.34,"metricUnits":"cm","observed
":2014
11011903,"result":71,"resulted":20141103143428,"summary":"HEIGHT 71
in","typeCod
e":"urn:va:vuid:4688724","typeName":"HEIGHT","uid":"urn:va:vital:F484:237:
53161"

Virtual Patient Record (VPR) 1.0
Developer’s Guide

11

July 2022

,"units":"in"}
, {"displayName":"P","facilityCode":"500D","facilityName":"SLC-FO HMP
DEV","high":
120,"kind":"Vital Sign","localId":53160,"locationName":"GENERAL
MEDICINE","locationUid":"urn:va:location:F484:23","low":60,"observed"vital
:F484:237:53160","units":"\/min"}
,
{"displayName":"PN","facilityCode":"500D","facilityName":"SLC-FO HMP
DEV","kind"
:"Vital Sign","localId":53164,"locationName":"GENERAL
MEDICINE","locationUid":"u
rn:va:location:F484:23","observed":201411011903,"result":2,"resulted":2014
110314
3428,"summary":"PAIN 2
","typeCode":"urn:va:vuid:4500635","typeName":"PAIN","uid
":"urn:va:vital:F484:237:53164","units":""}
,
{"displayName":"PO2","facilityCode":"500D","facilityName":"SLC-FO HMP
DEV","high
":100,"kind":"Vital Sign","localId":53163,"locationName":"GENERAL
MEDICINE","loc
ationUid":"urn:va:location:F484:23","low":50,"observed":201411011903,"resu
lt":95
,"resulted":20141103143428,"summary":"PULSE OXIMETRY
95 %","typeCode":"urn:va:vu
id:4500637","typeName":"PULSE
OXIMETRY","uid":"urn:va:vital:F484:237:53163","uni
ts":"%"}
,
{"displayName":"R","facilityCode":"500D","facilityName":"SLC-FO HMP
DEV","high":
30,"kind":"Vital Sign","localId":53159,"locationName":"GENERAL
MEDICINE","locati
onUid":"urn:va:location:F484:23","low":8,"observed":201411011903,"result":
16,"re
sulted":20141103143428,"summary":"RESPIRATION 16
\/min","typeCode":"urn:va:vuid:
4688725","typeName":"RESPIRATION","uid":"urn:va:vital:F484:237:53159","uni
ts":"\
/min"}
,
{"displayName":"T","facilityCode":"500D","facilityName":"SLC-FO HMP
DEV","high":
102,"kind":"Vital Sign","localId":53158,"locationName":"GENERAL
MEDICINE","locat
ionUid":"urn:va:location:F484:23","low":95,"metricResult":36.9,"metricUnit
s":"C"
,"observed":201411011903,"result":98.5,"resulted":20141103143428,"summary"
:"TEMP
ERATURE 98.5
F","typeCode":"urn:va:vuid:4500638","typeName":"TEMPERATURE","uid":
"urn:va:vital:F484:237:53158","units":"F"}
,
{"displayName":"WT","facilityCode":"500D","facilityName":"SLC-FO HMP
DEV","kind"
:"Vital Sign","localId":53162,"locationName":"GENERAL
MEDICINE","locationUid":"u

Virtual Patient Record (VPR) 1.0
Developer’s Guide

12

July 2022

rn:va:location:F484:23","metricResult":46.36,"metricUnits":"kg","observed"
:20141
1011903,"result":102,"resulted":20141103143428,"summary":"WEIGHT 102
lb","typeCo
de":"urn:va:vuid:4500639","typeName":"WEIGHT","uid":"urn:va:vital:F484:237
:53162
","units":"lb"}
]}}

Virtual Patient Record (VPR) 1.0
Developer’s Guide

13

July 2022

3  XML Tables
The tables in this section list the data elements returned by the VPR GET PATIENT DATA
RPC. All input parameters are optional to refine the extract, except for TYPE. All searches are
performed reverse-chronologically to return the most recent data, unless otherwise noted.

3.1  Allergy/Adverse Reaction Tracking (GMRA)
Input parameters:

“reactions” [required]

TYPE

[optional]

START

VA FileMan date to filter on “entered”

STOP

MAX

ID

VA FileMan date to filter on “entered”

Use not recommended, as reactions are not sorted

PATIENT ALLERGIES (#120.8) file IEN

FILTER

none

Table 3: RPC: VPR GET PATIENT DATA —Allergy/Adverse Reaction Tracking (GMRA) Elements
Returned

Elements

assessment

comment *

drugClass *

drugIngredient *

entered

facility

id

localCode

mechanism

name

Attributes

Content

value

id

enteredBy

entered

not done or nka

number

NEW PERSON (#200) Name

VA FileMan date.time

commentType

O or E (observed or error)

commentText

string

name

vuid

name

vuid

value

code

name

value

value

value

value

VA DRUG CLASS (#50.605) Classification

VA DRUG CLASS (#50.605) VUID

DRUG INGREDIENTS (#50.416) Name

DRUG INGREDIENTS (#50.416) VUID

VA FileMan date.time

INSTITUTION (#4) Station Number

INSTITUTION (#4) Name

PATIENT ALLERGIES (#120.8) ien

VA FileMan variable pointer

ALLERGY, PHARMACOLOGIC, or
UNKNOWN

string

Virtual Patient Record (VPR) 1.0
Developer’s Guide

14

July 2022

Elements

reaction *

removed

severity

source

type

verified

vuid

* = may be multiple

Attributes

name

vuid

value

value

value

value

value

value

Content

string

number

boolean (1 or 0)

MILD, MODERATE, or SEVERE

O or H (observed or historical)

any combination of DFO

any combination of DRUG, FOOD, OTHER

VUID number

3.2  Clinical Observations (MDC)
TYPE
Input parameters:

“observations” [required]

[optional]

START

VA FileMan date to filter on “observed”

STOP

MAX

ID

VA FileMan date to filter on “observed”

use with caution, as search is performed chronologically

OBS (#704.117) file ID (#.01) value

FILTER

none

Table 4: RPC: VPR GET PATIENT DATA—Clinical Observations (MDC) Elements Returned

Elements

bodySite

comment

entered

facility

id

location

method

Attributes

Content

code

name

value

value

code

name

value

code

name

code

VUID number

string

string

VA FileMan date.time

INSTITUTION (#4) Station Number

INSTITUTION (#4) Name

OBS (#704.117) ID

HOSPITAL LOCATION (#44) ien

HOSPITAL LOCATION (#44) Name

VUID number

Virtual Patient Record (VPR) 1.0
Developer’s Guide

15

July 2022

Elements

Attributes

Content

name

observed

position

product

quality

range

status

units

value

vuid

name

value

value

code

name

code

name

code

name

value

value

code

name

value

value

string

string

VA FileMan date.time

VUID number

string

VUID number

string

VUID number

string

Unknown, Normal, Out of Bounds Low,
Out of Bounds High, Low, High

Verified

VUID number

string

string

VUID number

3.3  Clinical Procedures (MC)
Input parameters:

TYPE

“clinicalProcedures” [required]

[optional]

START

VA FileMan date to filter on “dateTime”

STOP

MAX

ID

VA FileMan date to filter on “dateTime”

number of most recent procedures to return

variable pointer to CP data file/item

FILTER(“text”)  1 or 0, to include “content” text of report

Table 5: RPC: VPR GET PATIENT DATA—Clinical Procedures (MC) Elements Returned

Elements

category

consult

dateTime

document *

Attributes

Content

value

value

value

id

CP

CONSULT (#123) ien

VA FileMan date.time

TIU DOCUMENT (#8925) ien

Virtual Patient Record (VPR) 1.0
Developer’s Guide

16

July 2022

Elements

Attributes

Content

localTitle

nationalTitle

vuid

content

value

code

name

value

value

value

code

name

value

code

name

code

name

TIU DOCUMENT DEFINITION (#8925.1)
Name

TIU VHA ENTERPRISE STANDARD TITLE
(#8926.1)

VUID number

word-processing text

VISIT (#9000010) ien

INSTITUTION (#4) Station Number

INSTITUTION (#4) Name

boolean (1 or 0)

variable pointer

Normal, Abnormal, Borderline,
Incomplete, or Machine Resulted

HOSPITAL LOCATION (#44) ien

HOSPITAL LOCATION (#44) Name

string

ORDER (#100) ien

string

NEW PERSON (#200) ien

NEW PERSON (#200) Name

officePhone

NEW PERSON (#200) Office Phone

analogPager

NEW PERSON (#200) Voice Pager

fax

email

NEW PERSON (#200) Fax Number

NEW PERSON (#200) Email Address

taxonomyCode

PERSON CLASS (#8932.1) X12 Code

providerType

PERSON CLASS (#8932.1) Provider Type

classification

PERSON CLASS (#8932.1) Classification

specialization

PERSON CLASS (#8932.1) Area of
Specialization

service

value

value

NEW PERSON (#200) Service/Section

VA FileMan date.time

string

encounter

facility

hasImages

id

interpretation

location

name

order

provider

requested

status

Virtual Patient Record (VPR) 1.0
Developer’s Guide

17

July 2022

* = may be multiple

3.4  Clinical Reminders (PXRM)
Not all clinical reminders that may appear in CPRS will be available via this extract. Only the
nationally exported “wellness” reminders, those marked for Patient usage and shown in
MyHealtheVet, are processed and returned at run time.

Input parameters:

TYPE

“reminders” [required]

[optional]

START

STOP

MAX

ID

none

none

none

REMINDER DEFINITION (#811.9) file ien

FILTER

none

Table 6: RPC: VPR GET PATIENT DATA—Clinical Reminders (PXRM) Elements Returned

Elements

class

detail

due

facility

id

lastDone

name

status

summary

Attributes

Content

code

name

value

code

name

value

value

value

value

N

NATIONAL

word-processing text

VA FileMan date.time, DUE NOW, N/A, or
CNBD

INSTITUTION (#4) Station Number

INSTITUTION (#4) Name

REMINDER DEFINITION (#811.9) ien

VA FileMan date.time, or UNKNOWN

REMINDER DEFINITION (#811.9) Print
Name

DUE NOW, DUE SOON, NOT DUE,
RESOLVED, or N/A

word-processing text

Virtual Patient Record (VPR) 1.0
Developer’s Guide

18

July 2022

3.5  Consult/Request Tracking (GMRC)
Input parameters:

“consults” [required]

TYPE

[optional]

START

VA FileMan date to filter on “requested”

STOP

MAX

ID

VA FileMan date to filter on “requested”

number of most recent consult requests to return

REQUEST/CONSULTATION (#123) file IEN

FILTER(“text”)  1 or 0, to include “content” text of report

Table 7: RPC: VPR GET PATIENT DATA—Consult/Request Tracking (GMRC) Elements Returned

Elements

document *

facility

id

name

orderID

procedure

provider

Attributes

Content

id

localTitle

nationalTitle

vuid

content

code

name

value

value

value

value

code

name

TIU DOCUMENT (#8925) ien

TIU DOCUMENT DEFINITION (#8925.1)
Name

TIU VHA ENTERPRISE STANDARD
TITLE (#8926.1)

VUID number

word-processing text

INSTITUTION (#4) Station Number

INSTITUTION (#4) Name

REQUEST/CONSULTATION (#123) ien

string

ORDER (#100) ien

GMRC Procedure #123.3 Name or
“Consult”

NEW PERSON (#200) ien

NEW PERSON (#200) Name

officePhone

NEW PERSON (#200) Office Phone

analogPager

NEW PERSON (#200) Voice Pager

fax

email

NEW PERSON (#200) Fax Number

NEW PERSON (#200) Email Address

taxonomyCode

PERSON CLASS (#8932.1) X12 Code

providerType

PERSON CLASS (#8932.1) Provider Type

classification

PERSON CLASS (#8932.1)1
Classification

Virtual Patient Record (VPR) 1.0
Developer’s Guide

19

July 2022

Elements

Attributes

Content

specialization

service

code

name

system

value

value

value

value

value

value

value

PERSON CLASS (#8932.1) Area of
Specialization

NEW PERSON (#200 Service/Section

ICD code

ICD Description

ICD or 10D

word-processing text

VA FileMan date.time

string

REQUEST SERVICES (#123.5) Name

ORDER STATUS (#100.01) Name

C or P

string

provDx

reason

requested

result

service

status

type

urgency

* = may be multiple

Virtual Patient Record (VPR) 1.0
Developer’s Guide

20

July 2022

3.6  Functional Independence Measurements (RMIM)
The assessment scores are often entered by multiple clinicians. The set as a whole is not returned
until all 18 numeric scores are available. A sub-total for each section of scores will also then be
included.

Input parameters:

TYPE

“functionalMeasurements” [required]

[optional]

START

VA FileMan date to filter on “admitted”, chronologically

STOP

MAX

ID

VA FileMan date to filter on “admitted”, chronologically

Use not recommended, as measurements are not sorted

FUNCTIONAL INDEPENDENCE (#783) file IEN

FILTER(“text”)  1 or 0, to include “content” text of report

Table 8: RPC: VPR GET PATIENT DATA—Functional Independence Measurements (RMIM)
Elements Returned

Elements

Attributes

admitClass

admitted

assessment *

value

value

type

cognitiveScore

motorScore

totalScore

values

Content

1, 2, or 3

FileMan

admission, discharge, interim, follow
up, or goals

number, 5-35

number, 13-91

number, 18-126

number, 1-7

number, 1-7

number, 1-7

number, 1-7

number, 1-7

number, 1-7

number, 1-7

number, 1-7

number, 1-7

number, 1-7

number, 1-7

number, 1-7

eat

groom

bath

dressUp

dressLo

toilet

bladder

bowel

transChair

transToilet

transTub

locomWalk

Virtual Patient Record (VPR) 1.0
Developer’s Guide

21

July 2022

Elements

Attributes

Content

locomStair

number, 1-7

comprehend

number, 1-7

express

interact

problem

memory

number, 1-7

number, 1-7

number, 1-7

number, 1-7

walkMode

W, C, or B (walk, wheelchair, or both)

comprehendMode  A, V, or B (auditory, visual, or both)

expressMode

V, N, or B (vocal, non-vocal, or both)

care

case

discharged

value

value

value

document *

id

localTitle

nationalTitle

vuid

content

code

name

value

facility

id

impairmentGroup

value

interruption *

transfer

return

interruptionCode

value

name

onset

value

value

* = may be multiple

CONTINUUM OF CARE, ACUTE, or
SUBACUTE

number

VA FileMan date

TIU DOCUMENT (#8925) ien

TIU DOCUMENT DEFINITION
(#8925.1) Name

TIU VHA ENTERPRISE STANDARD
TITLE (#8926.1)

VUID number

word-processing text

INSTITUTION (#4) Station Number

INSTITUTION (#4) Name

FUNCTIONAL INDEPENDENCE
(#783) ien

string

VA FileMan date

VA FileMan date

string

Functional Independence Measurement

VA FileMan date

Virtual Patient Record (VPR) 1.0
Developer’s Guide

22

July 2022

3.7
Input parameters:

Integrated Billing (IB)
TYPE

“insurancePolicies” [required]

[optional]

START

STOP

MAX

ID

none

none

use not recommended, as policies are not sorted

none

FILTER(“status”) desired status codes, see ^IBBDOC for possible values

[default = “RB”]

Table 9: RPC: VPR GET PATIENT DATA—Integrated Billing (IB) Elements Returned

Elements

company

Attributes

Content

id

name

address

streetLine1

INSURANCE COMPANY (#36) ien

INSURANCE COMPANY (#36) Name

INSURANCE COMPANY (#36) Street
Address [1]

streetLine2

INSURANCE COMPANY (#36) Street
Address [2]

streetLine3

INSURANCE COMPANY (#36) Street
Address [3]

city

INSURANCE COMPANY (#36) City

stateProvince

INSURANCE COMPANY (#36) State

postalCode

INSURANCE COMPANY (#36) Zip

INSURANCE COMPANY (#36) Phone
Number

VA FileMan date.time

VA FileMan date.time

INSTITUTION (#4) Station Number

INSTITUTION (#4) Name

GROUP PLAN (#355.3) Group Name

string

DFN;company id;Group Plan (#355.3) ien

TYPE OF PLAN (#355.1) ien

TYPE OF PLAN (#355.1) Name

PATIENT, SPOUSE, NATURAL CHILD,

effectiveDate

expirationDate

facility

groupName

groupNumber

id

insuranceType

relationship

telecom

value

value

code

name

value

value

value

code

name

value

Virtual Patient Record (VPR) 1.0
Developer’s Guide

23

July 2022

Elements

Attributes

Content

EMPLOYEE, ORGAN DONOR, INJURED
PLAINTIFF, MOTHER, FATHER,
SIGNIFICANT OTHER, LIFE PARTNER,
or OTHER RELATIONSHIP

subscriber

id

name

string

string

3.8  Laboratory (LR)
Input parameters:

TYPE

“labs” [required]

[optional]

START

VA FileMan date to filter on “collected”

STOP

MAX

ID

VA FileMan date to filter on “collected”

number of most recent accessions to return

LAB DATA (#63) file IEN string

FILTER(“type”)  desired “type” code(s) [default = CH]

Table 10: RPC: VPR GET PATIENT DATA—Laboratory (LR) Elements Returned

Elements

collected

comment

facility

groupName

high

id

interpretation

labOrderID

localName

loinc

low

performingLab

provider

Attributes

Content

value

value

code

name

value

value

value

value

value

value

value

value

value

code

name

VA FileMan date.time

string

INSTITUTION (#4) Station Number

INSTITUTION (#4) Name

accession number string

string

LAB DATA (#63) ien string

L, L*, H, H*, or NULL

number

LAB TEST (#60) Print Name

LOINC code

string

string

NEW PERSON (#200) ien

NEW PERSON (#200) Name

Virtual Patient Record (VPR) 1.0
Developer’s Guide

24

July 2022

Elements

Attributes

Content

officePhone

NEW PERSON (#200) Office Phone

analogPager

NEW PERSON (#200) Voice Pager

fax

email

NEW PERSON (#200) Fax Number

NEW PERSON (#200) Email Address

taxonomyCode

PERSON CLASS (#8932.1) X12 Code

providerType

PERSON CLASS (#8932.1) Provider Type

classification

PERSON CLASS (#8932.1) Classification

specialization

PERSON CLASS (#8932.1) Area of
Specialization

service

NEW PERSON (#200) Service/Section

value

value

value

value

code

name

value

value

value

value

value

ORDER (#100) ien

string

VA FileMan date.time

COLLECTION SAMPLE (#62) Name

TOPOGRAPHY (#61) SNOMED Code

TOPOGRAPHY (#61) Name

completed or incomplete

LAB TEST (#60) Name

CH or MI

string

VUID number

orderID

result

resulted

sample

specimen

status

test

type

units

vuid

Virtual Patient Record (VPR) 1.0
Developer’s Guide

25

July 2022

3.8.1  Accessions
The same results can also be returned grouped by the accessioned specimen; this is the only Lab
domain that will return pathology data, and the recommended domain for retrieving
microbiology results.

Input parameters:

TYPE

“accessions” [required]

[optional]

START

VA FileMan date to filter on “collected”

STOP

MAX

ID

VA FileMan date to filter on “collected”

Number of most recent accessions to return

LAB DATA (#63) file IEN string

FILTER(“type”)  desired “type” codes

FILTER(“text”)  1 or 0, to include “content” text of report

Table 11: RPC: VPR GET PATIENT DATA—Accessions Elements Returned

Elements

collected

comment

document *

facility

groupName

id

labOrderID

name

pathologist

Attributes

Content

value

value

id

localTitle

VA FileMan date.time

string

TIU DOCUMENT (#8925) ien

TIU DOCUMENT DEFINITION (#8925.1)
Name

nationalTitle

TIU VHA ENTERPRISE STANDARD TITLE
(#8926.1)

vuid

content

code

name

value

value

value

value

code

name

VUID number

word-processing text

INSTITUTION (#4) Station Number

INSTITUTION (#4) Name

accession number string

LAB DATA (#63) ien string

number

ACCESSION (#68) Area

NEW PERSON (#200) ien

NEW PERSON (#200) Name

officePhone

NEW PERSON (#200) Office Phone

analogPager

NEW PERSON (#200) Voice Pager

Virtual Patient Record (VPR) 1.0
Developer’s Guide

26

July 2022

Elements

Attributes

Content

fax

email

NEW PERSON (#200) Fax Number

NEW PERSON (#200) Email Address

taxonomyCode

PERSON CLASS (#8932.1) X12 Code

providerType

PERSON CLASS (#8932.1) Provider Type

classification

PERSON CLASS (#8932.1) Classification

specialization

PERSON CLASS (#8932.1) Area of
Specialization

service

code

name

NEW PERSON (#200) Service/Section

NEW PERSON (#200) ien

NEW PERSON (#200) Name

officePhone

NEW PERSON (#200) Office Phone

analogPager

NEW PERSON (#200) Voice Pager

fax

email

NEW PERSON (#200) Fax Number

NEW PERSON (#200) Email Address

taxonomyCode

PERSON CLASS (#8932.1) X12 Code

providerType

PERSON CLASS (#8932.1) Provider Type

classification

PERSON CLASS (#8932.1) Classification

specialization

PERSON CLASS (#8932.1) Area of
Specialization

service

NEW PERSON (#200 Service/Section

value

value

code

name

value

value

id

test

result

VA FileMan date.time

COLLECTION SAMPLE (#62) Name

TOPOGRAPHY (#61) SNOMED Code

TOPOGRAPHY (#61) Name

completed or incomplete

CH, MI, CY, EM, SP, or AU

LAB DATA (#63) file ien string

LAB TEST (#60) Name

string

interpretation

L, L*, H, H*, or NULL

units

low

string

string

provider

resulted

sample

specimen

status

type

value *

Virtual Patient Record (VPR) 1.0
Developer’s Guide

27

July 2022

Elements

Attributes

high

Content

string

localName

LAB TEST (#60) Print Name

loinc

vuid

order

LOINC code

VUID number

ORDER (#100) ien

performingLab

string

* = may be multiple

3.8.2  Panels
Results can also be returned grouped by order or panel within an accession. Because Lab can
purge its order information, results are found by first searching the ORDER (#100) file then
retrieving the associated results from the LAB DATA (#63) file.

Input parameters:

TYPE

“panels” [required]

[optional]

START

VA FileMan date to filter on date order released

STOP

MAX

ID

VA FileMan date to filter on date order released

number of most recent orders to return

ORDER (#100) file IEN

FILTER(“type”)  desired “type” codes

Table 12: RPC: VPR GET PATIENT DATA—Panels Elements Returned

Attributes

Content

value

value

code

name

value

value

value

value

code

VA FileMan date.time

string

INSTITUTION (#4) Station Number

INSTITUTION (#4) Name

accession number string

ORDER (#100) ien

ORDER (#100) Package Reference string

LAB TEST (#60) Name

ORDER (#100) ien

Elements

collected

comment

facility

groupName

id

labOrderID

name

order

Virtual Patient Record (VPR) 1.0
Developer’s Guide

28

July 2022

Elements

Attributes

Content

provider

resulted

sample

specimen

status

type

value *

name

code

name

LAB TEST (#60) Name

NEW PERSON (#200) ien

NEW PERSON (#200) Name

officePhone

NEW PERSON (#200) Office Phone

analogPager

NEW PERSON (#200) Voice Pager

fax

email

NEW PERSON (#200) Fax Number

NEW PERSON (#200) Email Address

taxonomyCode

PERSON CLASS (#8932.1) X12 Code

providerType

PERSON CLASS (#8932.1) Provider Type

classification

PERSON CLASS (#8932.1) Classification

specialization

PERSON CLASS (#8932.1) Area of
Specialization

service

NEW PERSON (#200) Service/Section

value

value

code

name

value

value

id

test

result

VA FileMan date.time

COLLECTION SAMPLE (#62) Name

TOPOGRAPHY (#61) SNOMED Code

TOPOGRAPHY (#61) Name

completed or incomplete

CH or MI

LAB DATA (#63) file ien string

LAB TEST (#60) Name

string

interpretation

L, L*, H, H*, or NULL

units

low

high

string

string

string

localName

LAB TEST (#60) Print Name

loinc

vuid

LOINC code

VUID number

performingLab

string

* = may be multiple

Virtual Patient Record (VPR) 1.0
Developer’s Guide

29

July 2022

3.9  Orders (OR)
Most order views in CPRS include actions on orders as separate items; this extract returns only
the current snapshot of each order found, unless the view requested is specific to actions
(i.e., unsigned).

Input parameters:

TYPE

“orders” [required]

[optional]

START

VA FileMan date to filter on “released” or “entered”

STOP

MAX

ID

VA FileMan date to filter on “released” or “entered”

number of most recent orders to return

ORDER (#100) file IEN string

FILTER(“view”)  desired “view” code, see ^ORQ1 for possible values

[default = 6 (Released Orders), sorted by “released”]

Table 13: VPR GET PATIENT DATA—Orders (OR) Elements Returned

Elements

Attributes

Content

acknowledgement *

codingSystem

content

discontinued

entered

facility

group

id

location

name

code

name

date

code

name

date

by

byName

reason

value

code

name

value

value

code

name

code

NEW PERSON (#200) ien

NEW PERSON (#200) Name

VA FileMan date.time

string (national code)

CPT, NLT, or LNC

word-processing text

VA FileMan date.time

NEW PERSON (#200) ien

NEW PERSON (#200) Name

string

VA FileMan date.time

INSTITUTION (#4) Station Number

INSTITUTION (#4) Name

DISPLAY GROUP (#100.98) Short Name

ORDER (#100) ien string

HOSPITAL LOCATION (#44) ien

HOSPITAL LOCATION (#44) Name

ORDERABLE ITEMS (#101.43) ien

Virtual Patient Record (VPR) 1.0
Developer’s Guide

30

July 2022

Elements

Attributes

Content

provider

name

code

name

ORDERABLE ITEMS (#101.43) Name

NEW PERSON (#200) ien

NEW PERSON (#200) Name

officePhone

NEW PERSON (#200) Office Phone

analogPager

NEW PERSON (#200) Voice Pager

fax

email

NEW PERSON (#200) Fax Number

NEW PERSON (#200) Email Address

taxonomyCode

PERSON CLASS (#8932.1) X12 Code

providerType

PERSON CLASS (#8932.1) Provider Type

classification

PERSON CLASS (#8932.1) Classification

specialization

PERSON CLASS (#8932.1) Area of
Specialization

service

NEW PERSON (#200) Service/Section

released

resultID

service

signatureStatus

signed

signer

value

value

value

value

value

code

name

VA FileMan date.time

string (corresponds to “id” in other domains)

PACKAGE (#9.4) Prefix

ON CHART w/written orders,
ELECTRONIC, NOT SIGNED, NOT
REQUIRED, ON CHART w/printed orders,
NOT REQUIRED due to cancel/lapse,
SERVICE CORRECTION to signed order,
DIGITALLY SIGNED, or ON PARENT
order

VA FileMan date.time

NEW PERSON (#200) ien

NEW PERSON (#200) Name

officePhone

NEW PERSON (#200) Office Phone

analogPager

NEW PERSON (#200) Voice Pager

fax

email

NEW PERSON (#200) Fax Number

NEW PERSON (#200) Email Address

taxonomyCode

PERSON CLASS (#8932.1) X12 Code

providerType

PERSON CLASS (#8932.1) Provider Type

classification

PERSON CLASS (#8932.1) Classification

specialization

PERSON CLASS (#8932.1) Area of

Virtual Patient Record (VPR) 1.0
Developer’s Guide

31

July 2022

Elements

Attributes

Content

Specialization

service

NEW PERSON (#200) Service/Section

start

status

stop

type

vuid

value

code

name

vuid

value

value

value

VA FileMan date.time

ORDER STATUS (#100.01) Abbreviation

ORDER STATUS (#100.01) Name

ORDER STATUS (#100.01) VUID

VA FileMan date.time

DISPLAY GROUP (#100.98) Mixed Name

VUID number

* = may be multiple

3.10 Patient Care Encounter (PX)

  NOTE: All Patient Care Encounter (PCE) patient data file names all start with “V”,

which is short for VistA.

3.10.1  Exams
Input parameters:

TYPE

“exams” [required]

[optional]

START

VA FileMan date to filter on “dateTime”

STOP

MAX

ID

VA FileMan date to filter on “dateTime”

number of most recent exams to return

V EXAM (#9000010.13) file IEN

FILTER

none

Table 14: VPR GET PATIENT DATA—Exams Elements Returned

Elements

comment

dateTime

encounter

facility

Attributes

value

value

value

code

Content

string

VA FileMan date.time

VISIT (#9000010) ien

INSTITUTION (#4) Station Number

Virtual Patient Record (VPR) 1.0
Developer’s Guide

32

July 2022

Elements

Attributes

Content

id

name

result

name

value

value

value

INSTITUTION (#4) Name

V EXAM (#9000010.13) ien

EXAM (#9999999.15) Name

string

3.10.2  Education Topics
Input parameters:

TYPE

“educationTopics” [required]

[optional]

START

VA FileMan date to filter on “dateTime”

STOP

MAX

ID

VA FileMan date to filter on “dateTime”

number of most recent education instances to return

V PATIENT ED (#9000010.16) file IEN

FILTER

none

Table 15: VPR GET PATIENT DATA—Education Topics Elements Returned

Elements

comment

dateTime

encounter

facility

id

name

result

Attributes

value

value

value

code

name

value

value

value

Content

string

VA FileMan date.time

VISIT (#9000010) ien

INSTITUTION (#4) Station Number

INSTITUTION (#4) Name

V PATIENT ED (#9000010.16) ien

EDUCATION TOPICS (#9999999.09)
Name

string

Virtual Patient Record (VPR) 1.0
Developer’s Guide

33

July 2022

3.10.3  Health Factors
TYPE
Input parameters:

“healthFactors” [required]

[optional]

START

VA FileMan date to filter on “recorded”

STOP

MAX

ID

VA FileMan date to filter on “recorded”

number of most recent factors to return

V HEALTH FACTORS (#9000010.23) file IEN

FILTER

none

Elements

category

comment

encounter

facility

id

name

recorded

severity

Table 16: VPR GET PATIENT DATA—Health Factors Elements Returned

Attributes

Content

code

name

value

value

code

name

value

value

value

value

HEALTH FACTORS (#9999999.64) ien

HEALTH FACTORS (#9999999.64)
Category

string

VISIT (#9000010) ien

INSTITUTION (#4) Station Number

INSTITUTION (#4) Name

V HEALTH FACTORS (#9000010.23) ien

HEALTH FACTORS (#9999999.64) Factor

VA FileMan date.time

MINIMAL, MODERATE, or
HEAVY/SEVERE

Virtual Patient Record (VPR) 1.0
Developer’s Guide

34

July 2022

3.10.4  Immunizations
TYPE
Input parameters:

“immunizations” [required]

[optional]

START

VA FileMan date to filter on “administered”

STOP

MAX

ID

VA FileMan date to filter on “administered”

Number of most recent immunizations to return

V IMMUNIZATION (#9000010.11) file IEN

FILTER

none

Table 17: VPR GET PATIENT DATA—Immunizations Elements Returned

Elements

administered

bodySite

comment

contraindicated

cpt

cvx

documentedBy

dose

encounter

expirationDate

facility

id

location

lot

manufacturer

name

Attributes

Content

value

code

name

value

value

code

name

value

code

name

value

value

value

code

name

value

value

value

value

value

VA FileMan date.time

IMM ADMINISTRATION SITE (#920.3) HL7
Code

IMM ADMINISTRATION SITE (#920.3) Site

string

boolean (1 or 0)

CPT Code

CPT Short Name

CVX Code

NEW PERSON (#200) ien

NEW PERSON (#200) Name

string

VISIT (#9000010) ien

VA FileMan date.time

INSTITUTION (#4) Station Number

INSTITUTION (#4) Name

V IMMUNIZATION (#9000010.11) ien

HOSPITAL LOCATION (#44) Name

IMMUNIZATION LOT (#9999999.41) Lot
Number

IMMUNIZATION LOT (#9999999.41)
Manufacturer

IMMUNIZATION (#9999999.14) Name

Virtual Patient Record (VPR) 1.0
Developer’s Guide

35

July 2022

Elements

Attributes

Content

orderingProvider

provider

reaction

route

series

source

units

vis [m]

code

name

code

name

value

code

name

value

code

name

value

date

name

NEW PERSON (#200) ien

NEW PERSON (#200) Name

NEW PERSON (#200) ien

NEW PERSON (#200) Name

string

IMM ADMINISTRATION ROUTE (#920.2)
HL7 Code

IMM ADMINISTRATION ROUTE (#920.2)
Route

PARTIALLY COMPLETE, COMPLETE,
BOOSTER, SERIES 1-8

IMMUNIZATION INFO SOURCE (#920)
HL7 Code

IMMUNIZATION INFO SOURCE (#920)
Source

string

VA FileMan date

VACCINE INFORMATION STATEMENT
(#920) Name

editionDate

language

VA FileMan date

string

Virtual Patient Record (VPR) 1.0
Developer’s Guide

36

July 2022

3.10.5  Skin Tests
Input parameters:

TYPE

“skinTests” [required]

[optional]

START

VA FileMan date to filter on “dateTime”

STOP

MAX

ID

VA FileMan date to filter on “dateTime”

Number of most recent skin tests to return

V SKIN TEST (#9000010.12) file IEN

FILTER

none

Table 18: VPR GET PATIENT DATA—Skin Tests Elements Returned

Elements

comment

dateTime

encounter

facility

id

name

result

Attributes

value

value

value

code

name

value

value

value

Content

string

VA FileMan date.time

VISIT (#9000010) ien

INSTITUTION (#4) Station Number

INSTITUTION (#4) Name

V SKIN TEST (#9000010.12) ien

SKIN TEST (#9999999.28) Name

string

Virtual Patient Record (VPR) 1.0
Developer’s Guide

37

July 2022

3.11 Patient Record Flags (DGPF)
TYPE
Input parameters:

“flags” [required]

[optional]

START

STOP

MAX

ID

none

none

none

DFN~PRF variable pointer string

FILTER

none

Table 19: VPR GET PATIENT DATA—Patient Record Flags (DGPF) Elements Returned

Elements

approvedBy

assigned

category

content

document

id

name

origSite

ownSite

reviewDue

type

Attributes

Content

code

name

value

value

code

name

value

value

code

name

code

name

value

value

NEW PERSON (#200) ien

NEW PERSON (#200) Name

FileMan date.time

I (NATIONAL) or II (LOCAL)

word-processing text

TIU DOCUMENT (#8925) ien

TIU DOCUMENT DEFINITION (#8925.1)
Name

DFN~PRF variable pointer string

PRF NATIONAL FLAG (#26.15) or PRF
LOCAL FLAG (#26.11) Name

INSTITUTION (#4) Station Number

INSTITUTION (#4) Name

INSTITUTION (#4) Station Number

INSTITUTION (#4) Name

VA FileMan date

PRF TYPE (#26.16) Name

Virtual Patient Record (VPR) 1.0
Developer’s Guide

38

July 2022

3.12 Pharmacy (PS)
All meds may be requested by omitting any filters, but more commonly a single type of
medications is pulled at a time, as shown in the following tables. The PS API sorts meds by
expiration date and will include orders that expire on or after the START value but omit those
that do not begin until after the STOP value. As each type is processed in sequence, use of MAX
is discouraged with multiple types.

An alternate domain name is available for each med type that will instead run reverse-
chronologically on the ORDER (#100) file, filtering by the “ordered” date without regard to
medication type; thus, MAX may be safely used and return the most recent set of orders of the
desired type(s). Set TYPE to “pharmacy” to use this method instead.

3.12.1  Inpatient (Unit Dose) Medications
“meds” [required]
Input parameters:

TYPE

[optional]

START

VA FileMan date to filter on “expires”, chronologically

STOP

MAX

ID

VA FileMan date to filter on “expires”, chronologically

number of most recent inpatient med orders to return

ORDER (#100) file IEN

FILTER(“vaType”)  “I”

Table 20: VPR GET PATIENT DATA—Inpatient (Unit Dose) Medications Elements Returned

Elements

Attributes

Content

currentProvider

dose *

code

name

officePhone

analogPager

fax

email

NEW PERSON (#200) ien

NEW PERSON (#200) Name

NEW PERSON (#200) Office Phone

NEW PERSON (#200) Voice Pager

NEW PERSON (#200) Fax Number

NEW PERSON (#200) Email Address

taxonomyCode

PERSON CLASS (#8932.1) X12 Code

providerType

classification

specialization

service

dose

units

PERSON CLASS (#8932.1) Provider Type

PERSON CLASS (#8932.1) Classification

PERSON CLASS (#8932.1) Area of
Specialization

NEW PERSON (#200) Service/Section

string

string

Virtual Patient Record (VPR) 1.0
Developer’s Guide

39

July 2022

Elements

Attributes

unitsPerDose

noun

route

schedule

duration

conjunction

doseStart

doseStop

order

code

name

value

value

value

code

name

value

value

value

value

code

name

officePhone

analogPager

fax

email

facility

form

id

IMO

location

medID

name

ordered

orderID

orderingProvider

Content

number

string

MEDICATION ROUTES (#51.2)
Abbreviation

ADMINISTRATION SCHEDULE (#51.1)
Name

string

A, T, or E

VA FileMan date.time

VA FileMan date.time

ORDER (#100) ien

INSTITUTION (#4) Station Number

INSTITUTION (#4) Name

DOSAGE FORM (#50.606) Name

ORDER (#100) ien

boolean (1 or 0)

HOSPITAL LOCATION (#44) ien

HOSPITAL LOCATION (#44) Name

NON-VERIFIED ORDERS (#53.1)
ien_“P;I”, or UNIT DOSE ORDERS
(#55.06) subfile ien_“U;I”

PHARMACY ORDERABLE ITEM (#50.7)
Name, Form

VA FileMan date.time

ORDER (#100) ien

NEW PERSON (#200) ien

NEW PERSON (#200) Name

NEW PERSON (#200) Office Phone

NEW PERSON (#200) Voice Pager

NEW PERSON (#200) Fax Number

NEW PERSON (#200) Email Address

taxonomyCode

PERSON CLASS (#8932.1) X12 Code

providerType

PERSON CLASS (#8932.1) Provider Type

Virtual Patient Record (VPR) 1.0
Developer’s Guide

40

July 2022

Elements

Attributes

Content

classification

specialization

service

value

code

name

code

name

role

concentration

order

class

PERSON CLASS (#8932.1) Classification

PERSON CLASS (#8932.1) Area of
Specialization

NEW PERSON (#200) Service/Section

ORDER (#100) ien

NEW PERSON (#200) ien

NEW PERSON (#200) Name

DRUG (#50) ien

DRUG (#50) Generic Name

D

string

ORDER (#100) ien

code

VA DRUG CLASS (#50.605) Code

name

VA DRUG CLASS (#50.605) Classification

vaGeneric

vuid

code

VA DRUG CLASS (#50.605) VUID

VA GENERIC (#50.6) ien

name

VA GENERIC (#50.6) Name

vuid

code

VA GENERIC (#50.6) VUID

VA PRODUCT (#50.68) ien

name

VA PRODUCT (#50.68) Name

vuid

VA PRODUCT (#50.68) VUID

string

VA FileMan date.time

active, hold, historical, or not active

VA FileMan date.time

ORDER STATUS (#100.01) Name

I

vaProduct

value

value

value

value

value

value

parent

pharmacist

product *

sig

start

status

stop

vaStatus

vaType

* = may be multiple

Virtual Patient Record (VPR) 1.0
Developer’s Guide

41

July 2022

3.12.2  IV Fluids (Infusions)
Input parameters:

TYPE

“meds” [required]

[optional]

START

VA FileMan date to filter on “expires”, chronologically

STOP

MAX

ID

VA FileMan date to filter on “expires”, chronologically

Number of most recent infusion orders to return

ORDER (#100) file IEN

FILTER(“vaType”) “V”

Table 21: VPR GET PATIENT DATA—IV Fluids (Infusions) Elements Returned

Elements

Attributes

Content

currentProvider

dose *

facility

id

ivLimit

location

medID

code

name

officePhone

analogPager

fax

email

NEW PERSON (#200) ien

NEW PERSON (#200) Name

NEW PERSON (#200) Office Phone

NEW PERSON (#200) Voice Pager

NEW PERSON (#200) Fax Number

NEW PERSON (#200) Email Address

taxonomyCode

PERSON CLASS (#8932.1) X12 Code

providerType

classification

specialization

service

route

PERSON CLASS (#8932.1) Provider Type

PERSON CLASS (#8932.1) Classification

PERSON CLASS (#8932.1) Area of
Specialization

NEW PERSON (#200) Service/Section

MEDICATION ROUTES (#51.2)
Abbreviation

schedule

Administration Schedule #51.1 Name

code

name

value

value

code

name

value

INSTITUTION (#4) Station Number

INSTITUTION (#4) Name

ORDER (#100) ien

string

HOSPITAL LOCATION (#44) ien

HOSPITAL LOCATION (#44) Name

NON-VERIFIED ORDERS (#53.1)
ien_“P;I”, or IV ORDERS (#55.01) subfile
ien_“V;I”

Virtual Patient Record (VPR) 1.0
Developer’s Guide

42

July 2022

Elements

Attributes

Content

name

ordered

orderID

value

value

value

Pharmacy Orderable Item #50.7 Name,
Form

VA FileMan date.time

ORDER (#100) ien

orderingProvider

code

NEW PERSON (#200) ien

pharmacist

product *

name

officePhone

analogPager

fax

email

NEW PERSON (#200) Name

NEW PERSON (#200) Office Phone

NEW PERSON (#200) Voice Pager

NEW PERSON (#200) Fax Number

NEW PERSON (#200) Email Address

taxonomyCode

PERSON CLASS (#8932.1) X12 Code

providerType

classification

specialization

service

code

name

code

name

role

concentration

class

ordItem

vaGeneric

vaProduct

PERSON CLASS (#8932.1) Provider Type

PERSON CLASS (#8932.1) Classification

PERSON CLASS (#8932.1) Area of
Specialization

NEW PERSON (#200) Service/Section

NEW PERSON (#200) ien

NEW PERSON (#200) Name

DRUG (#50) ien

DRUG (#50) Generic Name

A or B

string

code

name

vuid

code

name

code

name

vuid

code

VA DRUG CLASS (#50.605) Code

VA DRUG CLASS (#50.605) Classification

VA DRUG CLASS (#50.605) VUID

PHARMACY ORDERABLE ITEM (#50.7)
ien

PHARMACY ORDERABLE ITEM (#50.7)
Name, Form

VA GENERIC (#50.6) ien

VA GENERIC (#50.6) Name

VA GENERIC (#50.6) VUID

VA PRODUCT (#50.68) ien

Virtual Patient Record (VPR) 1.0
Developer’s Guide

43

July 2022

Elements

Attributes

Content

name

vuid

VA PRODUCT (#50.68) Name

VA PRODUCT (#50.68) VUID

string

VA FileMan date.time

active, hold, historical, or not active

VA FileMan date.time

ORDER STATUS (#100.01) Name

V

rate

start

status

stop

vaStatus

vaType

value

value

value

value

value

value

* = may be multiple

3.12.3  Outpatient Medications
Input parameters:

TYPE

“meds” [required]

[optional]

START

VA FileMan date to filter on “expires”, chronologically

STOP

MAX

ID

VA FileMan date to filter on “expires”, chronologically

Number of most recent outpatient med orders to return

ORDER (#100) file IEN

FILTER(“vaType”) “O”

Table 22: VPR GET PATIENT DATA—Outpatient Medications Elements Returned

Elements

Attributes

Content

currentProvider

code

name

officePhone

analogPager

fax

email

NEW PERSON (#200) ien

NEW PERSON (#200) Name

NEW PERSON (#200) Office Phone

NEW PERSON (#200) Voice Pager

NEW PERSON (#200) Fax Number

NEW PERSON (#200) Email Address

taxonomyCode

PERSON CLASS (#8932.1) X12 Code

providerType

classification

specialization

PERSON CLASS (#8932.1) Provider Type

PERSON CLASS (#8932.1) Classification

PERSON CLASS (#8932.1) Area of

Virtual Patient Record (VPR) 1.0
Developer’s Guide

44

July 2022

Elements

Attributes

daysSupply

dose *

expires

facility

fill *

fillCost

fillsAllowed

fillsRemaining

form

id

lastFilled

location

service

value

dose

units

unitsPerDose

noun

route

schedule

duration

conjunction

doseStart

doseStop

value

code

name

fillDate

fillRouting

releaseDate

fillQuantity

fillDaysSupply

partial

value

value

value

value

value

value

code

name

Content

Specialization

NEW PERSON (#200) Service/Section

number

string

string

number

string

MEDICATION ROUTES (#51.2)
Abbreviation

ADMINISTRATION SCHEDULE (#51.1)
Name

string

A, T, or E

VA FileMan date.time

VA FileMan date.time

VA FileMan date

INSTITUTION (#4) Station Number

INSTITUTION (#4) Name

VA FileMan date

W, M, or C

VA FileMan date

number

number

boolean (1 or 0)

number

number

number

DOSAGE FORM (#50.606) Name

ORDER (#100) ien

VA FileMan date.time

HOSPITAL LOCATION (#44) ien

HOSPITAL LOCATION (#44) Name

Virtual Patient Record (VPR) 1.0
Developer’s Guide

45

July 2022

Elements

Attributes

Content

medID

value

name

ordered

orderID

value

value

value

PENDING OUTPATIENT ORDERS
(#52.41) ien_“P;O”, or PRESCRIPTION
(#52) file ien_“R;O”

PHARMACY ORDERABLE ITEM (#50.7)
Name, Form

VA FileMan date.time

ORDER (#100) ien

orderingProvider

code

NEW PERSON (#200) ien

pharmacist

prescription

product *

name

officePhone

analogPager

fax

email

NEW PERSON (#200) Name

NEW PERSON (#200) Office Phone

NEW PERSON (#200) Voice Pager

NEW PERSON (#200) Fax Number

NEW PERSON (#200) Email Address

taxonomyCode

PERSON CLASS (#8932.1) X12 Code

providerType

classification

specialization

service

code

name

value

code

name

role

concentration

class

vaGeneric

vaProduct

PERSON CLASS (#8932.1) Provider Type

PERSON CLASS (#8932.1) Classification

PERSON CLASS (#8932.1) Area of
Specialization

NEW PERSON (#200) Service/Section

NEW PERSON (#200) ien

NEW PERSON (#200) Name

string

DRUG (#50) ien

DRUG (#50) Generic Name

D

string

code

name

vuid

code

VA DRUG CLASS (#50.605) Code

VA DRUG CLASS (#50.605) Classification

VA DRUG CLASS (#50.605) VUID

VA GENERIC (#50.6) ien

name

VA GENERIC (#50.6) Name

vuid

code

VA GENERIC (#50.6) VUID

VA PRODUCT (#50.68) ien

Virtual Patient Record (VPR) 1.0
Developer’s Guide

46

July 2022

Elements

Attributes

Content

name

vuid

VA PRODUCT (#50.68) Name

VA PRODUCT (#50.68) VUID

ptInstructions

quantity

routing

sig

start

status

stop

supply

type

vaStatus

vaType

value

value

value

value

value

value

value

value

value

value

value

* = may be multiple

string

number

W, M, or C

string

VA FileMan date.time

active, hold, historical, or not active

VA FileMan date.time

boolean (1 or 0)

Prescription

ORDER STATUS (#100.01) Name

O

3.12.4  Non-VA Medications
Input parameters:

TYPE

“meds” [required]

[optional]

START

VA FileMan date to filter on “expires”, chronologically

STOP

MAX

ID

VA FileMan date to filter on “expires”, chronologically

Number of most recent non-VA med orders to return

ORDER (#100) file IEN

FILTER(“vaType”) “N”

Table 23: VPR GET PATIENT DATA—Non-VA Medications Elements Returned

Elements

Attributes

Content

currentProvider

code

name

officePhone

analogPager

fax

NEW PERSON (#200) ien

NEW PERSON (#200) Name

NEW PERSON (#200) Office Phone

NEW PERSON (#200) Voice Pager

NEW PERSON (#200) Fax Number

Virtual Patient Record (VPR) 1.0
Developer’s Guide

47

July 2022

Elements

Attributes

Content

email

NEW PERSON (#200) Email Address

taxonomyCode

PERSON CLASS (#8932.1) X12 Code

providerType

classification

specialization

service

dose

units

unitsPerDose

noun

route

schedule

code

name

value

value

code

name

value

value

value

value

dose [m]

facility

form

id

location

medID

name

ordered

orderID

PERSON CLASS (#8932.1) Provider Type

PERSON CLASS (#8932.1) Classification

PERSON CLASS (#8932.1) Area of
Specialization

NEW PERSON (#200) Service/Section

string

string

number

string

MEDICATION ROUTES (#51.2)
Abbreviation

ADMINISTRATION SCHEDULE (#51.1)
Name

INSTITUTION (#4) Station Number

INSTITUTION (#4) Name

DOSAGE FORM (#50.606) Name

ORDER (#100) ien

HOSPITAL LOCATION (#44) ien

HOSPITAL LOCATION (#44) Name

NON-VA MED ORDERS (#55.05) subfile
ien_“N;O”

PHARMACY ORDERABLE ITEM (#50.7)
Name, Form

VA FileMan date.time

ORDER (#100) ien

orderingProvider

code

NEW PERSON (#200) ien

name

officePhone

analogPager

fax

email

NEW PERSON (#200) Name

NEW PERSON (#200) Office Phone

NEW PERSON (#200) Voice Pager

NEW PERSON (#200) Fax Number

NEW PERSON (#200) Email Address

Virtual Patient Record (VPR) 1.0
Developer’s Guide

48

July 2022

Elements

Attributes

Content

taxonomyCode

PERSON CLASS (#8932.1) X12 Code

providerType

classification

specialization

service

code

name

role

concentration

class

vaGeneric

vaProduct

PERSON CLASS (#8932.1) Provider Type

PERSON CLASS (#8932.1) Classification

PERSON CLASS (#8932.1) Area of
Specialization

NEW PERSON (#200) Service/Section

DRUG (#50) ien

DRUG (#50) Generic Name

D

string

code

name

vuid

code

VA DRUG CLASS (#50.605) Code

VA DRUG CLASS (#50.605) Classification

VA DRUG CLASS (#50.605) VUID

VA GENERIC (#50.6) ien

name

VA GENERIC (#50.6) Name

vuid

code

name

vuid

VA GENERIC (#50.6) VUID

VA PRODUCT (#50.68) ien

VA PRODUCT (#50.68) Name

VA PRODUCT (#50.68) VUID

string

VA FileMan date.time

active, hold, historical, or not active

VA FileMan date.time

OTC

ORDER STATUS (#100.01) Name

N

product [m]

sig

start

status

stop

type

vaStatus

vaType

* = may be multiple

Virtual Patient Record (VPR) 1.0
Developer’s Guide

49

July 2022

3.13 Problem List (GMPL)
Input parameters:

TYPE

“problems” [required]

[optional]

START

VA FileMan date to filter on “onset”

STOP

MAX

ID

VA FileMan date to filter on “onset”

Use not recommended, as problems are not sorted

Problem file #9000011 IEN

FILTER(“status”)  desired “status” code

Table 24: VPR GET PATIENT DATA—Problem List (GMPL) Elements Returned

Element

acuity

codingSystem

comment

entered

exposure *

facility

icd

icdd

id

location

name

onset

provider

removed

resolved

Attributes

code

name

value

id

enteredBy

entered

commentText

value

value

code

name

value

value

value

value

value

value

code

name

value

value

Content

A or C

ACUTE or CHRONIC

ICD or 10D

number

NEW PERSON (#200) Name

VA FileMan date

string

date

AO, IR, PG, HNC, MST, CV, or SHAD

INSTITUTION (#4) Station Number

INSTITUTION (#4) Name

ICD code

ICD Description

PROBLEM (#9000011) ien

HOSPITAL LOCATION (#44) name

PROVIDER NARRATIVE (#9999999.27)
Narrative

VA FileMan date

NEW PERSON (#200) ien

NEW PERSON (#200) Name

boolean (1 or 0)

VA FileMan date

Virtual Patient Record (VPR) 1.0
Developer’s Guide

50

July 2022

Element

Attributes

Content

sc

sctc

sctd

sctt

service

status

unverified

updated

 * = may be multiple

value

value

value

value

value

code

name

value

value

boolean (1 or 0)

SNOMED Concept Code

SNOMED Designation Code

SNOMED Preferred Text

SERVICE (#49) Name

A or I

ACTIVE or INACTIVE

boolean (1 or 0)

VA FileMan date

3.14 Radiology/Nuclear Medicine (RA)
Input parameters:

“radiologyExams” [required]

TYPE

[optional]

START

VA FileMan date to filter on “dateTime”

STOP

MAX

ID

VA FileMan date to filter on “dateTime”

Number of most recent exams to return

EXAMINATIONS (#70.03) sub-file IEN string

FILTER(“text”)  1 or 0, to include “content” text of report

Table 25: VPR GET PATIENT DATA—Radiology/Nuclear Medicine (RA) Elements Returned

Elements

case

category

dateTime

document *

Attributes

value

value

value

id

localTitle

nationalTitle

Content

number

RA

VA FileMan date.time

TIU DOCUMENT (#8925) ien

TIU DOCUMENT DEFINITION (#8925.1)
Name

TIU VHA ENTERPRISE STANDARD TITLE
(#8926.1)

vuid

VUID number

Virtual Patient Record (VPR) 1.0
Developer’s Guide

51

July 2022

Elements

Attributes

Content

status

Verified, Released/NotVerified, or
Electronically Filed

content

word-processing text

encounter

facility

hasImages

id

imagingType

interpretation

location

modifier *

name

order

provider

radOrderID

value

code

name

value

value

code

name

value

code

name

code

name

value

code

name

code

name

VISIT (#9000010) ien

INSTITUTION (#4) Station Number

INSTITUTION (#4) Name

boolean (1 or 0)

EXAMINATIONS (#70.03) subfile ien string

IMAGING TYPE (#79.2) Abbreviation

IMAGING TYPE (#79.2) Type of Imaging

string

HOSPITAL LOCATION (#44) ien

HOSPITAL LOCATION (#44) name

CPT Modifier

CPT Modifier Name

RAD/NUC MED PROCEDURES (#71)
Name

ORDER (#100) ien

ORDERABLE ITEMS (#101.43) Name

NEW PERSON (#200) ien

NEW PERSON (#200) Name

officePhone

NEW PERSON (#200) Office Phone

analogPager

NEW PERSON (#200) Voice Pager

fax

email

NEW PERSON (#200) Fax Number

NEW PERSON (#200) Email Address

taxonomyCode

PERSON CLASS (#8932.1) X12 Code

providerType

PERSON CLASS (#8932.1) Provider Type

classification

PERSON CLASS (#8932.1) Classification

specialization

PERSON CLASS (#8932.1) Area of
Specialization

service

value

NEW PERSON (#200) Service/Section

RAD/NUC MED ORDERS (#75.1) ien

Virtual Patient Record (VPR) 1.0
Developer’s Guide

52

July 2022

Elements

status

type

urgency

* = may be multiple

Attributes

Content

value

code

name

value

COMPLETE, CANCELLED, EXAMINED,
WAITING FOR EXAM, or CALLED FOR
EXAM

CPT Code

CPT Description

STAT, ASAP, or ROUTINE

3.15 Registration (DPT)
Input parameters:

TYPE

“demographics” [required]

[optional]

START

STOP

MAX

ID

none

none

none

PATIENT (#2) file IEN

FILTER

none

Table 26: VPR GET PATIENT DATA—Registration (DPT) Elements Returned

Elements

Attributes

Content

address

admitted

alias *

streetLine1

streetLine2

streetLine3

city

stateProvince

postalCode

id

date

fullName

familyName

givenNames

string

string

string

string

STATE (#5) Name

string

PATIENT MOVEMENT (#405) ien

PATIENT MOVEMENT (#405) Date/Time

string

string

string

attending

code

NEW PERSON (#200) ien

Virtual Patient Record (VPR) 1.0
Developer’s Guide

53

July 2022

Elements

Attributes

Content

bid

died

disability *

dob

eligibility *

name

value

value

printName

scPercent

sc

value

name

primary

eligibilityStatus

value

ethnicity *

exposure *

facility *

familyName

flag *

fullName

gender

givenNames

icn

id

inpatient

language

location

value

value

id

name

latestDate

domain

homeSite

value

name

text

value

value

value

value

value

value

code

name

code

name

NEW PERSON (#200) Name

String

VA FileMan date

DISABILITY CONDITION (#31) Name

number

boolean (1 or 0)

VA FileMan date

ELIGIBILITY (#8) Name

boolean (1 or 0)

PENDING [RE]VERIFICATION or
VERIFIED

ETHNICITY (#10.2) HL7 Value

AO, IR, PG, HNC, MST, or CV

INSTITUTION (#4) Station Number

INSTITUTION (#4) Name

VA FileMan date.time

DOMAIN (#4.2) Name

boolean (1 or 0)

string

PRF NATIONAL FLAG (#26.15) or PRF
LOCAL FLAG (#26.11) Name

string

string

M, F, or UN

string

ICN number

PATIENT (#2) ien

boolean (1 or 0)

ISO 639 2-character language code

string

HOSPITAL LOCATION (#44) ien

HOSPITAL LOCATION (#44) Name

Virtual Patient Record (VPR) 1.0
Developer’s Guide

54

July 2022

Elements

Attributes

Content

locSvc

lrdfn

maritalStatus

meansTest

pcAssigned

pcProvider

code

name

value

value

value

value

code

name

officePhone

analogPager

fax

email

M, S, P, NH, NE, I, R, SCI, D, B, or NC

MEDICINE, SURGERY, PSYCHIATRY,
NHCU, NEUROLOGY, INTERMEDIATE
MED, REHAB MEDICINE, SPINAL CORD
INJURY, DOMICILIARY, BLIND REHAB,
or NON-COUNT

number

D, M, W, S, N, or U

MEANS TEST STATUS (#408.32) Name

VA FileMan date

NEW PERSON (#200) ien

NEW PERSON (#200) Name

NEW PERSON (#200) Office Phone

NEW PERSON (#200) Voice Pager

NEW PERSON (#200) Fax Number

NEW PERSON (#200) Email Address

taxonomyCode

PERSON CLASS (#8932.1) X12 Code

providerType

classification

specialization

service

address

PERSON CLASS (#8932.1) Provider Type

PERSON CLASS (#8932.1) Classification

PERSON CLASS (#8932.1) Area of
Specialization

NEW PERSON (#200) Service/Section

streetLine1

string

streetLine2

string

streetLine3

string

city

string

stateProvinc
e

STATE (#5) Name

postalCode

string

pcTeam

code

name

TEAM (#404.51) ien

TEAM (#404.51) Name

pcTeamMember

code

NEW PERSON (#200) ien

name

NEW PERSON (#200) Name

Virtual Patient Record (VPR) 1.0
Developer’s Guide

55

July 2022

Elements

Attributes

Content

officePhone

analogPager

fax

email

NEW PERSON (#200) Office Phone

NEW PERSON (#200) Voice Pager

NEW PERSON (#200) Fax Number

NEW PERSON (#200) Email Address

taxonomyCode

PERSON CLASS (#8932.1) X12 Code

providerType

classification

specialization

PERSON CLASS (#8932.1) Provider Type

PERSON CLASS (#8932.1) Classification

PERSON CLASS (#8932.1) Area of
Specialization

service

NEW PERSON (#200) Service/Section

race *

religion

roomBed

sc

scPercent

sensitive

servicePeriod

site

specialty

ssn

value

value

value

value

value

value

value

code

name

code

name

value

support *

contactType

name

relationship

RACE (#10) HL7 Value

RELIGIOUS PREFERENCE (#13) Name

string

boolean (1 or 0)

number

boolean (1 or 0)

PERIOD OF SERVICE (#21) Name

INSTITUTION (#4) Station Number

INSTITUTION (#4) Name

FACILITY TREATING SPECIALTY (#45.7)
ien

FACILITY TREATING SPECIALTY (#45.7)
Name

string

NOK or ECON

string

string

address

streetLine1

string

streetLine2

string

streetLine3

string

city

string

stateProvinc
e

STATE (#5) Name

Virtual Patient Record (VPR) 1.0
Developer’s Guide

56

July 2022

Elements

Attributes

Content

postalCode

string

telecom

usageType  H, MC, or WP

value

string

telecom

usageType

veteran

ward

value

value

code

name

* = may be multiple

H, MC, or WP

string

boolean (1 or 0)

WARD LOCATION (#42) ien

WARD LOCATION (#42) Name

3.16 Scheduling (SDAM)
The Scheduling API sorts appointments by dateTime chronologically; while past appointments
are available, the default view is to extract a patient’s future appointments.

Input parameters:

TYPE

“appointments” [required]

[optional]

START
[default = TODAY]

VA FileMan date to filter on “dateTime”

STOP

MAX

ID

VA FileMan date to filter on “dateTime”
[default = all future]

Number of [future] appointments to return

Inverse visit string (“servCatg;date.time;locationIEN”)

FILTER

none

Table 27: VPR GET PATIENT DATA—Scheduling (SDAM) Elements Returned

Elements

apptStatus

clinicStop

dateTime

facility

Attributes

Content

value

code

name

value

code

SCHEDULED/KEPT, INPATIENT, NO-
SHOW, CANCELLED BY PATIENT,
CANCELLED BY CLINIC,
RESCHEDULED, NO ACTION TAKEN

CLINIC STOP (#40.7) AMIS Stop Code

CLINIC STOP (#40.7)7 Name

VA FileMan date.time

INSTITUTION (#4) Station Number

Virtual Patient Record (VPR) 1.0
Developer’s Guide

57

July 2022

Elements

Attributes

Content

id

location

patientClass

provider

service

serviceCategory

type

visitString

name

value

value

value

code

name

value

code

name

code

name

value

INSTITUTION (#4) Name

serviceCategory code;dateTime;HOSPITAL
LOCATION (#44) ien

HOSPITAL LOCATION (#44) Name

AMB, IMP, or EMER

NEW PERSON (#200) ien

NEW PERSON (#200) Name

MEDICINE, SURGERY, PSYCHIATRY,
NHCU, NEUROLOGY, INTERMEDIATE
MED, REHAB MEDICINE, SPINAL CORD
INJURY, DOMICILIARY, BLIND REHAB, or
RESPITE CARE

A, I, or H

AMBULATORY, INPATIENT VISIT, or
HOSPITALIZATION

APPOINTMENT TYPE (#409.1) ien

APPOINTMENT TYPE (#409.1) Name

HOSPITAL LOCATION (#44) ien;dateTime;
serviceCategory code

Virtual Patient Record (VPR) 1.0
Developer’s Guide

58

July 2022

3.17 Surgery (SR)
TYPE
Input parameters:

“surgeries” [required]

[optional]

START

VA FileMan date to filter on “dateTime”

STOP

MAX

ID

VA FileMan date to filter on “dateTime”

number of most recent surgical procedures to return

SURGERY (#130) file IEN

FILTER(“text”)  1 or 0, to include “content” text of report

Elements

category

dateTime

document *

encounter

facility

id

modifier *

name

opReport

otherProcedure *

Table 28: VPR GET PATIENT DATA—Surgery (SR) Elements Returned

Attributes

Content

value

value

id

localTitle

SR

VA FileMan date

TIU DOCUMENT (#8925) ien

TIU DOCUMENT DEFINITION (#8925.1)
Name

nationalTitle

TIU VHA ENTERPRISE STANDARD TITLE
(#8926.1)

vuid

content

value

code

name

value

code

name

value

id

localTitle

nationalTitle

vuid

code

name

VUID number

word-processing text

VISIT (#9000010) ien

INSTITUTION (#4) Station Number

INSTITUTION (#4) Name

SURGERY (#130) ien

CPT Modifier

CPT Modifier Name

string

TIU DOCUMENT (#8925) ien

TIU DOCUMENT DEFINITION (#8925.1)
Name

TIU VHA ENTERPRISE STANDARD TITLE
(#8926.1)

VUID number

CPT Code

CPT Description

Virtual Patient Record (VPR) 1.0
Developer’s Guide

59

July 2022

Elements

provider

Attributes

Content

code

name

NEW PERSON (#200) ien

NEW PERSON (#200) Name

officePhone

NEW PERSON (#200) Office Phone

analogPager

NEW PERSON (#200) Voice Pager

fax

email

NEW PERSON (#200) Fax Number

NEW PERSON (#200) Email Address

taxonomyCode

PERSON CLASS (#8932.1) X12 Code

providerType

PERSON CLASS (#8932.1) Provider Type

classification

PERSON CLASS (#8932.1) Classification

specialization

PERSON CLASS (#8932.1) Area of
Specialization

service

value

code

name

NEW PERSON (#200) Service/Section

COMPLETED or ABORTED

CPT Code

CPT Description

status

type

3.18 Text Integration Utilities (TIU)
TYPE
Input parameters:

“documents” [required]

[optional]

START

VA FileMan date to filter on “referenceDateTime”

STOP

MAX

ID

VA FileMan date to filter on “referenceDateTime”

Number of most recent documents to return

TIU DOCUMENTS (#8925) file IEN

FILTER(“category”)  desired “category” code

FILTER(“status”)

“completed”, “unsigned”, or “all” (for current user)

FILTER(“loinc”)

LOINC code (see LOINC codes list following Table 29)

FILTER(“text”)

1 or 0, to include “content” text of report

Virtual Patient Record (VPR) 1.0
Developer’s Guide

60

July 2022

Table 29: VPR GET PATIENT DATA—Text Integration Utilities (TIU) Elements Returned

Elements

category

clinician [m]

Attributes

Content

value

code

name

role

PN, DS, CR, CP, SR, RA, LR, C, W, A, or
D

NEW PERSON (#200) ien

NEW PERSON (#200) Name

A, S, or C

dateTime

VA FileMan date.time

signatureBlock

string

officePhone

NEW PERSON (#200) Office Phone

analogPager

NEW PERSON (#200) Voice Pager

fax

email

NEW PERSON (#200) Fax Number

NEW PERSON (#200) Email Address

taxonomyCode

PERSON CLASS (#8932.1) X12 Code

providerType

PERSON CLASS (#8932.1) Provider Type

classification

PERSON CLASS (#8932.1) Classification

specialization

PERSON CLASS (#8932.1) Area of
Specialization

service

NEW PERSON (#200) Service/Section

content

documentClass

encounter

facility

id

images

localTitle

loinc

nationalTitle

value

value

code

name

value

value

value

value

code

name

word-processing text

TIU DOCUMENT DEFINITION (#8925.1)
Name

VISIT (#9000010) ien

INSTITUTION (#4) Station Number

INSTITUTION (#4) Name

TIU DOCUMENTS (#8925) ien

number

TIU DOCUMENT DEFINITION (#8925.1)
Name

LOINC code

TIU VHA ENTERPRISE STANDARD TITLE
(#8926.1) VUID

TIU VHA ENTERPRISE STANDARD TITLE
(#8926.1)

nationalTitleRole

code

TIU LOINC ROLE (#8926.3) VUID

Virtual Patient Record (VPR) 1.0
Developer’s Guide

61

July 2022

Elements

Attributes

Content

nationalTitleService

nationalTitleSetting

nationalTitleSubject

name

code

name

code

name

code

name

nationalTitleType

code

parent

referenceDateTime

status

subject

name

value

value

value

value

TIU LOINC ROLE (#8926.3) Role

TIU LOINC SERVICE (#8926.5) VUID

TIU LOINC SERVICE (#8926.5) Service

TIU LOINC SETTING (#8926.4) VUID

TIU LOINC SETTING (#8926.4) Setting

TIU LOINC SUBJ MATTER DOMN
(#8926.2) VUID

TIU LOINC SUBJECT MATTER DOMAIN
(#8926.2)

TIU LOINC DOCUMENT TYPE (#8926.6)
VUID

TIU LOINC DOCUMENT TYPE (#8926.6)
Doc Type

TIU DOCUMENTS (#8925) ien

VA FileMan date.time

TIU STATUS (#8925.6) Name, in lowercase

string

LOINC codes currently in use with VLER:

•  11488-4

•  18726-0

•  18842-5

•  26441-6

•  27895-2

•  27896-0

•  27897-8

•  27898-6

•  28570-0

•  28619-5

•  28634-4

•  29752-3

•  34117-2

Consultation Note

Radiology Studies

Discharge Summarization Note

Cardiology Studies

Gastroenterology Endoscopy Studies

Pulmonary Studies

Neuromuscular Electrophysiology Studies

Pathology Studies

Procedure Note (unspecified)

Ophthalmology Studies

Miscellaneous Studies

Perioperative Records

History & Physical Note

Virtual Patient Record (VPR) 1.0
Developer’s Guide

62

July 2022

Because there is no direct link in VistA between the TIU titles and LOINC codes, the above list
of codes has been manually mapped to existing TIU search capabilities. The “loinc” attribute is
only returned when a group of documents is requested using the loinc filter and will be the same
value passed into the extract.

3.19 Visits/PCE (PX)
Input parameters:

TYPE

“visits” [required]

[optional]

START

VA FileMan date to filter on “dateTime”

STOP

MAX

ID

VA FileMan date to filter on “dateTime”

Number of most recent visits to return

VISIT (#9000010) file IEN

FILTER(“text”)

1 or 0, to include “content” text of report

Table 30: VPR GET PATIENT DATA—Visits/PCE (PX) Elements Returned

Elements

cpt *

creditStopCode

dateTime

document *

facility

icd *

Attributes

Content

code

name

code

name

value

id

localTitle

nationalTitle

vuid

content

code

name

code

name

system

narrative

CPT Code

CPT Short Name

CLINIC STOP (#40.7) AMIS Stop Code

CLINIC STOP (#40.7) Name

VA FileMan date.time

TIU DOCUMENT (#8925) ien

TIU DOCUMENT DEFINITION (#8925.1)
Name

TIU VHA ENTERPRISE STANDARD TITLE
(#8926.1)

VUID number

word-processing text

INSTITUTION (#4) Station Number

INSTITUTION (#4) Name

ICD Code

ICD Description

ICD or 10D

V POV (#9000010.07) Provider Narrative

Virtual Patient Record (VPR) 1.0
Developer’s Guide

63

July 2022

Elements

id

location

patientClass

provider *

Attributes

ranking

Content

P or S

value

value

value

code

name

role

VISIT (#9000010) ien

HOSPITAL LOCATION (#44) Name

AMB, IMP, or EMER

NEW PERSON (#200) ien

NEW PERSON (#200) Name

P, S, or A

primary

boolean (1 or 0)

officePhone

NEW PERSON (#200) Office Phone

analogPager

NEW PERSON (#200) Voice Pager

fax

email

NEW PERSON (#200) Fax Number

NEW PERSON (#200) Email Address

taxonomyCode

PERSON CLASS (#8932.1) X12 Code

providerType

PERSON CLASS (#8932.1) Provider Type

classification

PERSON CLASS (#8932.1) Classification

specialization

PERSON CLASS (#8932.1) Area of
Specialization

reason

service

serviceCategory

service

code

name

system

narrative

value

code

name

NEW PERSON (#200) Service/Section

ICD Code

ICD Description

ICD or 10D

V POV (#9000010.07) Provider Narrative

MEDICINE, SURGERY, PSYCHIATRY,
NHCU, NEUROLOGY, INTERMEDIATE
MED, REHAB MEDICINE, SPINAL CORD
INJURY, DOMICILIARY, BLIND REHAB,
or RESPITE CARE

A, H, I, C, N, T, S, O, E, R, D, or X

AMBULATORY, HOSPITALIZATION, IN
HOSPITAL, CHART REVIEW, NOT
FOUND,
TELECOMMUNICATIONS, DAY
SURGERY, OBSERVATION, EVENT
(HISTORICAL), NURSING HOME, DAILY
HOSPITALIZATION DATA, ANCILLARY

Virtual Patient Record (VPR) 1.0
Developer’s Guide

64

July 2022

Elements

Attributes

Content

stopCode

type

visitString

code

name

code

name

value

Included with admissions:

admission

arrivalDateTime

departureDateTime

ptf

roomBed

specialty

* = may be multiple

PACKAGE DAILY DATA

CLINIC STOP (#40.7) AMIS Stop Code

CLINIC STOP (#40.7) Name

CPT Code

CPT Short Name

HOSPITAL LOCATION (#44) ien;dateTime;
serviceCategory code

PATIENT MOVEMENT (#405) ien

VA FileMan date.time

VA FileMan date.time

PTF (#45) ien

string

FACILITY TREATING SPECIALTY (#45.7)
Name

Virtual Patient Record (VPR) 1.0
Developer’s Guide

65

July 2022

3.20 Vital Measurements (GMV)
TYPE
Input parameters:

“vitals” [required]

[optional]

START

VA FileMan date to filter on “taken”

STOP

MAX

ID

VA FileMan date to filter on “taken”

Number of measurement sets to return (by “taken”)

GMRV VITAL MEASUREMENT (#120.5) file IEN, or

VA FileMan date.time to match “taken” and return the set

FILTER

none

Table 31: VPR GET PATIENT DATA—Vital Measurements (GMV) Elements Returned

Elements

Attributes

Content

entered

facility

location

value

code

name

code

name

VA FileMan date.time

INSTITUTION (#4) Station Number

INSTITUTION (#4) Name

HOSPITAL LOCATION (#44) ien

HOSPITAL LOCATION (#44) Name

measurement *

id

GMRV VITAL MEASUREMENT (#120.5) ien

vuid

name

value

units

metricValue

metricUnits

high

low

bmi

VUID number

GMRV VITAL TYPE (#120.51) Name

string

string

number

C, cm, or kg

number

number

number

qualifier *

name  GMRV VITAL QUALIFIER (#120.52) Qualifier

vuid

GMRV VITAL QUALIFIER (#120.52) VUID

removed *

value

INCORRECT DATE/TIME, INCORRECT READING,
INCORRECT PATIENT, INVALID RECORD

taken

value

VA FileMan date.time

* = may be multiple

Virtual Patient Record (VPR) 1.0
Developer’s Guide

66

July 2022

JSON Tables

4
This section includes tables that list the data elements returned by the VPR GET PATIENT
DATA JSON RPC. All input parameters are optional to refine the extract, except for domain,
and are passed in as list subscripts [i.e., FILTER(“parameter”)=value]. All searches are
performed reverse-chronologically to return the most recent data, unless otherwise noted.

4.1  Allergy/Adverse Reaction Tracking (GMRA)
Input Parameters:

“allergy” [required]

domain

[optional]

start

stop

max

id

uid

VA FileMan date to filter on “entered”

VA FileMan date to filter on “entered”

Use not recommended, as reactions are not sorted

PATIENT ALLERGIES (#120.8) file IEN

Universal ID for item (urn:va:domain:SYS:DFN:id)

Table 32: RPC: VPR GET PATIENT DATA JSON—Allergy/Adverse Reaction Tracking (GMRA)
Elements Returned

Attributes

name

vuid

name

vuid

Elements

entered

facilityCode

facilityName

historical

kind

localId

products

reactions *

reference

removed

summary

uid

verified

* = may be multiple

Virtual Patient Record (VPR) 1.0
Developer’s Guide

67

July 2022

4.2  Clinical Observations (MDC)
“obs” [required]
domain
Input parameters:

[optional]

start

stop

max

id

uid

VA FileMan date to filter on “observed”

VA FileMan date to filter on “observed”

Use with caution, as search is performed chronologically

OBS (#704.117) file ID (#.01) value

Universal ID for item (urn:va:domain:SYS:DFN:id)

Table 33 RPC: VPR GET PATIENT DATA JSON—Clinical Observations (MDC) Elements Returned

Elements

Attributes

bodySiteCode

bodySiteName

comment

entered

facilityCode

facilityName

interpretationCode

interpretationName

localId

locationName

locationUid

methodCode

methodName

observed

qualifiers *

result

setID

setName

setStart

code

name

type

Virtual Patient Record (VPR) 1.0
Developer’s Guide

68

July 2022

Attributes

Elements

setStop

setType

statusCode

statusName

typeCode

typeName

uid

units

4.3  Clinical Procedures (MDC)
domain
Input parameters:

“procedure” [required]

[optional]

start

stop

max

id

uid

VA FileMan date to filter on “dateTime”

VA FileMan date to filter on “dateTime”

Number of most recent procedures to return

Variable pointer to CP data file/item

Universal ID for item (urn:va:domain:SYS:DFN:id)

Table 34: RPC: VPR GET PATIENT DATA JSON—Clinical Procedures (MDC) Elements Returned

Attributes

Elements

category

consultUid

dateTime

encounterUid

facilityCode

facilityName

hasImages

interpretation

kind

localId

locationName

locationUid

Virtual Patient Record (VPR) 1.0
Developer’s Guide

69

July 2022

Elements

name

orderUid

providers

requested

results *

statusName

uid

Attributes

providerName

providerUid

localTitle

nationalTitle

uid

* = may be multiple

4.4  Consult/Request Tracking (GMRC)
Input parameters:

“consult” [required]

domain

[optional]

start

stop

max

id

uid

VA FileMan date to filter on “dateTime”

VA FileMan date to filter on “dateTime”

Number of most recent consult requests to return

REQUEST/CONSULTATION (#123) file IEN

Universal ID for item (urn:va:domain:SYS:DFN:id)

Table 35: RPC: VPR GET PATIENT DATA JSON—Consult/Request Tracking (GMRC) Elements
Returned

Attributes

Elements

category

consultProcedure

dateTime

facilityCode

facilityName

interpretation

localId

Virtual Patient Record (VPR) 1.0
Developer’s Guide

70

July 2022

Elements

orderName

orderUid

providerName

providerUid

provisionalDx

reason

results *

service

statusName

typeName

uid

urgency

Attributes

code

name

system

localTitle

nationalTitle

uid

* = may be multiple

Virtual Patient Record (VPR) 1.0
Developer’s Guide

71

July 2022

4.5  Laboratory (LR)
Input parameters:

domain

“lab” [required]

[optional]

start

stop

max

id

uid

VA FileMan date to filter on “observed”

VA FileMan date to filter on “observed”

Number of most recent accessions to return

LAB DATA (#63) file IEN string

Universal ID for item (urn:va:domain:SYS:DFN:id)

category

CH, MI, or AP [default = all]

Table 36: RPC: VPR GET PATIENT DATA JSON—Laboratory (LR) Elements Returned

Elements

Attributes

Content

bactRemarks

categoryCode

categoryName

comment

displayName

displayOrder

facilityCode

facilityName

gramStain *

groupName

groupUid

high

interpretationCode

interpretationName

labOrderId

localId

low

observed

orderUid

result

organisms *

drugs

interp

name

Virtual Patient Record (VPR) 1.0
Developer’s Guide

72

July 2022

Elements

Attributes

Content

restrict

result

organizerType

result

resulted

results *

sample

specimen

statusCode

statusName

typeCode

typeId

typeName

uid

units

urineScreen

vuid

name

qty

localTitle

nationalTitle

resultUid

uid

* = may be multiple

Virtual Patient Record (VPR) 1.0
Developer’s Guide

73

July 2022

4.6  Orders (OR)
Input parameters:

domain

[optional]

start

stop

max

id

uid

“order” [required]

VA FileMan date to filter on date released

VA FileMan date to filter on date released

Number of most recent orders to return

ORDER (#100) file IEN string

Universal ID for item (urn:va:domain:SYS:DFN:id)

Table 37: RPC: VPR GET PATIENT DATA JSON—Orders (OR) Elements Returned

Attributes

name

role

signedDateTime

uid

Elements

adminTimes

clinicians *

content

displayGroup

entered

facilityCode

facilityName

instructions

localId

locationName

locationUid

name

oiCode

oiName

oiPackageRef

orderUid

predecessor

providerName

providerUid

Virtual Patient Record (VPR) 1.0
Developer’s Guide

74

July 2022

Elements

results *

scheduleName

service

start

statusCode

statusName

statusVuid

stop

successor

uid

Attributes

uid

* = may be multiple

4.7  Patient Care Encounter (PX)
4.7.1  CPT Procedures
Input parameters:

“cpt” [required]

domain

[optional]

start

stop

max

id

uid

VA FileMan date to filter on “entered”

VA FileMan date to filter on “entered”

number of most recent procedures to return

V CPT (#9000010.18) file IEN

Universal ID for item (urn:va:domain:SYS:DFN:id)

Table 38: RPC: VPR GET PATIENT DATA JSON—CPT Procedures Elements Returned

Elements

comment

cptCode

encounterName

encounterUid

entered

facilityCode

facilityName

Virtual Patient Record (VPR) 1.0
Developer’s Guide

75

July 2022

Elements

localId

locationName

locationUid

name

quantity

type

uid

4.7.2  Exams
Input parameters:

[optional]

domain

“exam” [required]

start

stop

max

id

uid

VA FileMan date to filter on “entered”

VA FileMan date to filter on “entered”

Number of most recent exams to return

V EXAM (#9000010.13) file IEN

Universal ID for item (urn:va:domain:SYS:DFN:id)

Table 39: RPC: VPR GET PATIENT DATA JSON—Exams Elements Returned

Elements

comment

encounterName

encounterUid

entered

facilityCode

facilityName

localId

locationName

locationUid

name

result

uid

Virtual Patient Record (VPR) 1.0
Developer’s Guide

76

July 2022

4.7.3  Education Topics
Input parameters:

domain

[optional]

start

stop

max

id

uid

“education” [required]

VA FileMan date to filter on “entered”

VA FileMan date to filter on “entered”

Number of most recent education instances to return

V PATIENT ED (#9000010.16) file IEN

Universal ID for item (urn:va:domain:SYS:DFN:id)

Table 40: RPC: VPR GET PATIENT DATA JSON—Education Topics Elements Returned

Elements

comment

encounterName

encounterUid

entered

facilityCode

facilityName

localId

locationName

locationUid

name

result

uid

Virtual Patient Record (VPR) 1.0
Developer’s Guide

77

July 2022

4.7.4  Health Factors
domain
Input parameters:

[optional]

start

stop

max

id

uid

“factor” [required]

VA FileMan date to filter on “entered”

VA FileMan date to filter on “entered”

Number of most recent factors to return

V HEALTH FACTORS (#9000010.23) file IEN

Universal ID for item (urn:va:domain:SYS:DFN:id)

Table 41: RPC: VPR GET PATIENT DATA JSON—Health Factors Elements Returned

Elements

categoryName

categoryUid

comment

display

encounterName

encounterUid

entered

facilityCode

facilityName

kind

localId

locationName

locationUid

name

severityName

severityUid

summary

uid

Virtual Patient Record (VPR) 1.0
Developer’s Guide

78

July 2022

4.7.5
Input parameters:

Immunizations
domain

[optional]

start

stop

max

id

uid

“immunization” [required]

VA FileMan date to filter on “administeredDateTime”

VA FileMan date to filter on “administeredDateTime”

Number of most recent immunizations to return

V IMMUNIZATION (#9000010.11) file IEN

Universal ID for item (urn:va:domain:SYS:DFN:id)

Table 42: RPC: VPR GET PATIENT DATA JSON—Immunizations Elements Returned

Elements

administeredDateTime

comment

contraindicated

cptCode

cptName

encounterName

encounterUid

facilityCode

facilityName

localId

locationName

locationUid

name

performerName

performerUid

reactionCode

reactionName

seriesCode

seriesName

summary

uid

Virtual Patient Record (VPR) 1.0
Developer’s Guide

79

July 2022

4.7.6  Purpose of Visit
Input parameters:

domain

“pov” [required]

[optional]

start

stop

max

id

uid

VA FileMan date to filter on “entered”

VA FileMan date to filter on “entered”

Number of most recent reasons to return

V POV (#9000010.07) file IEN

Universal ID for item (urn:va:domain:SYS:DFN:id)

Table 43: RPC: VPR GET PATIENT DATA JSON—Purpose of Visit Elements Returned

Elements

comment

encounterName

encounterUid

entered

facilityCode

facilityName

icdCode

localId

locationName

locationUid

name

type

uid

Virtual Patient Record (VPR) 1.0
Developer’s Guide

80

July 2022

4.7.7  Skin Tests
Input parameters:

domain

[optional]

start

stop

max

id

uid

“skin” [required]

VA FileMan date to filter on “entered”

VA FileMan date to filter on “entered”

Number of most recent exams to return

V SKIN TEST (#9000010.12) file IEN

Universal ID for item (urn:va:domain:SYS:DFN:id)

Table 44: RPC: VPR GET PATIENT DATA JSON—Skin Tests Elements Returned

Elements

comment

dateRead

encounterName

encounterUid

entered

facilityCode

facilityName

localId

locationName

locationUid

name

reading

result

uid

Virtual Patient Record (VPR) 1.0
Developer’s Guide

81

July 2022

4.8  Pharmacy (PS)
4.8.1  Medications
Input parameters:

domain

[optional]

start

stop

max

id

“med” [required]

VA FileMan date to filter on date released

VA FileMan date to filter on date released

Number of most recent med orders to return

ORDER (#100) file IEN

vaType

I, O, or N

Table 45: RPC: VPR GET PATIENT DATA JSON—Medications Elements Returned

Elements

administrations *

comment

dosages *

facilityCode

facilityName

fills *

Attributes

dateTime

status

adminTimes

complexConjunction

complexDuration

dose

relatedOrder

relativeStart

relativeStop

routeName

scheduleFreq

scheduleName

scheduleType

start

stop

units

daysSupplyDispensed

dispenseDate

Virtual Patient Record (VPR) 1.0
Developer’s Guide

82

July 2022

Attributes

partial

releaseDate

routing

quantityDispensed

daysSupply

fillCost

fillsAllowed

fillsRemaining

locationName

locationUid

ordered

orderUid

pharmacistName

pharmacistUid

predecessor

prescriptionId

providerName

providerUid

quantityOrdered

successor

vaRouting

Elements

IMO

lastFilled

localId

medStatus

medStatusName

medType

name

orders

overallStart

overallStop

parent

Virtual Patient Record (VPR) 1.0
Developer’s Guide

83

July 2022

Elements

Attributes

patientInstruction

productFormName

products *

qualifiedName

sig

stopped

supply

type

uid

vaStatus

vaType

drugClassCode

drugClassName

ingredientCode

ingredientCodeName

ingredientName

ingredientRole

relatedOrder

strength

suppliedCode

suppliedName

* = may be multiple

Virtual Patient Record (VPR) 1.0
Developer’s Guide

84

July 2022

Infusions

4.8.2
Input parameters:

[optional]

domain

“med” [required]

start

stop

max

id

VA FileMan date to filter on date released

VA FileMan date to filter on date released

Number of most recent med orders to return

ORDER (#100) file IEN

vaType

“V”

Table 46: RPC: VPR GET PATIENT DATA JSON—Infusions Elements Returned

Elements

administrations *

comment

dosages

facilityCode

facilityName

IMO

localId

medStatus

medStatusName

medType

name

orders

Attributes

dateTime

status

adminTimes

duration

ivRate

restriction

routeName

scheduleFreq

scheduleName

scheduleType

locationName

locationUid

ordered

Virtual Patient Record (VPR) 1.0
Developer’s Guide

85

July 2022

Attributes

orderUid

pharmacistName

pharmacistUid

predecessor

providerName

providerUid

successor

drugClassCode

drugClassName

ingredientCode

ingredientCodeName

ingredientName

ingredientRole

relatedOrder

strength

suppliedCode

suppliedName

volume

Elements

overallStart

overallStop

parent

products *

qualifiedName

stopped

type

uid

vaStatus

vaType

* = may be multiple

Virtual Patient Record (VPR) 1.0
Developer’s Guide

86

July 2022

4.9  Problem List (GMPL)
Input parameters:

domain

“problem” [required]

[optional]

start

stop

max

id

none

none

Use not recommended, as problems are not sorted

PROBLEM (#9000011) file IEN

status

A or I [default = A (all)]

Table 47: RPC: VPR GET PATIENT DATA JSON—Problem List (GMPL) Elements Returned

Attributes

comment

entered

enteredByCode

enteredByName

Elements

acuityCode

acuityName

comments *

entered

facilityCode

facilityName

icdCode

icdName

localId

locationName

locationUid

onset

problemText

providerName

providerUid

removed

resolved

service

serviceConnected

Virtual Patient Record (VPR) 1.0
Developer’s Guide

87

July 2022

Attributes

Elements

statusCode

statusName

uid

unverified

updated

* = may be multiple

4.10 PTF (DG)
Input parameters:

domain

“ptf” [required]

[optional]

start

stop

max

id

uid

VA FileMan date to filter on movement date

VA FileMan date to filter on movement date

Number of most recent treatment codes to return

PTF (#45) file IEN

Universal ID for item (urn:va:domain:SYS:DFN:id)

Table 48: RPC: VPR GET PATIENT DATA JSON—PTF (DG) Elements Returned

Elements

arrivalDateTime

dischargeDateTime

encounterName

encounterUid

facilityCode

facilityName

icdCode

icdName

localId

principalDx

uid

Virtual Patient Record (VPR) 1.0
Developer’s Guide

88

July 2022

4.11 Radiology/Nuclear Medicine (RA)
Input parameters:

“image” [required]

domain

[optional]

start

stop

max

id

uid

VA FileMan date to filter on “dateTime”

VA FileMan date to filter on “dateTime”

Number of most recent exams to return

EXAMINATIONS (#70.03) sub-file IEN string

Universal ID for item (urn:va:domain:SYS:DFN:id)

Table 49: RPC: VPR GET PATIENT DATA JSON—Radiology/Nuclear Medicine (RA) Elements
Returned

Elements

case

category

dateTime

diagnosis *

encounterName

encounterUid

facilityCode

facilityName

hasImages

imageLocation

imagingTypeUid

interpretation

kind

localId

locationName

locationUid

name

orderName

orderUid

providers

Attributes

code

lexicon

primary

providerName

Virtual Patient Record (VPR) 1.0
Developer’s Guide

89

July 2022

Elements

results

statusName

summary

typeName

uid

verified

Attributes

providerUid

localTitle

uid

* = may be multiple

4.12 Registration (DPT)
Input parameters:

domain

“patient” [required]

[optional]

start

stop

max

id

uid

none

none

none

PATIENT (#2) file IEN

Universal ID for item (urn:va:domain:SYS:DFN:id)

Table 50: RPC: VPR GET PATIENT DATA JSON—Registration (DPT) Elements Returned

Elements

addresses *

aliases

briefId

dateOfBirth

Attributes

Content

city

postalCode

stateProvince

streetLine1

streetLine2

familyName

fullName

givenNames

Virtual Patient Record (VPR) 1.0
Developer’s Guide

90

July 2022

Elements

died

disability *

eligibility *

eligibilityStatus

ethnicities *

exposures *

facilities *

familyName

flags *

fullName

genderCode

genderName

givenNames

icn

inpatient

languageCode

languageName

localId

maritalStatuses

Attributes

Content

disPercent

name

sc

vaCode

name

primary

ethnicity

name

uid

code

homeSite

latestDate

localPatientId

name

systemId

name

text

code

name

Virtual Patient Record (VPR) 1.0
Developer’s Guide

91

July 2022

Elements

meansTest

pcProviderName

pcProviderUid

pcTeamMembers *

pcTeamName

pcTeamUid

races *

religionCode

religionName

sensitive

servicePeriod

ssn

supports *

telecoms *

uid

veteran

Attributes

Content

name

position

uid

race

addresses *

city

postalCode

stateProvince

streetLine1

streetLine2

telecom

usageCode

usageName

contactTypeCode

contactTypeName

name

relationship

telecomList *

telecom

usageCode

usageName

isVet

Virtual Patient Record (VPR) 1.0
Developer’s Guide

92

July 2022

Elements

* = may be multiple

Content

Attributes

lrdfn

serviceConnected

serviceConnectionPercent

4.13 Scheduling (SDAM)
The Scheduling API sorts appointments by dateTime chronologically; while past appointments
are available, the default view is to extract a patient’s future appointments.

Input parameters:

domain

“appointment” [required]

[optional]

start

stop

max

id

uid

VA FileMan date to filter on “dateTime”
[default = TODAY]

VA FileMan date to filter on “dateTime”
[default = all future]

Number of [future] appointments to return

Inverse visit string (“servCatg;date.time;locationIEN”)

Universal ID for item (urn:va:domain:SYS:DFN:id)

Table 51: RPC: VPR GET PATIENT DATA JSON—Scheduling (SDAM) Elements Returned

Elements

Attributes

appointmentStatus

categoryCode

categoryName

checkIn

checkOut

comment

dateTime

facilityCode

facilityName

localId

locationName

locationUid

Virtual Patient Record (VPR) 1.0
Developer’s Guide

93

July 2022

Elements

Attributes

providerName

providerUid

patientClassCode

patientClassName

providers

reasonName

service

stopCodeName

stopCodeUid

summary

typeCode

typeName

uid

* = may be multiple

4.14 Surgery (SR)
Input parameters:

domain

[optional]

start

stop

max

id

uid

“surgery” [required]

VA FileMan date to filter on “dateTime”

VA FileMan date to filter on “dateTime”

Number of most recent surgical procedures to return

SURGERY (#130) file IEN

Universal ID for item (urn:va:domain:SYS:DFN:id)

Table 52: RPC: VPR GET PATIENT DATA JSON—Surgery (SR) Elements Returned

Attributes

Elements

category

dateTime

encounterName

encounterUid

facilityCode

facilityName

Virtual Patient Record (VPR) 1.0
Developer’s Guide

94

July 2022

Elements

Attributes

kind

localId

providers *

providerName

results *

statusName

summary

typeCode

typeName

uid

providerUid

localTitle

nationalTitle

uid

* = may be multiple

Virtual Patient Record (VPR) 1.0
Developer’s Guide

95

July 2022

4.15 Text Integration Utilities (TIU)
domain
Input parameters:

“document” [required]

[optional]

start

stop

max

id

uid

VA FileMan date to filter on “referenceDateTime”

VA FileMan date to filter on “referenceDateTime”

Number of most recent documents to return

TIU DOCUMENTS (#8925) file IEN

Universal ID for item (urn:va:domain:SYS:DFN:id)

category

PN, CR, C, W, A, D, DS, SR, CP, LR, or RA

status

text

“completed”, “unsigned”, or “all” (for current user)

1 or 0, to include “content” text of document

Table 53: RPC: VPR GET PATIENT DATA JSON—Text Integration Utilities (TIU) Elements Returned

Elements

Attributes

Content

attendingName

attendingUid

documentClass

documentTypeCode

documentTypeName

encounterName

encounterUid

entered

facilityCode

facilityName

images

localId

localTitle

nationalTitle

nationalTitleRole

nationalTitleService

title

vuid

role

vuid

service

vuid

Virtual Patient Record (VPR) 1.0
Developer’s Guide

96

July 2022

Elements

Attributes

Content

setting

vuid

subject

vuid

type

vuid

clinicians *

content

dateTime

status

uid

nationalTitleSetting

nationalTitleSubject

nationalTitleType

parent

referenceDateTime

statusName

subject

text *

uid

urgency

* = may be multiple

name

role

signature

signedDateTime

uid

Virtual Patient Record (VPR) 1.0
Developer’s Guide

97

July 2022

4.16 Visits/PCE (PX)
Input parameters:

domain

“visit” [required]

[optional]

start

stop

max

id

uid

VA FileMan date to filter on “dateTime”

VA FileMan date to filter on “dateTime”

Number of most recent visits to return

VISIT (#9000010) file IEN

Universal ID for item (urn:va:domain:SYS:DFN:id)

Table 54: RPC: VPR GET PATIENT DATA JSON—Visits/PCE (PX) Elements Returned

Elements

Attributes

categoryCode

categoryName

checkOut

current

dateTime

documents *

facilityCode

facilityName

localId

locationName

locationUid

movements *

patientClassCode

localTitle

nationalTitle

uid

dateTime

localId

locationName

locationUid

movementType

providerName

providerUid

specialty

Virtual Patient Record (VPR) 1.0
Developer’s Guide

98

July 2022

Elements

Attributes

primary

providerName

providerUid

role

arrivalDateTime

dischargeDateTime

patientClassName

providers *

reasonName

reasonUid

roomBed

service

specialty

stay

stopCodeName

stopCodeUid

summary

typeName

uid

* = may be multiple

Virtual Patient Record (VPR) 1.0
Developer’s Guide

99

July 2022

4.17 Vital Measurements (GMV)
domain
Input parameters:

“vital” [required]

[optional]

start

stop

max

id

VA FileMan date to filter on “observed”

VA FileMan date to filter on “observed”

Number of measurement sets to return (by “taken”)

GMRV VITAL MEASUREMENT (#120.5) file IEN, or

VA FileMan date.time to match “taken” and return the set

uid

Universal ID for item (urn:va:domain:SYS:DFN:id)

Table 55: RPC: VPR GET PATIENT DATA JSON—Vital Measurements (GMV) Elements Returned

Attributes

name

vuid

Elements

displayName

facilityCode

facilityName

high

kind

localId

locationName

locationUid

low

metricResult

metricUnits

observed

qualifiers *

removed

result

resulted

summary

typeCode

typeName

uid

Virtual Patient Record (VPR) 1.0
Developer’s Guide

100

July 2022

Elements

units

Attributes

* = may be multiple

Virtual Patient Record (VPR) 1.0
Developer’s Guide

101

July 2022

5  HealthShare Interface
Patch VPR*1*8 introduced another method of retrieving VistA data to support the HealthShare
(HS) interface engine. This patch exported almost 150 entries in the VA FileMan ENTITY (#1.5)
file, to map VistA data elements to the SDA model and use the supported VA FileMan DDE1
calls DDE calls to retrieve the requested data as XML. Patch VPR*1*14 added approximately 40
more Entities to support the Advanced Medication Platform (AMPL) project.

SDA organizes patient data by classes called “containers,” which correspond to various types of
clinical data. VPR is currently populating 21 of the 30 SDA containers. There is a VPR entity for
every file or sub-file that feeds a container; some containers have multiple VistA sources, and so
multiple VPR entities exist. Entities also exist for sub-classes and common or shared data
elements, such as providers or locations. The names and structure of each VPR entity is intended
to comply with the SDA model.

Clinical data for active patients is loaded into the Edge Cache Repositories (ECR) on the
Regional Health Connect (RHC) servers by a pre-load job. Data is kept up to date by VPR
listeners that are attached to VistA application events. The VPR SUBSCRIPTION (#560) file
does the following:

•  Tracks which patients are currently active in HealthShare for each VistA system.

•  Maintains a list of records that have been modified and need to be updated in the ECR.

The VPRHS routine contains functions to support the RHC servers. These utilities supply an
SDA-formatted record to the RHC and manage the clinical data update list.

1 DDE is the name of the VA FileMan routine that contains the Entity utilities.

Virtual Patient Record (VPR) 1.0
Developer’s Guide

102

July 2022

5.1  Entity File VPR Entries
VPR uses the VA FileMan ENTITY (#1.5) file to store the mappings between VistA files and
fields, and SDA container classes and properties. Unlike the VPR RPCs that are hard-coded, the
DDE (Entity) utility provides a table-driven interface that can be easily updated and searched.

Table 56 lists the VPR entries in the ENTITY (#1.5) file:

Name

Display Name
(SDA Container or class)

Primary Source
Sub/File#

Table 56: VPR Entities

VPR ADMISSION

Encounter

VPR ADMISSION EXTENSION

EncounterExtension

VPR ADMISSION MOVEMENT

Movement

VPR ADVANCE DIRECTIVE

AdvanceDirective

VPR ALLERGY

VPR ALLERGY ASSESSMENT

Allergy

Allergy

VPR ALLERGY EXTENSION

AllergyExtension

VPR ALLERGY OBSERVATION

AllergyObservation

VPR ALLERGY SIGN EXTENSION

ReactionExtension

VPR ALLERGY SIGN/SYMPTOM

Reaction

VPR AMIS

VPR APPOINTMENT

StopCode

Appointment

VPR APPOINTMENT EXTENSION

AppointmentExtension

VPR CDC EXTENSION

CDCExtension

VPR CODE ONLY

VPR CODE TABLE

VPR COMBAT PERIOD

VPR COMBAT SERVICE

VPR COMMENT

CodeTable

CodeTable

Period

Conflict

Comment

VPR CONSULT SERVICE

HealthCareFacility

VPR COUNTRY

VPR CPT

VPR CPT MODIFIER

VPR CUSTOM PAIR

Country

ProcedureCode

CPTModifier

NVPair

405

405

405

8925

120.8

120.86

120.8

120.85

120.8

120.83

40.7

2.98

2.98

10.3

n/a

n/a

22

2

n/a

123.5

779.004

81

81.3

n/a

Virtual Patient Record (VPR) 1.0
Developer’s Guide

103

July 2022

Name

Display Name
(SDA Container or class)

Primary Source
Sub/File#

VPR CW NOTES

VPR DEL FAMILY HX

VPR DEL HF VACC REFUSAL

VPR DEL ICR

VPR DEL PTF

VPR DEL SOCIAL HX

VPR DEL TIU DOCUMENT

VPR DEL V CPT

VPR DEL V EXAM

VPR DEL V POV

VPR DEL VACCINATION

VPR DISPLAY GROUP

VPR DOCUMENT

Alert

FamilyHistory

Vaccination

Vaccination

Diagnosis

SocialHistory

Document

Procedure

PhysicalExam

Diagnosis

Vaccination

OrderCategory

Document

VPR DOCUMENT EXTENSION

DocumentExtension

VPR DOCUMENT ROLE

NationalTitleRole

VPR DOCUMENT SERVICE

NationalTitleService

VPR DOCUMENT SETTING

NationalTitleSetting

8925

9000010.23

9000010.23

9000010.707

45

9000010.23

8925

9000010.18

9000010.13

9000010.07

9000010.11

100.98

8925

8925

8926.3

8926.5

8926.4

VPR DOCUMENT STATUS

DocumentCompletionStatus  8925.6

VPR DOCUMENT SUBJECT

NationalTitleSubject

VPR DOCUMENT TITLE

NationalTitle

VPR DOCUMENT TYPE

NationalTitleType

VPR DOSAGE STEP

DosageStep

VPR DOSE EXTENSION

DosageStepExtension

VPR DRUG CLASS

VPR DRUG GENERIC

VPR DRUG INGREDIENT

VPR DRUG PRODUCT

ATCCode

Generic

DrugProduct

DrugProduct

VPR DRUG PRODUCT EXTENSION

DrugProductExtension

VPR EDP CODE

CodeTable

VPR EDP EXTENSION

EncounterExtension

VPR EDP LOG

Encounter

8926.2

8926.1

8926.6

100

100

50.605

50.6

50.416

50

50

233.1

230

230

Virtual Patient Record (VPR) 1.0
Developer’s Guide

104

July 2022

Name

VPR ELIGIBILITY

VPR ETHNICITY

VPR EXAM

VPR FACILITY

Display Name
(SDA Container or class)

Primary Source
Sub/File#

Eligibility

EthnicGroup

8

10.2

PhysExamCode

9999999.15

Organization

VPR FACILITY ADDRESS

Address

VPR FAMILY DOCTOR

VPR FAMILY HISTORY

VPR FIM

CareProvider

FamilyHistory

Problem

VPR FIM EXTENSION

ProblemExtension

VPR GRENADA SERVICE

Conflict

4

4

200

9000010.23

783

783

2

VPR HEALTH CONCERN

VPR HEALTH FACTOR

HealthConcern

DiagnosisCode

9000010.23

9999999.64

VPR HF EXTENSION

HealthConcernExtension

9000010.23

VPR ICD

DiagnosisCode

80

VPR ICR ADMINISTRATION

Administration

9000010.707

VPR ICR CONTRAINDICATION

ObservationValueCode

920.4

VPR ICR EVENT

Vaccination

9000010.707

VPR ICR EXTENSION

VaccinationExtension

9000010.707

VPR ICR OBSERVATION

Observation

9000010.707

VPR ICR REFUSAL

ObservationValueCode

920.5

VPR IMM ADMINISTRATION

Administration

9000010.11

VPR IMM EXTENSION

VaccinationExtension

9000010.11

VPR IMM MANUFACTURER

Manufacturer

9999999.04

VPR IMM ROUTE

VPR IMM SITE

VPR IMM VIS

VPR IMMUNIZATION

Route

AdministrationSite

VIS

OrderItem

VPR INS COMPANY ADDRESS

Address

VPR INS GROUP NAME

HealthFundPlan

VPR INSURANCE

MemberEnrollment

VPR INSURANCE COMPANY

HealthFundCode

920.2

920.3

920

9999999.14

36

355.3

2.312

36

Virtual Patient Record (VPR) 1.0
Developer’s Guide

105

July 2022

Display Name
(SDA Container or class)

Primary Source
Sub/File#

Name

VPR INSURANCE PLAN

VPR INSURED ADDRESS

VPR IV PRODUCT

VPR LAB FACILITY

VPR LAB ORDER

VPR LAB TEST

VPR LAB URGENCY

VPR LANGUAGE

VPR LEBANON SERVICE

HealthFund

Address

DrugProduct

Organization

LabOrder

LabTestItem

Priority

Language

Conflict

2.312

2.312

50

4

100

60

62.05

.85

2

44

VPR LOCATION

HealthCareFacility

VPR LOCATION EXTENSION

HealthCareFacilityExtension  44

VPR LOINC

ObservationValueCode

VPR LR RESULT EXTENSION

ResultExtension

VPR LRAP EXTENSION

DocumentExtension

VPR LRAP REPORT

VPR LRCH RESULT

Document

Result

VPR LRCH RESULT EXTENSION

ResultExtension

VPR LRCH RESULT ITEM

ResultItem

VPR LRCH RESULT ITEM
EXTENSION

VPR LRCY RESULT

VPR LREM RESULT

LabResultItemExtension

Result

Result

VPR LRMI EXTENSION

DocumentExtension

VPR LRMI REPORT

VPR LRMI RESULT

VPR LRSP RESULT

Document

Result

Result

VPR MARITAL STATUS

MaritalStatus

VPR MAS MOVEMENT TYPE

MovementType

VPR MAS TRANSACTION TYPE

TransactionType

VPR MDD PROCEDURE

ClinicalProcedure

VPR MED ADMINISTRATION

Administration

95.3

63

63.08

63.08

63.04

63.04

63.04

63.04

63.09

63.02

63.05

63.05

63.05

63.08

11.99

405.1

405.3

702.01

53.79

Virtual Patient Record (VPR) 1.0
Developer’s Guide

106

July 2022

Name

Display Name
(SDA Container or class)

Primary Source
Sub/File#

VPR MED EXTENSION

MedicationExtension

VPR MED FILL

VPR MED ROUTE

VPR MEDICATION

VPR NAME

Fill

Route

Medication

Name

VPR ORDER EXTENSION

OrderExtension

VPR ORDER STATUS

OrderStatus

VPR ORDER URGENCY

VPR ORDERABLE ITEM

Priority

Order

VPR ORDERABLE ITEM CODE

NationalItem

VPR ORDERABLE ITEM EXTENSION  OrderExtension

VPR OTHER ORDER

VPR PACKAGE

VPR PANAMA SERVICE

OtherOrder

Package

Conflict

VPR PAT TEMP ADD EXTENSION

AddressExtension

VPR PATIENT

VPR PATIENT ADDRESS

VPR PATIENT ADDRESS
EXTENSION

VPR PATIENT ALIAS

VPR PATIENT AO

VPR PATIENT BIRTHPLACE

VPR PATIENT DISABILITY

Patient

Address

AddressExtension

Alias

Exposure

Address

Disability

VPR PATIENT ECON

SupportContact

VPR PATIENT ECON ADDRESS

Address

VPR PATIENT ECON2

SupportContact

VPR PATIENT ECON2 ADDRESS

Address

VPR PATIENT ELIGIBILITY

Eligibility

VPR PATIENT EMPLOYER

SupportContact

VPR PATIENT EMPLOYER ADDRESS  Address

100

52

51.2

100

n/a

100

100.01

101.42

101.43

101.43

101.43

100

9.4

2

2

2

2

2

2.01

2

2

2.04

2

2

2

2

8

2

2

VPR PATIENT ENROLLMENT

Enrollment

2.001

Virtual Patient Record (VPR) 1.0
Developer’s Guide

107

July 2022

Name

Display Name
(SDA Container or class)

Primary Source
Sub/File#

VPR PATIENT EXTENSION

PatientExtension

VPR PATIENT ID

VPR PATIENT IR

PatientID

Exposure

2

2

2

VPR PATIENT LANGUAGE

PatientLanguage

2.07

VPR PATIENT MILITARY SERVICE

ServiceEpisode

VPR PATIENT NOK

SupportContact

VPR PATIENT NOK ADDRESS

Address

VPR PATIENT NOK2

SupportContact

VPR PATIENT NOK2 ADDRESS

Address

VPR PATIENT NUMBER

PatientNumber

VPR PATIENT RECORD FLAG

Alert

VPR PATIENT SWA

VPR PATIENT TEMP ADDRESS

VPR PERSIAN GULF SERVICE

Exposure

Address

Conflict

2

2

2

2

2

2

26.13

2

2

2

VPR PERSON CLASS

CareProviderType

8932.1

VPR PERSON CLASS EXTENSION

CareProviderTypeExtension  8932.1

VPR POW STATUS

VPR PREGNANCY

VPR PRF DBRS RECORD

VPR PRF EXTENSION

VPR PRF HISTORY

VPR PROBLEM

Conflict

SocialHistory

DBRSRecord

AlertExtension

Assignment

Problem

VPR PROBLEM EXTENSION

ProblemExtension

VPR PROCEDURE

Procedure

VPR PROCEDURE EXTENSION

ProcedureExtension

VPR PROVIDER

CareProvider

VPR PROVIDER EXTENSION

CareProviderExtension

VPR PTF

Diagnosis

VPR PTF EXTENSION

DiagnosisExtension

VPR RACE

Race

2

790.05

26.131

26.13

26.14

9000011

9000011

702

702

200

200

45

45

10.99

Virtual Patient Record (VPR) 1.0
Developer’s Guide

108

July 2022

Display Name
(SDA Container or class)

Primary Source
Sub/File#

Name

VPR RAD ORDER

VPR RAD REPORT

VPR RAD RESULT

RadOrder

Document

Result

VPR RAD RESULT EXTENSION

ResultExtension

VPR RAD RPT EXTENSION

DocumentExtension

VPR REFERRAL

Referral

100

74

70.03

74

74

123

VPR REFERRAL ACTIVITY

RequestAction

123.02

VPR REFERRAL EXTENSION

ReferralExtension

VPR REFERRING PROVIDER

CareProvider

VPR RELIGION

Religion

VPR SCH ADM EXTENSION

AppointmentExtension

VPR SCHEDULED ADMISSION

Appointment

VPR SIGNER

CareProvider

VPR SIGNER EXTENSION

CareProviderExtension

123

123

13

41.1

41.1

200

200

VPR SOCIAL HISTORY

VPR SOMALIA SERVICE

VPR SOURCE FACILITY

VPR SPECIALTY

VPR STATE

VPR SURGERY

SocialHistory

Conflict

LastTreated

CareProviderType

State

Procedure

VPR SURGERY EXTENSION

ProcedureExtension

VPR TEAM MEMBER

VPR TEXT ONLY

VPR USER

VPR V CPT

VPR V EXAM

VPR V POV

VPR V PROVIDER

VPR VACC HF ADMIN

CareProvider

CodeTable

User

Procedure

PhysicalExam

Diagnosis

CareProvider

Administration

9000010.23

2

2

45.7

5

130

130

200

n/a

200

9000010.18

9000010.13

9000010.07

9000010.06

9000010.23

VPR VACC HF EXT

VaccinationExtension

9000010.23

Virtual Patient Record (VPR) 1.0
Developer’s Guide

109

July 2022

Name

Display Name
(SDA Container or class)

Primary Source
Sub/File#

VPR VACC HF REFUSAL

VPR VACCINATION

Vaccination

Vaccination

9000010.23

9000010.11

VPR VCPT EXTENSION

ProcedureExtension

9000010.18

VPR VFILE DELETE

VPR VIETNAM SERVICE

VPR VISIT

VFile

Conflict

Encounter

VPR VISIT EXTENSION

EncounterExtension

VPR VISIT STUB

Encounter

VPR VITAL EXTENSION

ObservationExtension

VPR VITAL MEASUREMENT

Observation

VPR VITAL QUALIFIER

ObservationMethods

VPR VITAL TYPE

ObservationCode

VPR WARD LOCATION

WardLocation

VPR YUGOSLAVIA SERVICE

Conflict

n/a

2

9000010

9000010

9000010

120.5

120.5

120.52

120.51

42

2

5.2  Data Update Events
Patch VPR*1*8 installed a mechanism to monitor clinical data events in VistA, to enable
retrieval of updated information as a patient's data changes. VPR*1*10 adds new PROTOCOL
(#101) file entries and links to other appropriate clinical application events to capture the records
that have changed, as well as new patients.

Patient data is extracted when it is no longer in a draft status, usually electronically signed or in a
completed or verified state. Requests for future action, such as orders or appointments, can be
removed from the ECR if cancelled before being performed. Records that are retracted or
marked as in error are also removed.

5.2.1  Protocol Events
VPR added listeners to the HL7 event protocols listed in Table 57:

Table 57: VPR HL7 Event Protocols and Associated Listeners

Event Protocol

RMIM DRIVER

Listener

VPR RMIM EVENTS

VAFC ADT-A08 SERVER

VPR ADT-A08 CLIENT

Virtual Patient Record (VPR) 1.0
Developer’s Guide

110

July 2022

VPR also monitors the non-HL7 event protocols listed in Table 58:

Table 58: VPR Non-HL7 Event Protocols and Associated Listeners

Event Protocol

DG FIELD MONITOR

Listener

VPR DG UPDATES

DG PTF ICD DIAGNOSIS NOTIFIER

VPR PTF EVENTS

DG SA FILE ENTRY NOTIFIER

DGPF PRF EVENT

DGPM MOVEMENT EVENTS

FH EVSEND OR

GMPL EVENT

VPR DGS EVENTS

VPR PRF EVENTS

VPR INPT EVENTS

VPR XQOR EVENTS

VPR GMPL EVENT

GMRA ASSESSMENT CHANGE

VPR GMRA ASSESSMENT

GMRA ENTERED IN ERROR

VPR GMRA ERROR EVENTS

GMRA SIGN-OFF ON DATA

GMRA VERIFY DATA

GMRC EVSEND OR

VPR GMRA EVENTS

VPR GMRA EVENTS

VPR XQOR EVENTS

IBCN NEW INSURANCE EVENTS

VPR IBCN EVENTS

LR7O AP EVSEND OR

LR7O CH EVSEND OR

OR EVSEND FH

OR EVSEND GMRC

OR EVSEND LRCH

OR EVSEND ORG

OR EVSEND PS

OR EVSEND RA

OR EVSEND VPR

PS EVSEND OR

PSB EVSEND VPR

PXK VISIT DATA EVENT

RA EVSEND OR

VPR XQOR EVENTS

VPR XQOR EVENTS

VPR NA EVENTS

VPR NA EVENTS

VPR NA EVENTS

VPR XQOR EVENTS

VPR NA EVENTS

VPR NA EVENTS

VPR XQOR EVENTS

VPR XQOR EVENTS

VPR PSB EVENTS

VPR PCE EVENTS

VPR XQOR EVENTS

SCMC PATIENT TEAM CHANGES

VPR PCMM TEAM

SCMC PATIENT TEAM POSITION CHANGES

VPR PCMM TEAM POSITION

Virtual Patient Record (VPR) 1.0
Developer’s Guide

111

July 2022

Event Protocol

Listener

SDAM APPOINTMENT EVENTS

VPR APPT EVENTS

TIU DOCUMENT ACTION EVENT

VPR TIU RETRACT

WV PREGNANCY STATUS CHANGE EVENT

VPR PREGNANCY EVENT

5.2.2  MUMPS Index
Two VistA files that require data monitoring do not have a protocol event, so the MUMPS-type
cross references in Table 59 were created to call a VPR listener routine on edits:

Table 59: VPR MUMPS Cross Reference Listeners

File

TIU DOCUMENT (#8925)

GMRV VITAL MEASUREMENT (#120.5)

Index

AEVT

AVPR

5.2.3  Tasked Events
Most events process updates immediately, making changes available to the ECR in near real
time. Some event updates need to be tasked but usually run within 10-15 minutes.

5.2.3.1  Patient Demographics

The VistA Registration package fires the DG FIELD MONITOR protocol for every field that is
changed in the PATIENT (#2) file, but the entire Patient container is updated all at once. The
VPR DG UPDATES listener creates a task the first time it runs, which waits 10 minutes before
adding the Patient container to the upload list; the task number is saved in the VPR
SUBSCRIPTION (#560) file until it runs. When the DG event fires for another field, the VPR
listener simply quits if a task number already exists.

5.2.3.2  Encounters (PCE)

When encounters are created or edited via the Computerized Patient Record System (CPRS), that
data is passed to the Patient Care Encounter (PCE) application which fires the PXK VISIT
DATA EVENT protocol. This process can happen multiple times during a single user session,
so the VPR PCE EVENTS listener collects the identifiers of all modified records in ^XTMP in
the following format:

^XTMP("VPRPX",0) = descriptor node
^XTMP("VPRPX",visit~dfn) = NOW ^ visit;9000010 ^ 1 if new
^XTMP("VPRPX",visit~dfn,vFile,ien) = 1 if new
^XTMP("VPRPX","ZTSK") = current task number

Virtual Patient Record (VPR) 1.0
Developer’s Guide

112

July 2022

It then fires off a task (if one does not already exist) to check ^XTMP in 5 minutes; if the
encounter has been stable and unchanged for at least 2 minutes, it is moved to the AVPR upload
list along with any related PCE records. If any encounters remain in ^XTMP at the end of the
task, it requeues itself to repeat this process until all records have been moved to the upload list.

PCE records can be deleted in VistA, and these are also then removed from the ECR. If the flag
in ^XTMP is true (1), then the ^XTMP nodes are simply killed, because the record was never
sent to the ECR. If the record was not new, a copy of the deleted zero node is saved in ^XTMP
by upload sequence number so the SDA message can still be built when requested from the ECR:

^XTMP("VPR-seq",0) = descriptor node
^XTMP("VPR-seq",ien) = DFN ^ Container ^ ien;file# ^ D ^ visit
^XTMP("VPR-seq",ien,0) = zero node of deleted record

5.2.3.3  Documents (TIU)

The TIU Document event is an index, so it can fire multiple times during a single user session.
Documents are also usually linked to a visit, but the visit number assignment is tasked, and thus,
often saved after the note has been marked as complete and the index is executed. HealthShare
requires the encounter to be uploaded to the ECR first, before any data linked to that encounter.

For these reasons, TIU Documents also use the same process and task as Encounters to
populate the upload list. Document identifiers are also saved in ^XTMP in the following format:

^XTMP("VPRPX","DOC",ien) = NOW ^ ien;8925

The encounter task looks for any waiting documents tied to each visit processed, to ensure that a
document’s encounter is uploaded first. Any other waiting documents are then also moved to the
upload list when stable for at least 5 minutes.

5.3  VPR Subscription File and Indexes
When the RHC servers were first brought up, a job was fired off that called into each connected
VistA system and pre-loaded the clinical data of active patients. A patient was considered active
if s/he was a current inpatient, had been seen in the past 5 years, or had scheduled appointments;
they were also required to have an ICN and no date of death. These patients were saved in the
VPR SUBSCRIPTION (#560) file. Monitoring of new patients and data update events was also
enabled at this time, and those changes are tracked in this file.

5.3.1  VPR Subscription File
The VPR SUBSCRIPTION (#560) file tracks the subscription status of patients for inclusion in
the ECR. If subscribed, data changes detected for that patient are tracked in the Patients sub-file
and indexed for fast retrieval by HS in either of the following indexes:

•  ^VPR(“ANEW”)

•  ^VPR(“AVPR”)

Virtual Patient Record (VPR) 1.0
Developer’s Guide

113

July 2022

5.3.2  ANEW Index
New, or newly active, patients are added to the ANEW index when VistA clinical activity is
detected. The RHC monitors this index to register and subscribe to these patients. Once
subscribed, the RHC will then automatically upload all of that patient’s current data into
HealthShare. The ANEW index is subscripted by a sequence number and patient DFN, and also
includes the ICN:

^VPR("ANEW",9,224)="10111V183702"

The RHC removes the ANEW index node when it has registered the patient.

5.3.3  AVPR Index
Once a patient is subscribed to, changes to his/her clinical data results in a node added to the
AVPR index. Like the ANEW index, the AVPR index is subscripted by a sequence number and
the patient DFN. Changes are applied to the ECR in order; AVPR saves more data to know what
record has been updated, including:

•  Patient ICN

•  SDA Container Name

•  Record ID, which consists of two semi-colon pieces:

o  Internal entry number, or a string that uniquely identifies the record to the Entity
o  VistA source file or sub-file number

•  Action Code:

o  U—Update
o  D—Delete

•  Visit Number (if available)

For example:

^VPR("AVPR",1,229)="10104V248233^Problem^940;9000011^U^"

^VPR("AVPR",2,229)="10104V248233^OtherOrder^33751;100^U^"

^VPR("AVPR",3,229)="10104V248233^Referral^618;123^U^"

^VPR("AVPR",4,229)="10104V248233^Appointment^3190524.1128,229;2.98^U^"

^VPR("AVPR",5,229)="10104V248233^Document^4239;8925^U^7200"

Like ANEW, the RHC removes the AVPR index node when it has uploaded the record.

Virtual Patient Record (VPR) 1.0
Developer’s Guide

114

July 2022

5.4  VPRHS Utilities
The VPRHS routine contains the utility functions needed to directly support the RHC servers.
These APIs are only used within VPR or by Health Connect (HC). They are documented in this
document to help system administrators who support with the HC interface.

There are no ICR for these APIs; they are only used within VPR or by Health Connect (HC).

5.4.1  $$ON^VPRHS: System Monitoring On/Off

Description

The $$ON^VPRHS extrinsic function returns the current status of the data monitoring utilities.

The VPR event listeners use this function to verify that data should be passed to HealthShare. If
the system has been stopped for any reason, no data will be uploaded and the listener quits.

Format

$$ON^VPRHS

Input Parameters

None.

Output

Returns

5.4.1.1  Example

>W $$ON^VPRHS
1

This Boolean function returns the following:

•  1—If system monitoring of data events is active.

•  0—If system monitoring of data events is not active.

5.4.2  EN^VPRHS(): Subscribe a Patient

Description

The EN^VPRHS API adds a patient to the VPR SUBSCRIPTION (#560) file for data
monitoring.

The RHC server calls this API during the patient subscription process.

Format

EN^VPRHS(dfn)

Input Parameters

dfn:

(Required) Pointer to the PATIENT (#2) file.

Virtual Patient Record (VPR) 1.0
Developer’s Guide

115

July 2022

Output

None.

5.4.2.1  Example

>S DFN=229 D EN^VPRHS(DFN)

5.4.3  UN^VPRHS(): Unsubscribe a Patient

Description

The UN^VPRHS API removes a patient from the VPR SUBSCRIPTION (#560) file to stop data
monitoring for that patient.

The RHC server calls this API when a patient is removed from the data cache and data
subscription is stopped.

Format

UN^VPRHS(dfn)

Input Parameters

dfn:

(Required) Pointer to the PATIENT (#2) file.

Output

None.

5.4.3.1  Example

>S DFN=229 D UN^VPRHS(DFN)

Virtual Patient Record (VPR) 1.0
Developer’s Guide

116

July 2022

5.4.4  $$SUBS^VPRHS(): Subscription Status of a Patient

Description

The $$SUBS^VPRHS extrinsic function returns the current subscription status of a patient.

The POST^VPRHS API uses this function to determine if changes to this patient’s clinical data
are currently being tracked in HealthShare.

Format

$$SUBS^VPRHS(dfn)

Input Parameters

dfn:

(Required) Pointer to the PATIENT (#2) file.

Output

Returns

This Boolean function returns the following:

•  1—If the patient is currently subscribed.

•  0—If the patient is not currently subscribed.

5.4.4.1  Example

>S DFN=229 W $$SUBS^VPRHS(DFN)
0

Virtual Patient Record (VPR) 1.0
Developer’s Guide

117

July 2022

5.4.5  $$VALID^VPRHS(): Validation of a Patient for HealthShare

Description

The $$VALID^VPRHS extrinsic function evaluates a patient for possible subscription for data
monitoring in HealthShare. Patients:

•  Must have an ICN.

•  Cannot be deceased or merged.

•  Cannot be marked as test patients on a Production system.

The POST^VPRHS API uses this function when clinical data is added or modified for a patient
that is not currently subscribed.

Format

$$VALID^VPRHS(dfn)

Input Parameters

dfn:

(Required) Pointer to the PATIENT (#2) file.

Output

Returns

This Boolean function returns the following:

•  1—If the patient is valid for subscription.

•  0—If the patient is not valid for subscription.

5.4.5.1  Example

>S DFN=224 W $$VALID^VPRHS(DFN)
1

Virtual Patient Record (VPR) 1.0
Developer’s Guide

118

July 2022

5.4.6  POST^VPRHS(): Add Record to AVPR Index for Uploading

Description

The POST^VPRHS API adds a node to the AVPR upload index when clinical activity occurs in
VistA for a subscribed patient. If the patient is not subscribed but is eligible, control is passed to
the NEW^VPRHS API for subscribing. The RHC then automatically uploads all of the patient’s
data.

The VPR event listeners use this API when clinical data is added or modified for a patient:

•

•

•

If the patient is subscribed, an entry is made in the ^VPR(“AVPR”) index.

If the patient is not subscribed but passes the checks in the $$VALID^VPRHS function,
then a request to register the patient in HealthShare is posted in the ^VPR(“ANEW”)
index instead.

If the patient is neither subscribed nor eligible for subscription, nothing is uploaded and
the API quits.

Format

POST^VPRHS(dfn,type,id,action,visit[,.seq])

Input Parameters

(Required) Pointer to the PATIENT (#2) file.

(Required) Name of the SDA container where the data is to be stored.

(Required) Record identifier, in the format:

internal entry number_“;”_VistA source file number

(Required) NULL to update the record, or “@” to delete it from
HealthShare.

(Required) Pointer to the related VISIT (#9000010) entry, if applicable.

(Optional) Parameter to return the assigned sequence number in the
AVPR or ANEW upload lists, must be passed by reference.

dfn:

type:

id:

action:

visit:

.seq:

Output

This API does not directly return any results. If successful, however:

•  A node is added to the AVPR or ANEW index.

•  The sequence number assigned may optionally be returned in the SEQ parameter.

Virtual Patient Record (VPR) 1.0
Developer’s Guide

119

July 2022

5.4.6.1  Example

>D POST^VPRHS(229,"Problem","644;9000011")

5.4.7  NEW^VPRHS(): Add Patient to ANEW Index for Subscribing

Description

The NEW^VPRHS API adds a node to the ANEW upload index when clinical activity occurs in
VistA for an unsubscribed patient.

The POST^VPRHS API calls this API when a valid patient needs to be registered in HealthShare
and subscribed for data monitoring. The RHC server registers and subscribes the patient, and
then retrieves all current data for the patient so individual record identifiers do not need to be
passed here.

Format

NEW^VPRHS(dfn[,icn])

Input Parameters

(Required) Pointer to the PATIENT (#2) file.

(Optional) ICN of patient. If not defined, it retrieves the ICN from the
PATIENT (#2) file.

dfn:

icn:

Output

This API does not directly return any results. If successful, however, a node is added to the
ANEW index.

5.4.7.1  Example

>S DFN=229 D NEW^VPRHS(DFN)

Virtual Patient Record (VPR) 1.0
Developer’s Guide

120

July 2022

5.4.8  DEL^VPRHS(): Remove Nodes from ANEW or AVPR Upload

Index

Description

The DEL^VPRHS API removes a node from the ANEW or AVPR upload index after the RHC
has processed the patient or record.

The RHC server calls this API to remove nodes from the index after processing.

Format

DEL^VPRHS(list,seq)

Input Parameters

(Required) Name of the index, either “ANEW” or “AVPR”.

(Required) Sequence number in the index of the node to be removed.

list:

seq:

Output

This API does not directly return any results. If successful, however, the node disappears from
the specified index.

5.4.8.1  Example

>D DEL^VPRHS("AVPR",5873294)

Virtual Patient Record (VPR) 1.0
Developer’s Guide

121

July 2022

5.4.9  GET^VPRHS(): Retrieve Patient Data for ECR

Description

The GET^VPRHS API retrieves data from VistA in SDA format for HealthShare. The input
parameters are used to call the VA FileMan DDE utility GET^DDE API for the appropriate
ENTITY (#1.5) file entries, collecting and returning the results and optionally any errors that
may occur.

The RHC server calls this API when data upload requests are put into the AVPR or ANEW
index. For AVPR nodes, GET is called using the data saved in the index node as the input
parameters to request a specific record. For ANEW, the RHC server requests a whole container
at a time to retrieve all current data for the patient.

Format

GET^VPRHS(dfn,type[,id][,.query],format,results,errors)

Input Parameters

dfn:

type:

id:

(Required) Pointer to the PATIENT (#2) file.

(Required) Name of the desired SDA Container.

(Optional) Record identifier, in the format:

internal entry number_“;”_VistA source file number

If not defined, the entire container is returned based on Query.

.query(“name”):

(Optional) Array of search conditions as a list of name-value pairs, passed
by reference. This parameter is optional and not used if the id parameter is
defined.

Commonly used search parameters include:

QUERY(“start”) = VA FileMan formatted date.time
QUERY(“stop”) = VA FileMan formatted date.time
QUERY(“max”) = Maximum number of items to return

Others may be supported by a specific Entity, such as a status One value is
used when ID is defined, to retrieve stored data for deleted records:

QUERY(“sequence”) = AVPR list item being processed

format:

(Required) Format for results:

•  0=JSON.

•  1=XML (default).

Virtual Patient Record (VPR) 1.0
Developer’s Guide

122

July 2022

results:

(Required) Closed array name for returning results, default is:

^TMP(“VPR GET”,$J,#)

errors:

(Required) Closed array name for returning errors, default is:

^TMP(“VPR ERR”,$J,#)

Output

Returns:

This API return results in the specified array or ^TMP global, a single
record per list item. The total number of records returned is in the zero
node of the array.

5.4.9.1  Examples

5.4.9.1.1  Example 1

>D GET^VPRHS(229,"Problem","644;9000011",,1,"VPRESLT") ZW VPRESLT
VPRESLT(0)=1
VPRESLT(1)="<Problem><UpdatedOn>2007-04-10T00:00:00</UpdatedOn><Extension><IsExp
osureAO>false</IsExposureAO><IsExposureIR>false</IsExposureIR><IsExposurePG>fals
e</IsExposurePG><IsSc>false</IsSc><Service>MEDICAL</Service><OnsetDate>2005-04-0
7</OnsetDate><LexiconId>60339</LexiconId><Priority>CHRONIC</Priority></Extension
><ProblemDetails>Hypertension</ProblemDetails><Problem><SDACodingStandard>ICD-9-
CM</SDACodingStandard><Code>401.9</Code><Description>HYPERTENSION NOS</Descripti
on></Problem><Clinician><SDACodingStandard>VA200</SDACodingStandard><Extension><
Title>Scholar Extraordinaire</Title></Extension><Code>10000000031</Code><Descrip
tion>VEHU,ONEHUNDRED</Description><Name><FamilyName>VEHU</FamilyName><GivenName>
ONEHUNDRED</GivenName></Name></Clinician><Status><SDACodingStandard>SNOMED CT</S
DACodingStandard><Code>55561003</Code><Description>Active</Description></Status>
<EnteredBy><SDACodingStandard>VA200</SDACodingStandard><Code>10000000031</Code><
Description>VEHU,ONEHUNDRED</Description></EnteredBy><EnteredAt><SDACodingStanda
rd>VA4</SDACodingStandard><Code>500</Code><Description>CAMP MASTER</Description>
</EnteredAt><EnteredOn>2007-04-10T00:00:00</EnteredOn><FromTime>2005-04-07T00:00
:00</FromTime><ExternalId>644;PL</ExternalId></Problem>"

Virtual Patient Record (VPR) 1.0
Developer’s Guide

123

July 2022

5.4.9.1.2  Example 2

>S QRY("start")=2991101,QRY("stop")=2991130,QRY("max")=2
>D GET^VPRHS(129,"Encounter",,.QRY,1,"VPRESLT") ZW VPRESLT
VPRESLT(0)=2
VPRESLT(1)="<Encounter><Extension><StopCode><SDACodingStandard>AMIS</SDACodingSt
andard><Code>328</Code><Description>MEDICAL/SURGICAL DAY UNIT MSDU</Description>
</StopCode></Extension><EncounterNumber>1822</EncounterNumber><EncounterType>O</
EncounterType><EncounterCodedType><Code>A</Code><Description>AMBULATORY</Descrip
tion></EncounterCodedType><ConsultingClinicians><CareProvider><SDACodingStandard
>VA200</SDACodingStandard><Extension><Role>PRIMARY</Role><Title>Scholar Extraord
inaire</Title></Extension><Code>11712</Code><Description>PROVIDER,TWOHUNDREDNINE
TYSEVEN</Description><Name><FamilyName>PROVIDER</FamilyName><GivenName>TWOHUNDRE
DNINETYSEVEN</GivenName></Name><CareProviderType><SDACodingStandard>X12</SDACodi
ngStandard><Extension><Classification>Physician/Osteopath</Classification></Exte
nsion><Code>203B00000N</Code><Description>Physicians (M.D. and D.O.)</Descriptio
n></CareProviderType></CareProvider></ConsultingClinicians><HealthCareFacility><
SDACodingStandard>VA44</SDACodingStandard><Extension><StopCode><SDACodingStandar
d>AMIS</SDACodingStandard><Code>328</Code><Description>MEDICAL/SURGICAL DAY UNIT
 MSDU</Description></StopCode><CreditStopCode><SDACodingStandard>AMIS</SDACoding
Standard><Code>328</Code><Description>MEDICAL/SURGICAL DAY UNIT MSDU</Descriptio
n></CreditStopCode><Service>MEDICINE</Service></Extension><Code>261</Code><Descr
iption><![CDATA[MIKE'S MEDICAL CLINIC]]></Description><LocationType>OTHER</Locat
ionType></HealthCareFacility><Priority><Code>P</Code><Description>PRIMARY</Descr
iption></Priority><EnteredBy><SDACodingStandard>VA200</SDACodingStandard><Code>1
1712</Code><Description>PROVIDER,TWOHUNDREDNINETYSEVEN</Description></EnteredBy>
<EnteredAt><SDACodingStandard>VA4</SDACodingStandard><Code>500</Code><Descriptio
n>CAMP MASTER</Description></EnteredAt><EnteredOn>1999-11-22T11:13:45</EnteredOn
><FromTime>1999-11-22T11:13:12</FromTime><ToTime>1999-11-22T11:13:00</ToTime></E
ncounter>"
VPRESLT(2)="<Encounter><Extension><Cpt><SDACodingStandard>CPT-4</SDACodingStanda
rd><Code>99201</Code><Description><![CDATA[OFFICE OR OTHER OUTPATIENT VISIT FOR
THE EVALUATION AND MANAGEMENT OF A NEW PATIENT, WHICH REQUIRES THESE THREE KEY C
OMPONENTS: A PROBLEM FOCUSED HISTORY; A PROBLEM FOCUSED EXAMINATION; AND STRAIGH
TFORWARD MEDICAL DECISION MAKING. COUNSELING AND/OR COORDINATION OF CARE WITH OT
HER PROVIDERS OR AGENCIES ARE PROVIDED CONSISTENT WITH THE NATURE OF THE PROBLEM
(S) AND THE PATIENT'S AND/OR FAMILY'S NEEDS. USUALLY, THE PRESENTING PROBLEMS AR
E SELF LIMITED OR MINOR. PHYSICIANS TYPICALLY SPEND 10 MINUTES FACE-TO-FACE WITH
 THE PATIENT AND/OR FAMILY.]]></Description></Cpt><StopCode><SDACodingStandard>A
MIS</SDACodingStandard><Code>401</Code><Description>GENERAL SURGERY</Description
></StopCode></Extension><EncounterNumber>1806</EncounterNumber><EncounterType>O<
/EncounterType><EncounterCodedType><Code>A</Code><Description>AMBULATORY</Descri
ption></EncounterCodedType><ConsultingClinicians><CareProvider><SDACodingStandar
d>VA200</SDACodingStandard><Extension><Role>PRIMARY</Role><Title>Scholar Extraor
dinaire</Title></Extension><Code>11712</Code><Description>PROVIDER,TWOHUNDREDNIN
ETYSEVEN</Description><Name><FamilyName>PROVIDER</FamilyName><GivenName>TWOHUNDR
EDNINETYSEVEN</GivenName></Name><CareProviderType><SDACodingStandard>X12</SDACod
ingStandard><Extension><Classification>Physician/Osteopath</Classification></Ext
ension><Code>203B00000N</Code><Description>Physicians (M.D. and D.O.)</Descripti
on></CareProviderType></CareProvider></ConsultingClinicians><HealthCareFacility>
<SDACodingStandard>VA44</SDACodingStandard><Extension><StopCode><SDACodingStanda
rd>AMIS</SDACodingStandard><Code>401</Code><Description>GENERAL SURGERY</Descrip
tion></StopCode><Service>SURGERY</Service><Specialty><SDACodingStandard>VA45.7</
SDACodingStandard><Code>18</Code><Description>GEM ACUTE MEDICINE</Description></
Specialty></Extension><Code>91</Code><Description><![CDATA[SHERYL'S CLINIC]]></D
escription><Organization><SDACodingStandard>VA4</SDACodingStandard><Code>998</Co
de><Description>ABILENE (CAA)</Description></Organization><LocationType>OTHER</L
ocationType></HealthCareFacility><Priority><Code>P</Code><Description>PRIMARY</D
escription></Priority><EnteredBy><SDACodingStandard>VA200</SDACodingStandard><Co
de>11712</Code><Description>PROVIDER,TWOHUNDREDNINETYSEVEN</Description></Entere
dBy><EnteredAt><SDACodingStandard>VA4</SDACodingStandard><Code>500</Code><Descri

Virtual Patient Record (VPR) 1.0
Developer’s Guide

124

July 2022

ption>CAMP MASTER</Description></EnteredAt><EnteredOn>1999-11-17T11:12:10</Enter
edOn><FromTime>1999-11-17T09:00:00</FromTime><ToTime>1999-11-17T11:12:00</ToTime
></Encounter>"

5.4.10  TEST^VPRHS(): Test SDA Extract

Description

The TEST^VPRHS API retrieves data from VistA in SDA format for a single record. The input
parameters are used to call the VA FileMan $$GET1^DDE utility for the specified ENTITY
(#1.5) file entry and display the result or any errors that may occur onscreen.

This API can be used by a developer in programmer mode, for testing and debugging purposes.

Format

TEST^VPRHS(entity,id,dfn[,seq])

Input Parameters

entity:

id:

dfn:

seq:

Output

Returns:

(Required) Name of a single entry in, or pointer to, the ENTITY (#1.5) file.

(Required) Pointer to the desired record, from the VistA file defined by
the Entity’s DEFAULT FILE NUMBER (#.02) field.

(Required) Pointer to the PATIENT (#2) file.

(Optional) Sequence number of the record in the upload list.

This API executes the requested entity and displays the results onscreen,
as well as any errors that might occur.

Virtual Patient Record (VPR) 1.0
Developer’s Guide

125

July 2022

5.4.10.1 Example

>D TEST^VPRHS("VPR PROBLEM",644,229)

<Problem>
  <UpdatedOn>2007-04-10T00:00:00</UpdatedOn>
  <Extension>
    <IsExposureAO>false</IsExposureAO>
    <IsExposureIR>false</IsExposureIR>
    <IsExposurePG>false</IsExposurePG>
    <IsSc>false</IsSc>
    <Service>MEDICAL</Service>
    <OnsetDate>2005-04-07</OnsetDate>
    <LexiconId>60339</LexiconId>
    <Priority>CHRONIC</Priority>
  </Extension>
  <ProblemDetails>Hypertension</ProblemDetails>
  <Problem>
    <SDACodingStandard>ICD-9-CM</SDACodingStandard>
    <Code>401.9</Code>
    <Description>HYPERTENSION NOS</Description>
  </Problem>
  <Clinician>
    <SDACodingStandard>VA200</SDACodingStandard>
    <Extension>
      <Title>Scholar Extraordinaire</Title>
    </Extension>
    <Code>10000000031</Code>
    <Description>VEHU,ONEHUNDRED</Description>
    <Name>
      <FamilyName>VEHU</FamilyName>
      <GivenName>ONEHUNDRED</GivenName>
    </Name>
  </Clinician>
  <Status>
    <SDACodingStandard>SNOMED CT</SDACodingStandard>
    <Code>55561003</Code>
    <Description>Active</Description>
  </Status>
  <EnteredBy>
    <SDACodingStandard>VA200</SDACodingStandard>
    <Code>10000000031</Code>
    <Description>VEHU,ONEHUNDRED</Description>
  </EnteredBy>
  <EnteredAt>
    <SDACodingStandard>VA4</SDACodingStandard>
    <Code>500</Code>
    <Description>CAMP MASTER</Description>
  </EnteredAt>
  <EnteredOn>2007-04-10T00:00:00</EnteredOn>
  <FromTime>2005-04-07T00:00:00</FromTime>
  <ExternalId>644;PL</ExternalId>
</Problem>
>

Virtual Patient Record (VPR) 1.0
Developer’s Guide

126

July 2022

5.5  Generating Online Documentation
Use VA FileMan options to generate and display online documentation to get the most current
information about the VPR-SDA interface.

5.5.1  VPR CONTAINER (#560.1) File
The VPR CONTAINER (#560.1) file contains information about each SDA container class that
has been implemented. The SOURCE FILE sub-file defines each VistA source for that container,
and the Entities used to build SDA messages for each source.

Use the Print File Entries option [DIPRINT] of VA FileMan to display the contents of the VPR
CONTAINER (#560.1) file, as shown in Figure 5. The VPR CONTAINER SOURCES Print
template can be used to show the primary Entities for each container and source.

Virtual Patient Record (VPR) 1.0
Developer’s Guide

127

July 2022

Figure 5: Print File Entries Option—Displaying the VPR CONTAINER (#560.1) File Contents

Select OPTION: PRINT FILE ENTRIES

Output from what File: VPR CONTAINER// <Enter> (24 entries)
Sort by: NAME// <Enter>
Start with NAME: FIRST// <Enter>
First Print FIELD: [VPR CONTAINER SOURCES
                              (JUL 22, 2021@12:17) User #11948 File #560.1
Do you want to edit the 'VPR CONTAINER SOURCES' Template? No// <Enter>
(No)
Heading (S/C): VPR CONTAINER List// <Enter>
DEVICE: 0;80;99 <Enter> Linux Telnet /SSh

VPR CONTAINER List                             JUL 22, 2021@12:54   PAGE 1
NAME                 DISPLAY NAME
SOURCE FILE
NUMBER               UPDATE ENTITY            DELETE ENTITY
--------------------------------------------------------------------------

ADVANCE DIRECTIVE    AdvanceDirective
8925                 VPR ADVANCE DIRECTIVE

ALERT                Alert
26.13                VPR PATIENT RECORD FLAG
8925                 VPR CW NOTES

ALLERGY              Allergy
120.8                VPR ALLERGY
120.86               VPR ALLERGY ASSESSMENT

APPOINTMENT          Appointment
2.98                 VPR APPOINTMENT
41.1                 VPR SCHEDULED ADMISSION

DIAGNOSIS            Diagnosis
9000010.07           VPR V POV                VPR DEL V POV
45                   VPR PTF                  VPR DEL PTF

DOCUMENT             Document
8925                 VPR DOCUMENT             VPR DEL TIU DOCUMENT
74                   VPR RAD REPORT
63.05                VPR LRMI REPORT
63.08                VPR LRAP REPORT

ENCOUNTER            Encounter
9000010              VPR VISIT                VPR VISIT STUB
405                  VPR ADMISSION
230                  VPR EDP LOG

FAMILY HISTORY       FamilyHistory
9000010.23           VPR FAMILY HISTORY       VPR DEL FAMILY HX

ILLNESS HISTORY      IllnessHistory

LAB ORDER            LabOrder
100                  VPR LAB ORDER

Virtual Patient Record (VPR) 1.0
Developer’s Guide

128

July 2022

MEDICAL CLAIM        MedicalClaim

MEDICATION           Medication
100                  VPR MEDICATION

MEMBER ENROLLMENT    MemberEnrollment
2.312                VPR INSURANCE

OBSERVATION          Observation
120.5                VPR VITAL MEASUREMENT

OTHER ORDER          OtherOrder
100                  VPR OTHER ORDER

PATIENT              Patient
2                    VPR PATIENT

PHYSICAL EXAM        PhysicalExam
9000010.13           VPR V EXAM               VPR DEL V EXAM

PROBLEM              Problem
9000011              VPR PROBLEM
783                  VPR FIM

PROCEDURE            Procedure
130                  VPR SURGERY
9000010.18           VPR V CPT                VPR DEL V CPT

PROGRAM MEMBERSHIP   ProgramMembership

RAD ORDER            RadOrder
100                  VPR RAD ORDER

REFERRAL             Referral
123                  VPR REFERRAL

SOCIAL HISTORY       SocialHistory
9000010.23           VPR SOCIAL HISTORY       VPR DEL SOCIAL HX
790.05               VPR PREGNANCY

VACCINATION          Vaccination
9000010.11           VPR VACCINATION          VPR DEL VACCINATION
9000010.23           VPR VACC HF REFUSAL      VPR DEL HF VACC REFUSAL
9000010.707          VPR ICR EVENT            VPR DEL ICR

The UPDATE ENTITY (Figure 5) is used to build most SDA messages, to send a new or
updated record from VistA to the ECR. The DELETE ENTITY (Figure 5) is used to build SDA
messages for data or records that have been deleted from VistA, using data saved in ^XTMP
instead of the regular global.

Virtual Patient Record (VPR) 1.0
Developer’s Guide

129

July 2022

Inquire to Entity File Option

5.5.2
The Data Mapping [DDE ENTITY MAPPING] menu, on the VA FileMan Other Options
[DIOTHER] menu, contains options that support the creation and management of the ENTITY
(#1.5) file entries.

Use the Print an Entity [DDE ENTITY INQUIRE] option to display an Entity in a more
readable format than the regular VA FileMan Inquire to File Entries option [DIINQUIRE].
Basic information about the Entity displays first, followed by a list of the Entity’s Items.

Select the Summary format to see a simple list as shown in Figure 6, or Detailed to view all
properties of each item.

Figure 6: Print an Entity Option—Displaying Entities in a Readable Format

Select OPTION: OTHER OPTIONS
Select OTHER OPTION: DATA MAPPING
Select DATA MAPPING OPTION: ?
    Answer with DATA MAPPING OPTION NUMBER, or NAME
   Choose from:
   1            ENTER/EDIT AN ENTITY
   2            PRINT AN ENTITY
   3            GENERATE AN ENTITY FOR A FILE

Select DATA MAPPING OPTION: 2 <Enter> PRINT AN ENTITY
Select ENTITY: VPR ALLERGY
     1   VPR ALLERGY       SDA
     2   VPR ALLERGY ASSESSMENT       SDA
     3   VPR ALLERGY EXTENSION       SDA
     4   VPR ALLERGY OBSERVATION       SDA
     5   VPR ALLERGY SIGN EXTENSION       SDA
Press <Enter> to see more, '^' to exit this list,  OR
CHOOSE 1-5: 1 <Enter> VPR ALLERGY     SDA
Print item summary or details? Summary

DEVICE: HOME// 0;80;99  NETWORK

ENTITY: VPR ALLERGY (#52)
  FILE: PATIENT ALLERGIES (#120.8)          Jun 07, 2019@09:58:20   PAGE 1
--------------------------------------------------------------------------

DISPLAY NAME: Allergy

      SORT BY:                          DATA MODEL: SDA
    FILTER BY:                           READ ONLY: NO
       SCREEN:
QUERY ROUTINE: ALLERGYS^VPRSDAQ

 ENTRY ACTION: S VASITE=+$$SITE^VASITE S:VASITE'>0
VASITE=$$KSP^XUPARAM("INST")
    ID ACTION: D ALG1^VPRSDAL(DIEN)
  EXIT ACTION: K GMRAL,GMRAY,VPRALG,VASITE

Seq  Item                        Type Field  Sub/File   Entity

Virtual Patient Record (VPR) 1.0
Developer’s Guide

130

July 2022

--------------------------------------------------------------------------
2    Extension                     E         120.8      VPR ALLERGY
EXTENSION
3    Allergy                       E      1  120.8      VPR CODE TABLE
4    AllergyCategory               E    3.1  120.8      VPR CODE TABLE
5    Clinician                     E     21  120.8      VPR PROVIDER
6    Reaction                      E         120.8      VPR ALLERGY
SIGN/SYMPTOM
7    Severity                      E         120.85     VPR CODE TABLE
8    Certainty                     E     19  120.8      VPR CODE TABLE
12   InactiveTime                  S     23  120.8
13   InactiveComments              S         120.8
14   VerifiedTime                  S     20  120.8
17   FreeTextAllergy               S    .02  120.8
19   Status                        S     22  120.8
22   EnteredBy                     E      5  120.8      VPR USER
23   EnteredAt                     E         120.8      VPR FACILITY
24   EnteredOn                     S      4  120.8
25   FromTime                      S         120.85
26   ToTime                        S     23  120.8
27   ExternalId                    I

Select DATA MAPPING OPTION:

Virtual Patient Record (VPR) 1.0
Developer’s Guide

131

July 2022

5.6  Monitoring and Troubleshooting
The HealthShare Interface Manager [VPR HS MGR] menu shown in Figure 7 contains two
sub-menus that can be used for system monitoring and troubleshooting.

Figure 7: HealthShare Interface Manager [VPR HS MGR] Menu

Select OPTION NAME: VPR HS MGR <Enter> HealthShare Interface Manager

   HS     VPR HealthShare Utilities ...
   TEST   Test/Audit VPR Functions ...

Select HealthShare Interface Manager Option:

Table 60, describes the two HealthShare Interface Manager [VPR HS MGR] sub-menus that
contain options that can be used for technical support or testing:

Option Name

Option Text

Description

Table 60: VPR HS MGR Menu Options

VPR HS MENU

VPR HealthShare Utilities  This menu contains utilities for managing

the interface between the VistA Virtual
Patient Record (VPR) and the Regional
Health Connect (RHC) servers.

VPR HS TESTER  Test/Audit VPR Functions  This menu contains options to facilitate

the audit and testing of the VPR interface
with HealthShare.

Virtual Patient Record (VPR) 1.0
Developer’s Guide

132

July 2022

5.6.1  VPR HealthShare Utilities [VPR HS MENU] Menu
The VPR HealthShare Utilities [VPR HS MENU] menu shown in Figure 8 contains four options
used for managing the interface between VistA and the RHC servers:

Figure 8: VPR HealthShare Utilities [VPR HS MENU] Menu

Select HealthShare Interface Manager Option: HS <Enter> VPR HealthShare
Utilities

   ENC    Encounter Transmission Task Monitor
   AVPR   SDA Upload List Monitor
   UPD    Add Records to Upload List
   ON     Enable Data Monitoring

Select VPR HealthShare Utilities Option:

Table 61 and the sub-sections that follow describe the VPR HealthShare Utilities [VPR HS
MENU] menu options:

Table 61: VPR HealthShare Utilities Menu Options

Option Name

Option Text

Description

VPR HS TASK
MONITOR

Encounter Transmission Task
Monitor

VPR HS SDA
MONITOR

SDA Upload List Monitor

VPR HS PUSH

Add Records to Upload List

VPR HS ENABLE

Enable Data Monitoring

This option checks the status of the
task that collects encounters and
related records from PCE and TIU for
the AVPR upload list.

This option monitors the AVPR list of
upload requests for the RHC.

This option allows a site to manually
add patient record id(s) to the AVPR
upload list if needed.

This option enables or disables the
tracking of patient data for the AVPR
upload list.

Virtual Patient Record (VPR) 1.0
Developer’s Guide

133

July 2022

5.6.1.1  Encounter Transmission Task Monitor [VPR HS TASK MONITOR] Option

Updates to the ECR from the Patient Care Encounter (PCE) application are processed and added
to the upload list by a background task, to collect multiple edits into a single update per
encounter. Documents stored in the Text Integration Utilities (TIU) application also use this
process, as they are usually linked to a visit and may also save multiple edits during a single user
session.

  REF: For details on the event tasks, see Section 5.2.3.

HealthShare requires encounters to be uploaded first, before any data linked to that encounter
can be saved.

The Encounter Transmission Task Monitor [VPR HS TASK MONITOR] option checks the
health of this task, displaying the task number and its current status. Any waiting encounters or
documents can be viewed here. If the task has stopped for any reason and data is waiting, the
task can also be restarted with this option.

Virtual Patient Record (VPR) 1.0
Developer’s Guide

134

July 2022

Figure 9: Encounter Transmission Task Monitor [VPR HS TASK MONITOR] Option—System
Prompts and User Entries

Select VPR HealthShare Utilities Option: ENC <Enter> Encounter
Transmission Task Monitor

Current time: Feb 04, 2021@16:37:10

Data Monitoring System is ON.

Checking TaskMan ...

     VPR Encounter task is SCHEDULED.
     Task #8437572 is SCHEDULED for Feb 04, 2021@16:40:33

Checking the Transmission List ...

     There are encounters awaiting transmission.
     There are no documents awaiting transmission.

Enter monitor action: UPDATE// ?

     Enter <RETURN> to refresh the monitor display.
     Enter Q to exit the monitor.
     Enter T to display the task.
     Enter R to re-queue the transmission task.
     Enter E to display the Encounter list.
     Enter D to display the Document list.
     Enter ? to see this message.

Enter monitor action: UPDATE// E

     Last Updated   Visit#      DFN         Location Feb 04, 2021@16:37:21
--------------------------------------------------------------------------
 2/ 4/21@16:33:33    1851       9           GENERAL MEDICINE

Press <return> to continue ...<Enter>

Current time: Feb 04, 2021@16:37:26

Data Monitoring System is ON.

Checking TaskMan ...

     VPR Encounter task is SCHEDULED.
     Task #8437572 is SCHEDULED for Feb 04, 2021@16:40:33

Checking the Transmission List ...

     There are encounters awaiting transmission.
     There are no documents awaiting transmission.

Enter monitor action: UPDATE// Q

Virtual Patient Record (VPR) 1.0
Developer’s Guide

135

July 2022

5.6.1.2  SDA Upload List Monitor [VPR HS SDA MONITOR] Option

The SDA Upload List Monitor [VPR HS SDA MONITOR] option is a simple monitor of the
AVPR index, which the RHC server polls every few seconds for data extracts, optionally filtered
by patient and container. If no patient or container is selected, all current entries in the list are
displayed. The RHC server removes entries from this index when the data has been uploaded, so
this list should turn over every few seconds if the system is running correctly.

The last sequence number used in this list is also displayed at the bottom.

Figure 10: SDA Upload List Monitor [VPR HS SDA MONITOR] Option—System Prompts and User
Entries

Select VPR HealthShare Utilities Option: SDA Upload List Monitor
Select PATIENT NAME: <Enter>
Select CONTAINER: <Enter>

VPR Global Upload Monitor                         Apr 16, 2021@15:08:30
SEQ       DFN       All containers for all patients
--------------------------------------------------------------------------
4838      8         5000000049V161696^Medication^16417;100^U^
4839      153       5000000100V704929^Medication^16419;100^U^
4840      153       5000000100V704929^Medication^16420;100^U^
4841      9         5000000098V757329^Observation^525;120.5^U^
4842      9         5000000098V757329^Observation^526;120.5^U^
4843      741       5000000026V032296^Medication^16547;100^U^
4844      741       5000000026V032296^Medication^16546;100^U^
4845      9         5000000098V757329^LabOrder^16578;100^U^
4846      9         5000000098V757329^LabOrder^16577;100^U^
4847      9         5000000098V757329^Medication^16550;100^U^
4848      181       5000000068V971252^Medication^15534;100^U^
4849      300       5000000128V793395^Medication^15556;100^U^
4850      129       5000000129V929287^Medication^15549;100^U^
4851      129       5000000129V929287^Medication^15551;100^U^
4852      300       5000000128V793395^Medication^15553;100^U^
4853      134       5000000046V523900^Medication^15555;100^U^
4854      756       1012856479V033267^Alert^7;26.13^U^
4855      128       5000000126V406128^Medication^16579;100^U^
4856      300       5000000128V793395^Medication^15578;100^U^

Press <return> to continue or ^ to exit ... <Enter>

VPR Global Upload Monitor                         Apr 16, 2021@15:09:06
SEQ       DFN       All containers for all patients
--------------------------------------------------------------------------
4857      9         5000000098V757329^Medication^16892;100^U^
4858      179       5000000115V760984^Medication^16374;100^U^
4859      755       1012856477V526483^Allergy^947;120.8^U^
4860      9         5000000098V757329^Medication^16413;100^U^

Current Sequence#: 4860
Do you wish to continue to monitor the upload global? YES// NO

Virtual Patient Record (VPR) 1.0
Developer’s Guide

136

July 2022

5.6.1.3  Add Records to Upload List [VPR HS PUSH] Option

The Add Records to Upload List [VPR HS PUSH] option allows patient record id(s) to be
manually added to the AVPR upload list, if it is suspected that the data cache has gotten out of
synch or a record extract has errored.

Figure 11: Add Records to Upload List [VPR HS PUSH] Option—System Prompts and User Entries

Select VPR HealthShare Utilities Option: UPD <Enter> Add Records to Upload
List

Select PATIENT NAME: VPRPATIENT,ONE <Enter>       12-1-46    666000004
YES     NSC VETERAN         *MULTIPLE BIRTH*      SMB     SMB
Select CONTAINER: PROB <Enter> Problem
Update the full container? NO// ?

Enter YES to send all available records in this container to the ECR, or
NO to exit.

Update the full container? NO// <Enter>

This container has multiple sources; please select one.
Select SOURCE FILE: ?

Select a VistA source file for this container, or press return for all.

     Select one of the following:

          9000011   PROBLEM
          783       FUNCTIONAL INDEPENDENCE MEASUREMENT RECORD

Select SOURCE FILE: PROBLEM

Available Problems for VPRPATIENT,ONE:
1    JUL 29, 2019  Hearing loss (SCT 15188001)
Select ITEM(S): 1
Problem #1 added to update queue.

Select CONTAINER:

Virtual Patient Record (VPR) 1.0
Developer’s Guide

137

July 2022

5.6.1.4  Enable Data Monitoring [VPR HS ENABLE] Option

The Enable Data Monitoring [VPR HS ENABLE] option enables or disables the tracking of
patient data changes in the AVPR upload list, for retrieval by the RHC server. Turning off data
monitoring effectively disables the VistA – HealthShare interface entirely, so this option is for
emergency use only and is locked with the VPR HS ENABLE security key. A timestamp is
captured when the system is turned on or off, for use in data recovery.

  CAUTION: In a Production system, only use this option at the direction of Health

Product Support (HPS) or VPR development staff!

Figure 12: Enable Data Monitoring [VPR HS ENABLE] Option—System Prompts and User Entries

Select VPR HealthShare Utilities Option: ON <Enter> Enable Data Monitoring

WARNING: Turning off data monitoring will cause the Regional Health
Connect
         server to become out of synch with VistA!!

    ***  Do NOT proceed unless directed to do so by Health Product Support
         or VPR development staff!

ARE YOU SURE? NO// YES

ENABLE MONITORING: YES// <Enter>

5.6.2  Test/Audit VPR Functions [VPR HS TESTER] Menu
The Test/Audit VPR Functions [VPR HS TESTER] menu shown in Figure 13 contains five
options for testing and monitoring the VPR data monitoring functions:

Figure 13: Test/Audit VPR Functions [VPR HS TESTER] Menu

Select HealthShare Interface Manager Option: TEST <Enter> Test/Audit VPR
Functions

   SDA    Test SDA Extracts
   AVPR   SDA Upload List Monitor
   LOG    Data Upload List Log
   ENC    Encounter Transmission Task Monitor
   PAT    Inquire to Patient Subscriptions

Select Test/Audit VPR Functions Option:

Virtual Patient Record (VPR) 1.0
Developer’s Guide

138

July 2022

Table 62 and the sub-sections that follow describe the Test/Audit VPR Functions [VPR HS
TESTER] menu options:

Table 62: Test/Audit VPR Functions [VPR HS TESTER] Menu Options

Option Name

Option Text

Description

VPR HS TEST

Test SDA Extracts

VPR HS SDA
MONITOR

SDA Upload List Monitor

VPR HS LOG

Data Upload List Log

VPR HS TASK
MONITOR

Encounter Transmission Task
Monitor

VPR HS PATIENTS

Inquire to Patient
Subscriptions

This option runs the SDA data
extracts for a selected patient and
container to view onscreen.

This option monitors the AVPR list of
upload requests for the RHC.

This option enables saving and
viewing of the upload list in ^XTMP
for testing or debugging purposes,
for up to 3 days.

This option checks the status of the
task that collects encounters and
related records from PCE and TIU for
the AVPR upload list.

This option displays information
about a patient’s subscription status
for data monitoring.

Virtual Patient Record (VPR) 1.0
Developer’s Guide

139

July 2022

5.6.2.1  Test SDA Extracts [VPR HS TEST] Option

The Test SDA Extracts [VPR HS TEST] option runs the SDA data extracts for a selected
patient and container, to view the records in SDA format as they were sent to the HealthShare.
No data is actually sent to the ECR using this option, the results are only displayed on screen for
testing and debugging purposes.

Figure 14: Test SDA Extracts [VPR HS TEST] Option—System Prompts and User Entries

Select Test/Audit VPR Functions Option: SDA <Enter> Test SDA Extracts
Select PATIENT NAME: VPRPATIENT,ONE <Enter>      12-1-46    666000004
YES NSC VETERAN         *MULTIPLE BIRTH*      SMB     SMB
Select CONTAINER: PROBLEM
Select SOURCE FILE: <Enter>
Select START DATE: <Enter>
Select TOTAL #items: <Enter>
DEVICE: HOME// <Enter> Linux Telnet /SSh

#Results: 1

Press <return> to continue or ^ to exit results ... <Enter>

Result #1

<Problem>
  <UpdatedOn>2019-07-29T00:00:00</UpdatedOn>
  <Extension>
    <IsExposureAO>false</IsExposureAO>
    <IsExposureIR>false</IsExposureIR>
    <IsExposurePG>false</IsExposurePG>
    <IsExposureCV>true</IsExposureCV>
    <Location>
      <SDACodingStandard>VA44</SDACodingStandard>
      <Extension>
        <StopCode>
          <SDACodingStandard>AMIS</SDACodingStandard>
          <Code>203</Code>
          <Description>AUDIOLOGY</Description>
        </StopCode>
        <Service>MEDICINE</Service>
        <Specialty>
          <SDACodingStandard>VA45.7</SDACodingStandard>
          <Code>11</Code>
          <Description>INTERMEDIATE MED</Description>

Press <return> to continue or ^ to exit item ... ^

Select CONTAINER: <Enter>
Select PATIENT NAME:

Virtual Patient Record (VPR) 1.0
Developer’s Guide

140

July 2022

5.6.2.2  SDA Upload List Monitor [VPR HS SDA MONITOR] Option

The SDA Upload List Monitor [VPR HS SDA MONITOR] option is duplicated on the VPR
HS TESTER menu for the convenience of users testing VPR patches.

  REF: For a description of this option, see Section 5.6.1.2.

5.6.2.3  Data Upload List Log [VPR HS LOG] Option

The Data Upload List Log [VPR HS LOG] option enables VPR to save a copy of the AVPR
upload list entries in ^XTMP(“VPRHS”) temporarily, for testing or debugging purposes.
Entries are stored by date of activity, so a nightly Kernel job can remove data from the log after 3
days.

The log can also be viewed in this option, by date of activity, and optionally by patient.

Virtual Patient Record (VPR) 1.0
Developer’s Guide

141

July 2022

Figure 15: Data Upload List Log [VPR HS LOG] Option—System Prompts and User Entries

Select Test/Audit VPR Functions Option: LOG <Enter> Data Upload List Log

Upload list logging is currently OFF

Would you like to turn it ON? NO// Y <Enter> YES

   SDA    Test SDA Extracts
   AVPR   SDA Upload List Monitor
   LOG    Data Upload List Log
   ENC    Encounter Transmission Task Monitor
   PAT    Inquire to Patient Subscriptions

Select Test/Audit VPR Functions Option: LOG <Enter> Data Upload List Log

Upload list logging is currently ON

Select log action: VIEW// <Enter>
Select a date: Apr 16, 2021// ?

Available date is Apr 16, 2021, or enter ^ to exit.

Select a date: Apr 16, 2021// <Enter> (APR 16, 2021)
Starting sequence#: FIRST// <Enter>
Select PATIENT NAME: <Enter>

SEQ       DFN       Apr 16, 2021
--------------------------------------------------------------------------
5342      4         5000000103V528688^Problem^187;9000011^U^

Press <return> to continue ... <Enter>

Select a date: Apr 16, 2021// ^

Select log action: VIEW// QUIT

5.6.2.4  Encounter Transmission Task Monitor [VPR HS TASK MONITOR] Option

The Encounter Transmission Task Monitor [VPR HS TASK MONITOR] option is duplicated
on the VPR HS TESTER menu for the convenience of users testing VPR patches. However, the
action of re-queuing the task, if it has stopped, is not available when the option is accessed via
the VPR HS TESTER menu.

  REF: For a description of this option, see Section 5.6.1.1.

Virtual Patient Record (VPR) 1.0
Developer’s Guide

142

July 2022

5.6.2.5  Inquire to Patient Subscriptions [VPR HS PATIENTS] Option

The Inquire to Patient Subscriptions [VPR HS PATIENTS] option displays information about
a selected patient’s subscription status for HealthShare data monitoring.

Figure 16: Inquire to Patient Subscriptions [VPR HS PATIENTS] Option—System Prompts and
User Entries

Select Test/Audit VPR Functions Option: PAT <Enter> Inquire to Patient
Subscriptions

Select PATIENT NAME: VPRPATIENT,TWO MEANS RD <Enter>       3-3-30
666000003 NO  SC VETERAN                   ORANGE TEAM

VPRPATIENT,TWO MEANS RD is subscribed in HealthShare
DFN: 3
ICN: 5000000101V983844
>> Patient DIED on May 29, 2021@08:00

Select PATIENT NAME: VPRPATIENT,THREE <Enter>     0-0-01    102000001P
**Pseudo SSN
**     YES     SC VETERAN         *MULTIPLE BIRTH*      SMB     SMB

VPRPATIENT,THREE is subscribed in HealthShare
DFN: 9
ICN: 5000000098V757329

Select PATIENT NAME: NEWVPRPATIENT,RELEASE <Enter>       12-30-45
666000015     NO     COLLATERAL

                 *** Patient Requires a Means Test ***

                         *** Please update ***

Enter <RETURN> to continue. <Enter>

MEANS TEST REQUIRED
   PATIENT REQUIRES A MEANS TEST

NEWVPRPATIENT,RELEASE is NOT subscribed in HealthShare
DFN: 15
ICN: NO MPI NODE

Select PATIENT NAME:

Virtual Patient Record (VPR) 1.0
Developer’s Guide

143

July 2022

5.7  Call To Populate
The Call To Populate (CTP) is a utility created by the VPR team that can re-pull VistA patient
records that already exist on the RHC server. It is used to update data records after national
release of a VPR patch, which added extension properties or corrected a data extract problem.

  REF: This document describes the VistA CTP Utility, for more information on the

Veterans Data Integration and Federation Enterprise Platform (VDIF-EP) CTP Utility,
see the VDIF-EP Utilities User Guide (vdif_ug_utilities.pdf); located in the VDIF-EP
GitHub repository.

5.7.1  VPRZCTP

Description

The VPRZCTP routine exists on each RHC server to support the CTP utility. It is in the VPRZ
namespace as it is only for use by the RHC and is not exported to any VistA site. Routine
mappings tell the RHC to look for VPRZ routines on its system rather than in VistA. Because
the job started on the RHC, the results will accumulate in a global there instead of filling up a
^TMP or ^XTMP global in VistA.

VPRZCTP itself does not actually extract any data. It uses the VPR CONTAINER (#560.1) file
and existing Entity file definitions to search for affected records, but it only executes the Query
Routine. The resulting record identifiers are formatted like the strings used by the AVPR index
and returned to the RHC for processing with the real-time updates.

Format

EN^VPRZCTP(start,stop,max,routine,type,id,format,number,dfn,result)

Input Parameters

All input parameters are optional; however, if the type input parameter is not defined then no
data can be returned.

start:

stop:

max:

routine:

type:

Date to start searching for records (default is all records).

Date to stop searching for records (default is all records).

Maximum number of items to return per container (default is 9999).

Name of a VPRZ routine to execute for a specialized search.

Name of the desired SDA Container(s) and optional source file number,
separated by commas, each in the format:

Container name_[“;”_VistA source file number]

id:

Record identifier, in the format:

internal entry number_“;”_VistA source file number

Virtual Patient Record (VPR) 1.0
Developer’s Guide

144

July 2022

format:

String indicating the type of results to return, as:

•  “OPS”―Individual record identifier strings (default).

•  “CNT”―A count of the records found by container.

number:

Base number from which to start incrementing the sequence numbers in
the results array (default is 0).

dfn:

Pointer to the PATIENT (#2) file, or list of pointers as:

“~”_pointer_”~”_pointer_..._”~”_pointer

result:

Closed array name for returning results, default is:

^PL.CTP(#)

Global that accumulates on the RHC.

Output

This routine returns a list of record identifiers in the specified array, as well as indexes by patient
and container. The total number of records returned can be found in the “Tot” node of the array.

Result(#):

Record identifier string, formatted for use with AVPR index utility and
indexed by:

Result(“DFN”, dfn, #)
Result(“DOMAIN”, dfn, type, #)

Result(“Tot”):

Nodes containing counts of the records found by the query, in the form:

Result(“Tot”)

total ^ updates ^ deletes ^ last subscript ^
error message, if any
# of records to be updated
# of records to be deleted
# of records in the container

Result(“Tot”, “U”)
Result(“Tot”, “D”)
Result(“Tot”, type)
Result(“Tot”, type, file#)  # of records in the container and source

file

Virtual Patient Record (VPR) 1.0
Developer’s Guide

145

July 2022

5.7.1.1  Examples

The following are some examples of running the VPRZCTP routine utilities to demonstrate how
the RHC server calls it and the results returned:

  NOTE: This routine exists only on the RHC servers and not in any VistA site.

•  Error! Reference source not found.

•  CTP by Domain: CNT

•  CTP by Patient

•  CTP by ID

•  CTP by Patch

5.7.1.1.1  CTP by Domain

Running the CTP by Domain utility only truly requires the container name; however, due to the
volume of data in VistA other filters, such as a date range, are strongly recommended.

  NOTE: Dates do not need to be passed in VA FileMan format. All input dates are

validated using the VA FileMan %DT utility, so any format that passes this check is
acceptable.

Any domain that relies on visits will also return any related Encounter records.

Virtual Patient Record (VPR) 1.0
Developer’s Guide

146

July 2022

Figure 17: CTP by Domain Utility―Sample Results

>D EN^VPRZCTP(20210701,20211231,,,"Document",,,,,"RESULT") ZW RESULT
RESULT(1)="5000000103V528688^Document^1709;8925^U^1862^4"
RESULT(2)="5000000103V528688^Encounter^1862;9000010^U^^4"
RESULT(3)="5000000098V757329^Document^1716;8925^U^1860^9"
RESULT(4)="5000000098V757329^Document^1706;8925^U^1860^9"
RESULT(5)="5000000098V757329^Encounter^1860;9000010^U^^9"
RESULT(6)="5000000129V929287^Document^1726;8925^U^^129"
RESULT(7)="5000000148V605820^Document^1707;8925^U^1861^229"
RESULT(8)="5000000148V605820^Encounter^1861;9000010^U^^229"
RESULT("DFN",4,1)=""
RESULT("DFN",4,2)=""
RESULT("DFN",9,3)=""
RESULT("DFN",9,4)=""
RESULT("DFN",9,5)=""
RESULT("DFN",129,6)=""
RESULT("DFN",229,7)=""
RESULT("DFN",229,8)=""
RESULT("DOMAIN",4,"Document",1)=""
RESULT("DOMAIN",4,"Encounter",2)=""
RESULT("DOMAIN",9,"Document",3)=""
RESULT("DOMAIN",9,"Document",4)=""
RESULT("DOMAIN",9,"Encounter",5)=""
RESULT("DOMAIN",129,"Document",6)=""
RESULT("DOMAIN",229,"Document",7)=""
RESULT("DOMAIN",229,"Encounter",8)=""
RESULT("Tot")="8^8^0^8^"
RESULT("Tot","D")=0
RESULT("Tot","Document")=5
RESULT("Tot","Document",8925)=5
RESULT("Tot","Encounter")=3
RESULT("Tot","Encounter",9000010)=3
RESULT("Tot","U")=8

>

Virtual Patient Record (VPR) 1.0
Developer’s Guide

147

July 2022

5.7.1.1.2  CTP by Domain: CNT

The “CNT” format of the CTP by Domain utility performs the same query as the regular CTP
by Domain utility, but it only returns the index and total nodes to the RHC server. The “CNT”
parameter simply tells CTP to only count the number of entries it finds that fit the criteria; it
does not actually return all of the record ids or do the update. This is sometimes used first to get
an estimate of how long it takes the actual CTP by Domain to complete at a given site.

Figure 18: CTP by Domain: CNT Utility―Sample Results

>D EN^VPRZCTP(20210701,20211231,,,"Document",,"CNT",,,"RESULT") ZW RESULT
RESULT("DFN",4,1)=""
RESULT("DFN",4,2)=""
RESULT("DFN",9,3)=""
RESULT("DFN",9,4)=""
RESULT("DFN",9,5)=""
RESULT("DFN",129,6)=""
RESULT("DFN",229,7)=""
RESULT("DFN",229,8)=""
RESULT("DOMAIN",4,"Document",1)=""
RESULT("DOMAIN",4,"Encounter",2)=""
RESULT("DOMAIN",9,"Document",3)=""
RESULT("DOMAIN",9,"Document",4)=""
RESULT("DOMAIN",9,"Encounter",5)=""
RESULT("DOMAIN",129,"Document",6)=""
RESULT("DOMAIN",229,"Document",7)=""
RESULT("DOMAIN",229,"Encounter",8)=""
RESULT("Tot")="8^8^0^8^"
RESULT("Tot","D")=0
RESULT("Tot","Document")=5
RESULT("Tot","Document",8925)=5
RESULT("Tot","Encounter")=3
RESULT("Tot","Encounter",9000010)=3
RESULT("Tot","U")=8

>

Virtual Patient Record (VPR) 1.0
Developer’s Guide

148

July 2022

5.7.1.1.3  CTP by Patient

The CTP by Patient utility can be run for a single patient by passing the local PATIENT (#2)
pointer in the dfn parameter. A finite list of patient dfn’s can also be requested by passing in a
string whose first character is the delimiter separating each dfn. For example: “~129~231~744”.

Figure 19: CTP by Patient Utility―Sample Results

>D EN^VPRZCTP(20210701,20211231,,,"Document,Problem",,,,9,"RESULT") ZW
RESULT
RESULT(1)="5000000098V757329^Document^1716;8925^U^1860^9"
RESULT(2)="5000000098V757329^Document^1706;8925^U^1860^9"
RESULT(3)="5000000098V757329^Problem^195;9000011^U^^9"
RESULT(4)="5000000098V757329^Problem^155;9000011^U^^9"
RESULT(5)="5000000098V757329^Encounter^1860;9000010^U^^9"
RESULT("DFN",9,1)=""
RESULT("DFN",9,2)=""
RESULT("DFN",9,3)=""
RESULT("DFN",9,4)=""
RESULT("DFN",9,5)=""
RESULT("DOMAIN",9,"Document",1)=""
RESULT("DOMAIN",9,"Document",2)=""
RESULT("DOMAIN",9,"Encounter",5)=""
RESULT("DOMAIN",9,"Problem",3)=""
RESULT("DOMAIN",9,"Problem",4)=""
RESULT("Tot")="5^5^0^5^"
RESULT("Tot","D")=0
RESULT("Tot","Document")=2
RESULT("Tot","Document",8925)=2
RESULT("Tot","Encounter")=1
RESULT("Tot","Encounter",9000010)=1
RESULT("Tot","Problem")=2
RESULT("Tot","Problem",9000011)=2
RESULT("Tot","U")=5

>

Virtual Patient Record (VPR) 1.0
Developer’s Guide

149

July 2022

5.7.1.1.4  CTP by ID

Use the CTP by ID utility to pass in a single record id. It is often used after an error has
occurred. If the id parameter is passed, then the type and dfn parameters are also required.

Figure 20: CTP by ID Utility―Sample Results

>D EN^VPRZCTP(20210701,20211231,,,"Problem","195;9000011",,,9,"RESULT")

>ZW RESULT
RESULT(1)="5000000098V757329^Problem^195;9000011^U^^9"
RESULT("DFN",9,1)=""
RESULT("DOMAIN",9,"Problem",1)=""
RESULT("Tot")="1^1^0^1^"
RESULT("Tot","D")=0
RESULT("Tot","Problem")=1
RESULT("Tot","Problem",9000011)=1
RESULT("Tot","U")=1

>

5.7.1.1.5  CTP by Patch

Some containers, such as Documents, are very intensive to re-load; so, a special lookup routine
can be written to target only those records directly affected by a patch. The CTP by Patch utility
allows you to pass the CTP patch routine name into VPRZCTP. It should follow these
constraints:

•  Be named VPRZP##; where ## is the number of the corresponding VistA VPR patch; it

will be loaded only on the RHC servers.

•  Have a “CTP” line tag, that will be called from inside VPRZCTP.

•  Support the search parameters for date range and patient that are available in the

variables: VPRBDT, VPREDT, and VPRPT respectively.

•  Support the type parameter, if multiple searches are performed; type is available in the
VPRTYPE variable and can be whatever domain identifier needed by the routine, such
as a container name or a line tag to execute.

•  Can call the POST^VPRZCTP API for each record identified, to return the same results

array.

Virtual Patient Record (VPR) 1.0
Developer’s Guide

150

July 2022

Figure 21 is an example of the CTP routine from patch VPR*1*20, to find documents in the TIU
DOCUMENT (#8925) file affected by the patch.

Figure 21: Sample CTP Routine―Finding Documents in the TIU DOCUMENT (#8925) File affected
by the Patch

>D EN^VPRZCTP(20210701,20211231,,"VPRZP20","TIU",,,,,"RESULT") ZW RESULT
RESULT(1)="5000000098V757329^Document^1706;8925^U^1860^9^1706;TIU"
RESULT(2)="5000000098V757329^Document^1716;8925^U^1860^9^1716;TIU"
RESULT(3)="5000000098V757329^Encounter^1860;9000010^U^^9^1860"
RESULT(4)="5000000129V929287^Document^1726;8925^U^^129^1726;TIU"
RESULT(5)="5000000148V605820^Document^1707;8925^U^1861^229^1707;TIU"
RESULT(6)="5000000148V605820^Encounter^1861;9000010^U^^229^1861"
RESULT("DFN",9,1)=""
RESULT("DFN",9,2)=""
RESULT("DFN",9,3)=""
RESULT("DFN",129,4)=""
RESULT("DFN",229,5)=""
RESULT("DFN",229,6)=""
RESULT("DOMAIN",9,"Document",1)=""
RESULT("DOMAIN",9,"Document",2)=""
RESULT("DOMAIN",9,"Encounter",3)=""
RESULT("DOMAIN",129,"Document",4)=""
RESULT("DOMAIN",229,"Document",5)=""
RESULT("DOMAIN",229,"Encounter",6)=""
RESULT("Tot")="6^6^0^6^"
RESULT("Tot","D")=0
RESULT("Tot","TIU")=6
RESULT("Tot","U")=6

>

Virtual Patient Record (VPR) 1.0
Developer’s Guide

151

July 2022
