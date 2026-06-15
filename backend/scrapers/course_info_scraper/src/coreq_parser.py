from __future__ import annotations

from .prereq_parser import PrereqParser


# ----- CoreqParser --------------------
class CoreqParser(PrereqParser):
    def __init__(self):
        """
        Parses corequisite HTML from Kuali API into structured corequisite trees according to 
        predefined schema.
        """

        super().__init__()