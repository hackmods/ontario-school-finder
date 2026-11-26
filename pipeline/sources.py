"""Source registry.

Every number the site shows carries a ``source_id`` that points at one resource below.
Each resource records its URL, licence and school year; the retrieval date is added at
download time (see ``fetch.py``). If a URL or a file's columns change, the loaders fail
with a clear "expected vs found" message instead of guessing.
"""
from __future__ import annotations

OGL_ON = ("Open Government Licence – Ontario", "https://www.ontario.ca/page/open-government-licence-ontario")
STATCAN = ("Statistics Canada Open Licence", "https://www.statcan.gc.ca/en/reference/licence")

DATA_ON = "https://data.ontario.ca/dataset/"

# ---------------------------------------------------------------------------
# Source datasets (the numbers in the brief's table are kept as `brief_no`).
# ---------------------------------------------------------------------------
DATASETS: dict[str, dict] = {
    "sif": {
        "brief_no": 1,
        "title": "School information and student demographics",
        "publisher": "Ontario Ministry of Education",
        "landing": DATA_ON + "school-information-and-student-demographics",
        "ckan_id": "school-information-and-student-demographics",
        "licence": OGL_ON,
        "used_for": "School list, board, address, grades, coordinates, EQAO results (Grade 3, 6, 9, OSSLT) for every year published, student-population context.",
        "status": "used",
    },
    "contact": {
        "brief_no": 2,
        "title": "Ontario public school contact information",
        "publisher": "Ontario Ministry of Education",
        "landing": DATA_ON + "ontario-public-school-contact-information",
        "ckan_id": "ontario-public-school-contact-information",
        "licence": OGL_ON,
        "used_for": "Current phone, email, website and open status; date each school opened.",
        "status": "used",
    },
    "eqao_repo": {
        "brief_no": 3,
        "title": "EQAO Open Agency Data Repository",
        "publisher": "Education Quality and Accountability Office (EQAO)",
        "landing": "https://www.eqao.com/",
        "licence": ("EQAO terms (to be checked before republishing)", "https://www.eqao.com/terms-of-use/"),
        "used_for": "Not used yet (Phase 2). Every school page links to the school's EQAO results page instead.",
        "status": "phase2",
    },
    "sbpr": {
        "brief_no": 4,
        "title": "School board achievements and progress",
        "publisher": "Ontario Ministry of Education",
        "landing": DATA_ON + "school-board-achievements-and-progress",
        "ckan_id": "school-board-achievements-and-progress",
        "licence": OGL_ON,
        "used_for": "Official board-level Grade 6 reading, Grade 10 OSSLT, credit accumulation and graduation rates.",
        "status": "used",
    },
    "enrol": {
        "brief_no": 5,
        "title": "Ontario public schools enrolment",
        "publisher": "Ontario Ministry of Education",
        "landing": DATA_ON + "ontario-public-schools-enrolment",
        "ckan_id": "ontario-public-schools-enrolment",
        "licence": OGL_ON,
        "used_for": "Enrolment trend for every school, 2011-12 to 2024-25.",
        "status": "used",
    },
    "board_area": {
        "brief_no": 6,
        "title": "Board service area",
        "publisher": "Ontario Ministry of Education",
        "landing": DATA_ON + "board-service-area",
        "ckan_id": "board-service-area",
        "licence": ("Licence not specified (dataset under review)", DATA_ON + "board-service-area"),
        "used_for": "Skipped: the dataset is listed as \"under review\" with no files to download. Approximate board areas are drawn from school locations instead.",
        "status": "skipped",
    },
    "fsa_boundary": {
        "brief_no": 7,
        "title": "2021 Census Forward Sortation Area boundary file (cartographic)",
        "publisher": "Statistics Canada",
        "landing": "https://www12.statcan.gc.ca/census-recensement/2021/geo/sip-pis/boundary-limites/index2021-eng.cfm?year=21",
        "licence": STATCAN,
        "used_for": "Postal-area (FSA) outlines, the Ontario outline, and the FSA check for every school.",
        "status": "used",
    },
    "csd_boundary": {
        "brief_no": 8,
        "title": "2021 Census subdivision boundary file",
        "publisher": "Statistics Canada",
        "landing": "https://www12.statcan.gc.ca/census-recensement/2021/geo/sip-pis/boundary-limites/index2021-eng.cfm?year=21",
        "licence": STATCAN,
        "used_for": "Not needed: it was only for joining the board service areas (#6), which are unavailable.",
        "status": "skipped",
    },
    "census": {
        "brief_no": 9,
        "title": "Census Profile, 2021 Census of Population — forward sortation areas",
        "publisher": "Statistics Canada",
        "landing": "https://www12.statcan.gc.ca/census-recensement/2021/dp-pd/prof/index.cfm?Lang=E",
        "licence": STATCAN,
        "used_for": "Area context on postal-area pages: population, children 0–14, families with children, household income, children in low income, languages.",
        "status": "used",
    },
    "childcare": {
        "brief_no": 10,
        "title": "Licensed child care facilities in Ontario",
        "publisher": "Ontario Ministry of Education",
        "landing": DATA_ON + "licensed-child-care-facilities-in-ontario",
        "ckan_id": "licensed-child-care-facilities-in-ontario",
        "licence": OGL_ON,
        "used_for": "Licensed child care at each school's address and in each postal area.",
        "status": "used",
    },
    "enrol_grade": {
        "brief_no": 12,
        "title": "School enrolment by grade",
        "publisher": "Ontario Ministry of Education",
        "landing": DATA_ON + "school-enrolment-by-grade",
        "ckan_id": "school-enrolment-by-grade",
        "licence": OGL_ON,
        "used_for": "Added for parents: how many students are in each grade at each school, 2017-18 to 2024-25.",
        "status": "used",
    },
    "class_size": {
        "brief_no": 13,
        "title": "Elementary class size",
        "publisher": "Ontario Ministry of Education",
        "landing": DATA_ON + "elementary-class-size",
        "ckan_id": "elementary-class-size",
        "licence": OGL_ON,
        "used_for": "Added for parents: class sizes at each elementary school, 2007-08 to 2025-26 (primary classes every year; all classes from 2014-15).",
        "status": "used",
    },
    "fsl": {
        "brief_no": 14,
        "title": "Public schools offering French as a Second Language (FSL) programs",
        "publisher": "Ontario Ministry of Education",
        "landing": DATA_ON + "public-schools-offering-french-as-a-second-language-fsl-programs",
        "ckan_id": "public-schools-offering-french-as-a-second-language-fsl-programs",
        "licence": OGL_ON,
        "used_for": "Added for parents: which English-language schools offer Core French, Extended French and French Immersion (2024-25, preliminary).",
        "status": "used",
    },
    "shsm": {
        "brief_no": 15,
        "title": "Specialist High Skills Major (SHSM) program list",
        "publisher": "Ontario Ministry of Education",
        "landing": DATA_ON + "specialist-high-skills-major-shsm-program-list",
        "ckan_id": "specialist-high-skills-major-shsm-program-list",
        "licence": OGL_ON,
        "used_for": "Added for parents: which high schools offer which Specialist High Skills Major sectors, and for how many years (2025-26).",
        "status": "used",
    },
    "attendance": {
        "brief_no": 11,
        "title": "Board-published attendance boundaries",
        "publisher": "Individual school boards",
        "landing": "",
        "licence": ("Per board; written permission recorded before use", ""),
        "used_for": "Not used yet. Checked November 2026: no Ontario board publishes its attendance boundaries under an open licence. Several boards (Waterloo Region DSB, Hamilton-Wentworth DSB, Simcoe County DSB, Grand Erie DSB, Dufferin-Peel CDSB, Kawartha Pine Ridge DSB, Halton CDSB) post map layers without a licence, so they need the board's written permission first. Every school page links to its board's own school locator instead.",
        "status": "phase2",
    },
}

