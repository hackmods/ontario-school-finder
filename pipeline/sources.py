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
    "attendance": {
        "brief_no": 11,
        "title": "Board-published attendance boundaries",
        "publisher": "Individual school boards",
        "landing": "",
        "licence": ("Per board; written permission recorded before use", ""),
        "used_for": "Not used yet (Phase 2). Every school page links to its board so parents can use the board's own school locator.",
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
    out.append({**FSA_RESOURCE, "dataset": "fsa_boundary"})
    out.append({**CENSUS_RESOURCE, "dataset": "census"})
    return out
