"""US-09 unit tests: the Librarian chops, tags, and ranks winning blocks
first; quarantined blocks are the caller's job to exclude (tested at the
API level)."""

from bidproof_librarian import LibraryBlock, chop_proposal, rank_blocks

PROPOSAL = """Company Profile
We are an established manufacturer of industrial storage systems with
three decades of experience.

Technical Approach
Our racking systems are engineered to IS 4923 and installed by certified
crews using calibrated torque tooling.

Delivery and Support
Pan-India installation teams with a 24x7 support desk and spare stocking.

Declarations
We hereby declare that the information furnished is true and correct.
"""


def test_chop_splits_into_tagged_blocks_with_outcome():
    blocks = chop_proposal(PROPOSAL, outcome="won", source_name="CWC 2024 bid")
    tags = [b.section_tag for b in blocks]
    assert "company_profile" in tags
    assert "technical_approach" in tags
    assert "delivery_and_support" in tags
    assert "declarations" in tags
    assert all(b.outcome == "won" for b in blocks)
    assert all(b.source_name == "CWC 2024 bid" for b in blocks)
    technical = next(b for b in blocks if b.section_tag == "technical_approach")
    assert "IS 4923" in technical.text


def test_ranking_puts_winning_blocks_first():
    won = LibraryBlock("technical_approach", "racking systems per IS 4923",
                       "won", "bid A")
    lost = LibraryBlock("technical_approach", "racking systems per IS 4923",
                        "lost", "bid B")
    synthetic = LibraryBlock("technical_approach", "racking systems per IS 4923",
                             "synthetic", "starter")
    ranked = rank_blocks("technical_approach", "storage racking IS 4923",
                         [lost, synthetic, won], top_k=3)
    assert [b.outcome for b in ranked] == ["won", "synthetic", "lost"]


def test_ranking_filters_by_section_and_relevance():
    relevant = LibraryBlock("technical_approach", "pallet racking installation",
                            "synthetic", "starter")
    other_section = LibraryBlock("commercial_terms", "payment in 30 days",
                                 "won", "bid A")
    ranked = rank_blocks("technical_approach", "pallet racking",
                         [relevant, other_section])
    assert ranked == [relevant]


def test_malformed_document_yields_no_invented_blocks():
    assert chop_proposal("no headings here, just prose", "won", "x") == []