SIF_URL = "https://data.ontario.ca/dataset/d85f68c5-fcb0-4b4d-aec5-3047db47dcd5/resource/{}/download/{}"
ENR_URL = "https://data.ontario.ca/dataset/d89271cf-c5b7-4537-9d8b-5905766d93c6/resource/{}/download/{}"

# Columns that changed name in 2021-22 when Grade 9 math was de-streamed.
G9_STREAMED = "streamed"
G9_DESTREAMED = "destreamed"

# year = school year of the file; eqao_year = school year of the EQAO results inside it
# (None when the file only repeats an earlier year's results — EQAO did not run during
# the pandemic in 2019-20 and 2020-21).
SIF_RESOURCES = [
    dict(id="sif-2024-25", year="2024-25", eqao_year="2024-25", g9=G9_DESTREAMED, note="Ministry label: \"Preliminary 2024-2025\" (OnSIS preliminary as of July 17, 2026)",
         url=SIF_URL.format("f75540ed-59eb-49ab-ac43-976d563b3a65", "new_sif_data_2024_25_final_en_oct_2026.xlsx")),
    dict(id="sif-2023-24", year="2023-24", eqao_year="2023-24", g9=G9_DESTREAMED, context_numeric="fraction", note="Ministry label: \"Preliminary 2023-2024\"; percentages stored as 0-1 numbers",
         url=SIF_URL.format("f381e1de-3aa8-4ae9-826a-20009a6f4a01", "new_sif_data_table_2023_24prelim_en_january2026.xlsx")),
    dict(id="sif-2022-23", year="2022-23", context_numeric="whole", eqao_year="2022-23", g9=G9_DESTREAMED, note="",
         url=SIF_URL.format("f95fc955-b1f0-4a2e-9b7f-cfa6eda37e0b", "sif_data_table_2022_2023_en.xlsx")),
    dict(id="sif-2021-22", year="2021-22", context_numeric="whole", eqao_year="2021-22", g9=G9_DESTREAMED, note="",
         url=SIF_URL.format("e0e90bd5-d662-401a-a6d2-60d69ac89d14", "sif_data_table_2021_2022_en.xlsx")),
    dict(id="sif-2020-21", year="2020-21", context_numeric="whole", eqao_year=None, g9=G9_STREAMED, note="Sheet repeats 2018-19 EQAO results (no EQAO assessments during the pandemic)",
         url=SIF_URL.format("600ab128-f50f-43a4-b4d4-97c39bb270b6", "sif_data_table_2020_2021_en.xlsx"), sheet_must_contain="EQAO1819"),
    dict(id="sif-2019-20", year="2019-20", context_numeric="whole", eqao_year=None, g9=G9_STREAMED, note="Sheet repeats 2018-19 EQAO results (no EQAO assessments during the pandemic)",
         url=SIF_URL.format("602a5186-67f5-4faf-94f3-7c61ffc4719a", "sif_data_table_2019_2020_en.xlsx"), sheet_must_contain="EQAO1819"),
    dict(id="sif-2018-19", year="2018-19", context_numeric="whole", eqao_year="2018-19", g9=G9_STREAMED, note="",
         url=SIF_URL.format("bbbac037-b1c9-4b32-8f67-4fed1dfcac06", "sif_data_table_2018_2019_en.xlsx"), sheet_must_contain="EQAO1819"),
    dict(id="sif-2017-18", year="2017-18", context_numeric="whole", eqao_year="2017-18", g9=G9_STREAMED, note="",
         url=SIF_URL.format("3d8e7824-d033-4ca5-a5de-aa0dbec99002", "sif_data_table_2017_2018_en.xlsx"), sheet_must_contain="EQAO1718"),
    # Older file, no longer listed on the dataset page but still published on files.ontario.ca.
    # Its student-context columns differ (and use decimals), so only school details + EQAO are read.
    dict(id="sif-2015-16", year="2015-16", eqao_year="2016-17", g9=G9_STREAMED, eqao_only=True, sheet_must_contain="EQAO1617",
         note="Archived 2015-16 file; carries 2016-17 EQAO results (sheet SIF_1516Data_EQAO1617_EN)",
         url="https://files.ontario.ca/opendata/sif_data_table_2015_2016_en.xlsx"),
]

