from app.models.lab import LabProfile

_DEBUG_STUB = [
    LabProfile(
      pi_name="Hagit Hel-Or",
      institution="University of Haifa",
      faculty="Computer Science",
      research_summary=[
        "Head of the Computational Human Behavior lab focusing on understanding human behavior through Computer Vision and Machine Learning",
        "Develops novel algorithms to study behavioral questions in psychology, physiology, and physiotherapy",
        "Applies data science tools to automate balance testing for elderly individuals and diagnostics for mental disorders",
        "Researches abnormal language development and sign language using AI-based analysis"
      ],
      keywords=[
        "Computer Vision",
        "Machine Learning",
        "Behavioral Science",
        "Data Science",
        "Human Behavior Analysis",
        "Medical Informatics"
      ],
      technologies=[
        "Computer Vision",
        "Machine Learning",
        "Data Science",
        "Computerized Adaptive Testing",
        "Sensors",
        "Biomedical Informatics",
        "Behavioral Economics",
        "Sign Language Analysis"
      ],
      hiring_status="Not mentioned",
      lab_url="https://cis.haifa.ac.il/staff/%d7%97%d7%92%d7%99%d7%aa-%d7%94%d7%9c-%d7%90%d7%95%d7%a8/",
      representative_papers=[
        "Remote fall prevention training for community-dwelling older adults: comparison with face-to-face and effect of delivery sequence-A randomized controlled trial",
        "Shortening the MacArthur-Bates Communicative Developmental Inventory Using Machine Learning Based Computerized Adaptive Testing (ML-CAT)",
        "The Argenta Classification for Positional Plagiocephaly in Infants: An Inter-and Intra-Rater Reliability Study",
        "Feasibility and effectiveness of physical exercise for older adults delivered remotely via videoconferencing—systematic review and meta analysis",
        "Publication 3: Feasibility and effectiveness of physical exercise for older adults delivered remotely via videoconferencing–Systematic review and Meta analysis"
      ]
    ),
    LabProfile(
      pi_name="Omri Abend",
      institution="The Hebrew University of Jerusalem",
      faculty="Computer Science and Engineering; Cognitive and Brain Sciences",
      research_summary=[
        "Developing manual and computational methods for mapping text to structured semantic and grammatical representations",
        "Modeling the computational mechanisms of child language acquisition and word categorization",
        "Advancing language technologies including neural machine translation, information extraction, and LLM evaluation"
      ],
      keywords=[
        "NLP",
        "Computational Linguistics",
        "Semantic Parsing",
        "Machine Translation",
        "Language Acquisition"
      ],
      technologies=[
        "Large Language Models",
        "Natural Language Processing",
        "Computational Linguistics",
        "Semantic Parsing",
        "Reinforcement Learning",
        "Machine Translation",
        "Information Extraction",
        "Cognitive Modeling",
        "Lexical Alignment",
        "Text Simplification",
        "Image Captioning",
        "Theory of Mind",
        "Universal Conceptual Cognitive Annotation"
      ],
      hiring_status="Not mentioned",
      lab_url="https://www.cs.huji.ac.il/~oabend/",
      representative_papers=[
        "Surveying the Landscape of Image Captioning Evaluation: A Comprehensive Taxonomy, Trends and Metrics Analysis",
        "Computational Analysis of Character Development in Holocaust Testimonies",
        "Mind Your Theory: Theory of Mind Goes Deeper Than Reasoning",
        "T5Score: A Methodology for Automatically Assessing the Quality of LLM Generated Multi-Document Topic Sets",
        "Beneath the Surface of Consistency: Exploring Cross-lingual Knowledge Representation Sharing in LLMs"
     ]
),
    LabProfile(pi_name="Sahar Melamed",
      institution="The Hebrew University of Jerusalem",
      faculty="The Faculty of Medicine",
      research_summary=[
        "Investigation of regulatory RNAs and their roles in bacterial physiology",
        "Study of the relationships between bacteria and their environment",
        "Analysis of RNA-RNA interactomes using specialized sequencing techniques",
        "Research into phage-encoded small RNAs and their impact on host replication"
      ],
      keywords=[
        "RNA biology",
        "Bacterial genetics",
        "RIL-seq",
        "Regulatory RNA",
        "Bacteriophage",
        "Vibrio cholerae"
      ],
      technologies=[
        "RNA-RNA interactomes",
        "RIL-seq",
        "Transcriptomics",
        "Bacterial Physiology",
        "Phage Biology",
        "Gene Regulation",
        "Microbiology"
      ],
      hiring_status=True,
      lab_url="https://melamed-rna-lab.huji.ac.il/",
      representative_papers=[
        "Phage-encoded small RNA hijacks host replication machinery to support the phage lytic cycle",
        "Biological insights from RNA–RNA interactomes in bacteria, as revealed by RIL-seq",
        "ProQ-associated small RNAs control motility in Vibrio cholerae"
      ]
    )
]
DEBUG_STUB = _DEBUG_STUB  # Exported for debug scripts
