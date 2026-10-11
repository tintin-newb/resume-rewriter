## Repository Structure
```sh
resume_rewriter/
├── config/
│   ├── __init__.py
│   └── settings.py          # Environment settings via Pydantic
├── db/
│   ├── schema.sql           # Database DDL script
│   ├── __init__.py
│   └── connection.py        # Connection test and table verification
├── parsers/
│   ├── __init__.py
│   ├── base.py              # Base parser interface (ABC)
│   ├── resume_parser.py     # PDF / Text resume extractor
│   └── verb_parser.py       # Action verb PDF parser
├── bootstrap.py             # System health-check runner
├── .env.example             # Template configuration
└── requirements.txt         # Dependencies
```