CONTACT_RESOURCE = dict(
    id="contact-2026-11", year="November 2026",
    url="https://data.ontario.ca/dataset/fb3a7c18-90af-453e-bc0a-a76ecc471862/resource/f3a8c2a3-09d9-4715-9044-d8a0189f572c/download/public_school_contact_list_november2026_en.txt",
    note="Publicly funded schools, November 2026",
)

SBPR_URL = "https://data.ontario.ca/en/dataset/71244894-f3e1-4be0-a69a-9bdc4eb45ac1/resource/{}/download/{}"
SBPR_RESOURCES = [
    dict(id="sbpr-2026-11", year="2025-26", eqao_year="2025-26", credits_year="2024-25", grad_year="2024-25",
         url=SBPR_URL.format("53f3c491-98dc-44b6-9ed2-6a9e0d5f310a", "updated_sbpr_data_table_en_nov2026.xlsx"),
         note="November 2026 release: EQAO 2025-26, credit accumulation 2024-25, graduation rates 2024-25"),
    dict(id="sbpr-2026-05", year="2024-25", eqao_year="2024-25", credits_year="2024-25", grad_year="2023-24",
         url=SBPR_URL.format("9d81dc27-32ef-4864-94b5-f09950d00c72", "updated_sbpr_data_table_en_may2026.xlsx"),
         note="May 2026 release: EQAO 2024-25, credit accumulation 2024-25, graduation rates 2023-24"),
]

