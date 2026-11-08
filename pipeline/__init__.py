"""web-outreach pipeline.

Python part of the "new website as the first contact" outreach system:
Google Places search -> website audit -> AI/template copy -> one-page preview
-> screenshots -> publish. n8n drives the human approval and e-mail flow and
talks to this package through ``pipeline.api`` (HTTP) or ``pipeline.cli``.
"""

__version__ = "0.1.0"
