"""
Seed list of Israeli university faculty index URLs.

Add or remove entries here to control which pages the daily ingestion
pipeline crawls. The scheduler reads this list at startup.
"""

FACULTY_INDEX_URLS: list[str] = [
    # Hebrew University of Jerusalem
    "https://cs.huji.ac.il/en/people/faculty",
    "https://en.lifesci.huji.ac.il/people/faculty-members",

    # Technion — Israel Institute of Technology
    "https://www.cs.technion.ac.il/faculty/",
    "https://biomedical.technion.ac.il/faculty/",

    # Tel Aviv University
    "https://en-exact-sciences.tau.ac.il/computer/faculty",
    "https://medicine.tau.ac.il/research_groups",

    # Weizmann Institute of Science
    "https://www.weizmann.ac.il/pages/scientific-departments",

    # Ben-Gurion University of the Negev
    "https://in.bgu.ac.il/en/engn/ece/Pages/Staff.aspx",
    "https://in.bgu.ac.il/en/natural/cs/Pages/Faculty.aspx",

    # Bar-Ilan University
    "https://cs.biu.ac.il/en/node/491",

    # University of Haifa
    "https://cs.haifa.ac.il/en/faculty",
]