ENROL_RESOURCES = [
    dict(id="enrol-2024-25", year="2024-25", url=ENR_URL.format("5205b284-8f9d-4d97-8e3f-fb5391d0911d", "enrolment_by_school_2425_en.txt")),
    dict(id="enrol-2023-24", year="2023-24", url=ENR_URL.format("d490d94c-a2f2-49a9-8cae-19f4c4342611", "enrolment_supp_en_2023-2024.txt")),
    dict(id="enrol-2022-23", year="2022-23", url=ENR_URL.format("63d5fd29-ece6-4ea3-b4b5-13951c0c209f", "enrolment_supp_en_2022-2023.txt")),
    dict(id="enrol-2021-22", year="2021-22", url=ENR_URL.format("6beacf63-55c0-4f1c-9759-f611f642e6f3", "enrolment_by_school_2122_en_supp.txt")),
    dict(id="enrol-2020-21", year="2020-21", url=ENR_URL.format("c328c012-9b25-4668-b6ad-f8327fbe6806", "en_public_schools_enrolment_2020-21.txt")),
    dict(id="enrol-2019-20", year="2019-20", url=ENR_URL.format("8cf44c8a-5feb-4af1-82c9-fc2524b84fff", "enrolment_supp_en_2019-2020.txt")),
    dict(id="enrol-2018-19", year="2018-19", url=ENR_URL.format("fec01aff-e961-4258-a38a-a84b5d9e7505", "enrol_by_sch_1819_en.txt")),
    dict(id="enrol-2017-18", year="2017-18", url="https://files.ontario.ca/opendata/enrol_by_schl_1718_en.txt"),
    dict(id="enrol-2016-17", year="2016-17", url="https://files.ontario.ca/opendata/enrl_byschen_0.txt"),
    dict(id="enrol-2015-16", year="2015-16", url="https://files.ontario.ca/opendata/enrl_byschen.txt"),
    dict(id="enrol-2014-15", year="2014-15", url="https://files.ontario.ca/opendata/enrl_by_schen.txt"),
    dict(id="enrol-2013-14", year="2013-14", url="https://files.ontario.ca/opendata/enrolment_by_school_2013-14_en.txt"),
    dict(id="enrol-2012-13", year="2012-13", url="https://files.ontario.ca/opendata/enrolment_by_school_2012-2013_en.txt"),
    dict(id="enrol-2011-12", year="2011-12", url="https://files.ontario.ca/opendata/enrolment_by_school_2011-2012_en_2.txt"),
]

CHILDCARE_RESOURCE = dict(
    id="childcare-2026-09", year="September 30, 2026",
    url="https://data.ontario.ca/dataset/7efd8b4b-cc63-4337-a551-c940a346605b/resource/2b81313c-9ada-4680-abba-4470ec386a2e/download/child_care_facilities_open_data_sep_2026.xlsx",
    note="Snapshot of licensed child care centres and home child care agencies as of September 30, 2026",
)

# Statistics Canada's www12 download site sits behind a browser check that automated
# clients cannot pass. We try the official file first and, when it is blocked, read the
# same 2021 cartographic boundary file from Esri Canada's open republication of it
# (published under the Statistics Canada Open Licence). We never bypass the check.
FSA_RESOURCE = dict(
    id="fsa-boundary-2021", year="2021 Census",
    url="https://www12.statcan.gc.ca/census-recensement/2021/geo/sip-pis/boundary-limites/files-fichiers/lfsa000b21a_e.zip",
    mirror="https://services.arcgis.com/wjcPoefzjpzCgffS/arcgis/rest/services/Forward_Sortation_Area_(FSA)_Boundaries_2021/FeatureServer/0",
    mirror_landing="https://www.arcgis.com/home/item.html?id=aa8cbc1d6c0e47c7b08613d72c0c95b3",
    note="Statistics Canada 2021 cartographic FSA boundaries (lfsa000b21a_e)",
)

CENSUS_RESOURCE = dict(
    id="census-2021-fsa", year="2021 Census",
    url="https://api.statcan.gc.ca/census-recensement/profile/sdmx/rest/dataflow/STC_CP/DF_FSA/1.0",
    api="https://api.statcan.gc.ca/census-recensement/profile/sdmx/rest/data/STC_CP,DF_FSA,1.0/",
    note="Census Profile 2021 by forward sortation area, via Statistics Canada's Census Profile SDMX API",
)

# Census Profile characteristic ids (CL_CHARACTERISTIC, DF_FSA) and the statistic we read.
# statistic 1 = counts, 4 = rates/percentages.
CENSUS_FIELDS = [
    # key, characteristic id, statistic, label, unit
    ("population", "1", "1", "Population, 2021", "count"),
    ("land_area_km2", "7", "1", "Land area (square kilometres)", "number"),
    ("density_per_km2", "6", "1", "Population density per square kilometre", "number"),
    ("children_0_14", "9", "1", "Children aged 0 to 14", "count"),
    ("children_0_14_pct", "9", "4", "Share of the population aged 0 to 14", "pct"),
    ("age_0_4", "10", "1", "Children aged 0 to 4", "count"),
    ("age_5_9", "11", "1", "Children aged 5 to 9", "count"),
    ("age_10_14", "12", "1", "Children aged 10 to 14", "count"),
    ("households", "100", "1", "Private households", "count"),
    ("couple_hh_children_pct", "103", "4", "Households that are couples with children", "pct"),
    ("one_parent_hh_pct", "105", "4", "Households that are one-parent families", "pct"),
    ("median_household_income", "229", "1", "Median total income of households in 2020", "dollars"),
    ("low_income_0_17_pct", "332", "4", "Children 0–17 in low income (LIM-AT, 2020)", "pct"),
    ("lang_english_only_pct", "370", "4", "Know English only (official languages)", "pct"),
    ("lang_french_only_pct", "371", "4", "Know French only", "pct"),
    ("lang_both_pct", "372", "4", "Know both English and French", "pct"),
    ("lang_neither_pct", "373", "4", "Know neither English nor French", "pct"),
    ("home_english_pct", "724", "4", "Speak English most often at home", "pct"),
    ("home_french_pct", "725", "4", "Speak French most often at home", "pct"),
    ("home_other_pct", "726", "4", "Speak a non-official language most often at home", "pct"),
]

# Links that explain codes and terms (cited on /methodology/).
REFERENCES = [
    ("EQAO: explanation of terms used in results (N/R, N/D, W)", "https://www.eqao.com/explanation-of-terms/"),
    ("Ontario: Find an elementary or secondary school (School Information Finder)", "https://www.ontario.ca/page/find-your-school"),
    ("OpenStreetMap copyright and licence", "https://www.openstreetmap.org/copyright"),
    ("OpenFreeMap (map tiles)", "https://openfreemap.org/"),
    ("Natural Resources Canada Geolocation Service (address search)", "https://natural-resources.canada.ca/maps-tools-and-publications/maps/geolocation-service"),
]


def all_resources() -> list[dict]:
    """Every downloadable resource with its dataset key attached."""
    out = []
    for r in SIF_RESOURCES:
        out.append({**r, "dataset": "sif"})
    out.append({**CONTACT_RESOURCE, "dataset": "contact"})
    for r in SBPR_RESOURCES:
        out.append({**r, "dataset": "sbpr"})
    for r in ENROL_RESOURCES:
        out.append({**r, "dataset": "enrol"})
    out.append({**CHILDCARE_RESOURCE, "dataset": "childcare"})
    for r in ENROL_GRADE_RESOURCES:
        out.append({**r, "dataset": "enrol_grade"})
    for r in CLASS_SIZE_RESOURCES:
        out.append({**r, "dataset": "class_size"})
    out.append({**FSL_RESOURCE, "dataset": "fsl"})
    out.append({**SHSM_RESOURCE, "dataset": "shsm"})
    out.append({**FSA_RESOURCE, "dataset": "fsa_boundary"})
    out.append({**CENSUS_RESOURCE, "dataset": "census"})
    return out


EGR_URL = "https://data.ontario.ca/dataset/502b8125-e48b-443a-b463-a5b76eda8c25/resource/{}/download/{}"
ENROL_GRADE_RESOURCES = [
    dict(id="egrade-2024-25", year="2024-25", url=EGR_URL.format("9b8f3fb2-5008-4f04-9857-5e0e35feff60", "enrolment_by_grade_2024-2025_en.txt")),
    dict(id="egrade-2023-24", year="2023-24", url=EGR_URL.format("aa4bae0d-95b0-4d13-b7ee-20bdca16f432", "enrol_by_grade_en.txt")),
    dict(id="egrade-2022-23", year="2022-23", url=EGR_URL.format("5771f96b-0c04-4f87-8c18-a2258a163cdf", "enrol_grade_en.txt")),
    dict(id="egrade-2021-22", year="2021-22", url=EGR_URL.format("948c3dc9-f3a0-4cfa-a70a-e2fb779b09dc", "enrol_grade_2122_en.txt")),
    dict(id="egrade-2020-21", year="2020-21", url=EGR_URL.format("7b5d32cf-4f67-43c7-9aef-c435c5158d29", "en_school_enrolment_by_grade_2020-2021.txt")),
    dict(id="egrade-2019-20", year="2019-20", url=EGR_URL.format("0e44519d-0d49-426b-87cb-a209afeb21d0", "enrol_grade_en_1920.txt")),
    dict(id="egrade-2018-19", year="2018-19", fmt="xlsx", url=EGR_URL.format("daf0e0e2-2fb0-41a3-b8db-d80a9f77d4b5", "pubschenrolgr1819en_supp.xlsx")),
    dict(id="egrade-2017-18", year="2017-18", fmt="xlsx", url=EGR_URL.format("3db3bb6a-7dff-4015-9534-e78a19425feb", "pubschenrolgr1718en_supp.xlsx")),
]

CS_URL = "https://data.ontario.ca/dataset/c43b5632-599b-43d1-86b5-2439f3d68c93/resource/{}/download/{}"
CLASS_SIZE_RESOURCES = [
    dict(id="classsize-2007-23", year="2007-08 to 2022-23", url=CS_URL.format("95db507f-ccae-4711-836f-f5571fcea753", "2007-08_to_2022-23_class_size_data_june_15.xlsx"),
         note="One sheet per school year; before 2014-15 only primary (JK to Grade 3) classes are listed"),
    dict(id="classsize-2023-24", year="2023-24", url=CS_URL.format("41110399-2d30-43f3-8967-e8e55185aa6a", "elementary_class_size_open_data_suppressed_2023-24_fr.xlsx")),
    dict(id="classsize-2024-25", year="2024-25", url=CS_URL.format("abc5d307-ecfb-482f-b74f-f1703d2af039", "2024-25_elementary_class_size_open_data_v.1_engfr.xlsx")),
    dict(id="classsize-2025-26", year="2025-26", url=CS_URL.format("6f67ef06-a420-47cb-bf6b-2621adc2ffb0", "2025-26_elementary_class_sizes_open_data1.xlsx")),
]

FSL_RESOURCE = dict(
    id="fsl-2024-25", year="2024-25",
    url="https://data.ontario.ca/dataset/0743f4d3-64bb-4b76-b9fc-51743c7a7f46/resource/3b211d55-85b6-4f35-ac54-58e2d2452372/download/schools_offering_fsl_2425_en.txt",
    note="Preliminary 2024-25 list (the catalogue labels the files 2023-2024); English-language school boards only",
)
SHSM_RESOURCE = dict(
    id="shsm-2025-26", year="2025-26",
    url="https://data.ontario.ca/dataset/8ee79eb8-9e2c-4fb0-a2a5-51f54f2f383f/resource/e2336170-94cb-475f-8ada-0a0250dc258a/download/shsm_2025-26_program_list_en.csv",
)
