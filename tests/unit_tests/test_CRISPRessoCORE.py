"""Unit tests for CRISPResso2CORE."""
import pytest

from pytest_check import check

from CRISPResso2 import CRISPRessoCORE


def calc_score(seq, ref):
    score = 0
    for seq_i, ref_i in zip(seq, ref):
        if seq_i == ref_i:
            score += 1
    return int(100 * score / float(len(seq)))


def test_get_consensus_alignment_from_pairs():
    """Tests for generating consensus alignments from paired reads."""
    try:
        CRISPRessoCORE.get_consensus_alignment_from_pairs
    except AttributeError:
        pytest.xfail('get_consensus_alignment_from_pairs is not implemented yet!')

    print("testing Easy")

    #basic test
    qual1                =   "AAAA"
    aln1_seq             = "--CGAT----"
    aln1_ref             = "ATCGATCGAT"
    aln2_seq             = "-----TCGAT"
    aln2_ref             = "ATCGATCGAT"
    qual2                =      "AAAAA"

    aln_seq, ref_seq, score, caching_ok = CRISPRessoCORE.get_consensus_alignment_from_pairs(
        aln1_seq,
        aln1_ref,
        calc_score(aln1_seq, aln1_ref),
        qual1,
        aln2_seq,
        aln2_ref,
        calc_score(aln2_seq, aln2_ref),
        qual2,
    )
    with check:
        assert aln_seq ==      "NNCGATCGAT"
        assert ref_seq ==      "ATCGATCGAT"
        assert score == 80
        assert caching_ok

    #test quality difference
    qual1                =   "AAAB"
    aln1_seq             = "--CGAT----"
    aln1_ref             = "ATCGATCGAT"
    aln2_seq             = "-----GCGAT"
    aln2_ref             = "ATCGATCGAT"
    qual2                =      "AAAAA"

    aln_seq, ref_seq, score, caching_ok = CRISPRessoCORE.get_consensus_alignment_from_pairs(
        aln1_seq,
        aln1_ref,
        calc_score(aln1_seq, aln1_ref),
        qual1,
        aln2_seq,
        aln2_ref,
        calc_score(aln2_seq, aln2_ref),
        qual2,
    )
    with check:
        assert aln_seq ==      "NNCGATCGAT"
        assert ref_seq ==      "ATCGATCGAT"
        assert score == 80
        assert not caching_ok

    #test quality difference
    qual1                =   "AAAA"
    aln1_seq             = "--CGAT----"
    aln1_ref             = "ATCGATCGAT"
    aln2_seq             = "-----GCGAT"
    aln2_ref             = "ATCGATCGAT"
    qual2                =      "BAAAA"

    aln_seq, ref_seq, score, caching_ok = CRISPRessoCORE.get_consensus_alignment_from_pairs(
        aln1_seq,
        aln1_ref,
        calc_score(aln1_seq, aln1_ref),
        qual1,
        aln2_seq,
        aln2_ref,
        calc_score(aln2_seq, aln2_ref),
        qual2,
    )
    with check:
        assert aln_seq ==      "NNCGAGCGAT"
        assert ref_seq ==      "ATCGATCGAT"
        assert score == 70
        assert not caching_ok

    #gaps between r1 and r2
    qual1                = "AAAAAAAAAA"
    aln1_seq             = "--CGA-----"
    aln1_ref             = "ATCGATCGAT"
    aln2_seq             = "-------GA-"
    aln2_ref             = "ATCGATCGAT"
    qual2                = "AAAAAAAAAA"

    aln_seq, ref_seq, score, caching_ok = CRISPRessoCORE.get_consensus_alignment_from_pairs(
        aln1_seq,
        aln1_ref,
        calc_score(aln1_seq, aln1_ref),
        qual1,
        aln2_seq,
        aln2_ref,
        calc_score(aln2_seq, aln2_ref),
        qual2,
    )
    with check:
        assert aln_seq ==      "NNCGANNGAN"
        assert ref_seq ==      "ATCGATCGAT"
        assert score == 50
        assert caching_ok

    print('Finished easy tests... now for the hard stuff')

    #insertion in r1
    qual1                =   "AAAA"
    aln1_seq             = "--CCGA-----".replace(" ","") #added replace for vertical alignment
    aln1_ref             = "ATC-GATCGAT".replace(" ","")
    aln2_seq             = "--- ----GA-".replace(" ","")
    aln2_ref             = "ATC GATCGAT".replace(" ","")
    qual2                =         "AA"

    aln_seq, ref_seq, score, caching_ok = CRISPRessoCORE.get_consensus_alignment_from_pairs(
        aln1_seq,
        aln1_ref,
        calc_score(aln1_seq, aln1_ref),
        qual1,
        aln2_seq,
        aln2_ref,
        calc_score(aln2_seq, aln2_ref),
        qual2,
    )
    with check:
        assert aln_seq ==      "NNCCGANNGAN"
        assert ref_seq ==      "ATC-GATCGAT"
        assert score == 45
        assert caching_ok

    #deletion in r1
    qual1                =   "AA"
    aln1_seq             = "--C-A-----".replace(" ","")
    aln1_ref             = "ATCGATCGAT".replace(" ","")
    aln2_seq             = "-------GA-".replace(" ","")
    aln2_ref             = "ATCGATCGAT".replace(" ","")
    qual2                =        "AA"

    aln_seq, ref_seq, score, caching_ok = CRISPRessoCORE.get_consensus_alignment_from_pairs(
        aln1_seq,
        aln1_ref,
        calc_score(aln1_seq, aln1_ref),
        qual1,
        aln2_seq,
        aln2_ref,
        calc_score(aln2_seq, aln2_ref),
        qual2,
    )
    with check:
        assert aln_seq ==      "NNC-ANNGAN"
        assert ref_seq ==      "ATCGATCGAT"
        assert score == 40
        assert caching_ok

    #insertion in r2
    qual1                =   "AAAA"
    aln1_seq             = "--CCGA-----".replace(" ","") #added replace for vertical alignment
    aln1_ref             = "ATCCGATC AT".replace(" ","")
    aln2_seq             = "--------GA-".replace(" ","")
    aln2_ref             = "ATCCGATC-AT".replace(" ","")
    qual2                =         "AA"

    aln_seq, ref_seq, score, caching_ok = CRISPRessoCORE.get_consensus_alignment_from_pairs(
        aln1_seq,
        aln1_ref,
        calc_score(aln1_seq, aln1_ref),
        qual1,
        aln2_seq,
        aln2_ref,
        calc_score(aln2_seq, aln2_ref),
        qual2,
    )
    with check:
        assert aln_seq ==      "NNCCGANNGAN"
        assert ref_seq ==      "ATCCGATC-AT"
        assert score == 45
        assert caching_ok

    # deletion in r2
    qual1                =   "AAA"
    aln1_seq             = "--CGA-----".replace(" ","")
    aln1_ref             = "ATCGATCGAT".replace(" ","")
    aln2_seq             = "-----T-GA-".replace(" ","")
    aln2_ref             = "ATCGATCGAT".replace(" ","")
    qual2                =      "AAA"

    aln_seq, ref_seq, score, caching_ok = CRISPRessoCORE.get_consensus_alignment_from_pairs(
        aln1_seq,
        aln1_ref,
        calc_score(aln1_seq, aln1_ref),
        qual1,
        aln2_seq,
        aln2_ref,
        calc_score(aln2_seq, aln2_ref),
        qual2,
    )
    with check:
        assert aln_seq ==      "NNCGAT-GAN"
        assert ref_seq ==      "ATCGATCGAT"
        assert score == 60
        assert caching_ok

    # insertion in r1 and r2
    qual1                =   "AAAAAA"
    aln1_seq             = "--CGATCC---".replace(" ","")
    aln1_ref             = "ATCGAT-CGAT".replace(" ","")
    aln2_seq             = "----ATACGA-".replace(" ","")
    aln2_ref             = "ATCGAT-CGAT".replace(" ","")
    qual2                =     "AAAAAA ".replace(" ", "")

    aln_seq, ref_seq, score, caching_ok = CRISPRessoCORE.get_consensus_alignment_from_pairs(
        aln1_seq,
        aln1_ref,
        calc_score(aln1_seq, aln1_ref),
        qual1,
        aln2_seq,
        aln2_ref,
        calc_score(aln2_seq, aln2_ref),
        qual2,
    )
    with check:
        assert aln_seq ==      "NNCGATCCGAN"
        assert ref_seq ==      "ATCGAT-CGAT"
        assert score == 63
        assert not caching_ok

    # insertion in r1 and r2, different positions
    qual1                =   "AAAAAA"
    aln1_seq             = "--CGATCC---".replace(" ","")
    aln1_ref             = "ATCGAT-CGAT".replace(" ","")
    aln2_seq             = "----ATATGA-".replace(" ","")
    aln2_ref             = "ATCGATC-GAT".replace(" ","")
    qual2                =     "AAAAAA ".replace(" ", "")

    aln_seq, ref_seq, score, caching_ok = CRISPRessoCORE.get_consensus_alignment_from_pairs(
        aln1_seq,
        aln1_ref,
        calc_score(aln1_seq, aln1_ref),
        qual1,
        aln2_seq,
        aln2_ref,
        calc_score(aln2_seq, aln2_ref),
        qual2,
    )
    with check:
        assert aln_seq ==      "NNCGATCCTGAN"
        assert ref_seq ==      "ATCGAT-C-GAT"
        assert score == 58
        assert not caching_ok

    # insertion at beginning of r1
    qual1                = "AAAAA"
    aln1_seq             = "TA-CGA----- ".replace(" ","")
    aln1_ref             = "-ATCGATCGAT ".replace(" ","")
    aln2_seq             = " --------AT ".replace(" ","")
    aln2_ref             = " ATCGATCGAT".replace(" ","")
    qual2                =          "AA"

    aln_seq, ref_seq, score, caching_ok = CRISPRessoCORE.get_consensus_alignment_from_pairs(
        aln1_seq,
        aln1_ref,
        calc_score(aln1_seq, aln1_ref),
        qual1,
        aln2_seq,
        aln2_ref,
        calc_score(aln2_seq, aln2_ref),
        qual2,
    )
    with check:
        assert aln_seq ==      "TA-CGANNNAT"
        assert ref_seq ==      "-ATCGATCGAT"
        assert score == 54
        assert caching_ok

    # insertion at end of r2 and beginning of r1
    qual1                = "AAAAA"
    aln1_seq             = "TA-CGA-----   ".replace(" ","")
    aln1_ref             = "-ATCGATCGAT   ".replace(" ","")
    aln2_seq             = " -----TCGATCCA".replace(" ","")
    aln2_ref             = " ATCGATCGAT---".replace(" ","")
    qual2                =       "AAAAAAAA"

    aln_seq, ref_seq, score, caching_ok = CRISPRessoCORE.get_consensus_alignment_from_pairs(
        aln1_seq,
        aln1_ref,
        calc_score(aln1_seq, aln1_ref),
        qual1,
        aln2_seq,
        aln2_ref,
        calc_score(aln2_seq, aln2_ref),
        qual2,
    )
    with check:
        assert aln_seq ==      "TA-CGATCGATCCA"
        assert ref_seq ==      "-ATCGATCGAT---"
        assert score == 64
        assert caching_ok

    qual1    = '>1>1A@DFAADAGGGGGGGGGGHHHHHHHHHHHHHHHGGHHHHHHHHGGGHHHHHHHHHGHHHHHHHHHHHHGHGGGGGGGGGGHHHHHHHGHHHHHHHHHHHHHHHHHHHHHHHGHHGGGGGHHHHG'
    aln1_seq = 'AATGTCCCCCAATGGGAAGTTCATCTGGCACTGCCCACAGGTGAGGAGGTCATGATCCCCTTCTGGAGCTCCCAACGCGGC-----CTGGTTCATCATCTGTAAGAATGGCTTCAAGAGGCTCGGCTGTGGTT'
    aln1_ref = 'AATGTCCCCCAATGGGAAGTTCATCTGGCACTGCCCACAGGTGAGGAGGTCATGATCCCCTTCTGGAGCTCCCAACGGGCCGTGGTCTGGTTCATCATCTGTAAGAATGGCTTCAAGAGGCTCGGCTGTGGTT'
    aln2_seq = 'AACCACAGCC-----GAGCCTCTTGAAGCCATTCTTACAGATGATGAAC-CAGG--CCGCGTTGGGAGCTCCAGAAGGGGATCATGACCT----CCTCACCTGTGGGCAGTGCCAGATGAACTTCCCATTGGGGGACATT'
    aln2_ref = 'AATGTCCCCCAATGGGAAGTTCATCTGGCACTGCCCACAGGTGAGGAGGTCATGATCCCCTTCTGGAGCTCCCAACGGGC--CGTGGTCTGGTTCATCATCTGTAAGAATGGCTTCAAGAGGCTCGGCTGTGGTT-----'
    qual2    = 'BCCDCCDFDDDDGGGGGGGGGGHHHHHHHHHHHHHHHHHHHHHHHHHGHGGGGGGGHGHGGHHHHHHHHHGGGGGHHHHHHHHHHHHHHHHHHHGGHGHHHHHHHHHHHHHHHHHHHHHHHGGGGGHH'

    aln_seq, ref_seq, score, caching_ok = CRISPRessoCORE.get_consensus_alignment_from_pairs(
        aln1_seq,
        aln1_ref,
        calc_score(aln1_seq, aln1_ref),
        qual1,
        aln2_seq,
        aln2_ref,
        calc_score(aln2_seq, aln2_ref),
        qual2,
    )
    with check:
        assert aln_seq == 'AACCACCCCCAATGGGAAGTTCATCTGGCACTGCCCACAGGTGAGGAACTCATGATCCCCTTCTGGAGCTCCAAAAGGGGATCATGACCTGGTTCATCATCTGTAAGAATGGCTTCAAGAGGTTCCCATTTGGTTACATT'
        assert ref_seq == 'AATGTCCCCCAATGGGAAGTTCATCTGGCACTGCCCACAGGTGAGGAGGTCATGATCCCCTTCTGGAGCTCCCAACGGGC--CGTGGTCTGGTTCATCATCTGTAAGAATGGCTTCAAGAGGCTCGGCTGTGGTT-----'
        assert score == 83
        assert not caching_ok

    aln_seq, ref_seq, score, caching_ok = CRISPRessoCORE.get_consensus_alignment_from_pairs(aln1_seq, aln1_ref, calc_score(aln1_seq, aln1_ref), qual1, aln2_seq, aln2_ref, calc_score(aln2_seq, aln2_ref), qual2)
    check.equal(aln_seq, "TA-CGANNNAT")
    check.equal(ref_seq, "-ATCGATCGAT")
    check.equal(score, 54) #double check this score... should be 6/11
    # check.is_true(caching_ok) # check this

    # alternating qualities
    qual1                = "BABABABABA"
    aln1_seq             = "ACCAACCAAT".replace(" ","")
    aln1_ref             = "ATCGATCGAT".replace(" ","")
    aln2_seq             = "TTGGTTGGTT".replace(" ","")
    aln2_ref             = "ATCGATCGAT".replace(" ","")
    qual2                = "ABABABABAB"

    aln_seq, ref_seq, score, caching_ok = CRISPRessoCORE.get_consensus_alignment_from_pairs(aln1_seq, aln1_ref, calc_score(aln1_seq, aln1_ref), qual1, aln2_seq, aln2_ref, calc_score(aln2_seq, aln2_ref), qual2)
    check.equal(aln_seq, "ATCGATCGAT")
    check.equal(ref_seq, "ATCGATCGAT")
    check.equal(score, 100)
    # check.is_true(caching_ok) # check this

    # large insertion in r1
    qual1                = "AAAAAA"
    aln1_seq             = "ACGTGA---------".replace(" ","")
    aln1_ref             = "A-----TCGATCGAT".replace(" ","")
    aln2_seq             = "------CGAT".replace(" ","")
    aln2_ref             = "ATCGATCGAT".replace(" ","")
    qual2                =       "AAAA"

    aln_seq, ref_seq, score, caching_ok = CRISPRessoCORE.get_consensus_alignment_from_pairs(aln1_seq, aln1_ref, calc_score(aln1_seq, aln1_ref), qual1, aln2_seq, aln2_ref, calc_score(aln2_seq, aln2_ref), qual2)
    check.equal(aln_seq, "ACGTGANNNNNCGAT")
    check.equal(ref_seq, "A-----TCGATCGAT")
    check.equal(score, 33)
    # check.is_true(caching_ok) # check this

    # large insertion in r2
    qual1                = "AAAAA"
    aln1_seq             = "ATCGA-----".replace(" ","")
    aln1_ref             = "ATCGATCGAT".replace(" ","")
    aln2_seq             = "-----TTAGCT---".replace(" ","")
    aln2_ref             = "ATCGAT---C-GAT".replace(" ","")
    qual2                =      "AAAAAA"

    aln_seq, ref_seq, score, caching_ok = CRISPRessoCORE.get_consensus_alignment_from_pairs(aln1_seq, aln1_ref, calc_score(aln1_seq, aln1_ref), qual1, aln2_seq, aln2_ref, calc_score(aln2_seq, aln2_ref), qual2)
    check.equal(aln_seq, "ATCGATTAGCTNNN")
    check.equal(ref_seq, "ATCGAT---C-GAT") #TODO: Is this right? ATCGATCCCCGGAT
    check.equal(score, 50)
    # check.is_true(caching_ok) # check this

    # Conflicts with reference
    qual1                = "AAAAAAAAAA"
    aln1_seq             = "TAGCTAGCTA".replace(" ","")
    aln1_ref             = "ATCGATCGAT".replace(" ","")
    aln2_seq             = "TAGCTAGCTA".replace(" ","")
    aln2_ref             = "ATCGATCGAT".replace(" ","")
    qual2                = "AAAAAAAAAA"

    aln_seq, ref_seq, score, caching_ok = CRISPRessoCORE.get_consensus_alignment_from_pairs(aln1_seq, aln1_ref, calc_score(aln1_seq, aln1_ref), qual1, aln2_seq, aln2_ref, calc_score(aln2_seq, aln2_ref), qual2)
    check.equal(aln_seq, "TAGCTAGCTA")
    check.equal(ref_seq, "ATCGATCGAT")
    check.equal(score, 0)
    # check.is_true(caching_ok) # check this

    # Conflicts between reads
    qual1                = "AAAAAAAAAA"
    aln1_seq             = "TAGCTAGCTA".replace(" ","")
    aln1_ref             = "ATCGATCGAT".replace(" ","")
    aln2_seq             = "ATCGATCGAT".replace(" ","")
    aln2_ref             = "ATCGATCGAT".replace(" ","")
    qual2                = "AAAAAAAAAA"

    aln_seq, ref_seq, score, caching_ok = CRISPRessoCORE.get_consensus_alignment_from_pairs(aln1_seq, aln1_ref, calc_score(aln1_seq, aln1_ref), qual1, aln2_seq, aln2_ref, calc_score(aln2_seq, aln2_ref), qual2)
    check.equal(aln_seq, "TAGCTAGCTA") #Should it take r1 or the one that's like the reference sequence? - For Kendell
    check.equal(ref_seq, "ATCGATCGAT")
    check.equal(score, 0)
    # check.is_true(caching_ok) # check this

    # Alternating reads
    qual1                = "AAAAAAAAAA"
    aln1_seq             = "AT--AT--AT".replace(" ","")
    aln1_ref             = "ATCGATCGAT".replace(" ","")
    aln2_seq             = "--CG--CG--".replace(" ","")
    aln2_ref             = "ATCGATCGAT".replace(" ","")
    qual2                = "AAAAAAAAAA"

    aln_seq, ref_seq, score, caching_ok = CRISPRessoCORE.get_consensus_alignment_from_pairs(aln1_seq, aln1_ref, calc_score(aln1_seq, aln1_ref), qual1, aln2_seq, aln2_ref, calc_score(aln2_seq, aln2_ref), qual2)
    check.equal(aln_seq, "ATCGATCGAT") #TODO: Failure returns AT-AT-AT
    check.equal(ref_seq, "ATCGATCGAT")
    check.equal(score, 100) #TODO: See above, score 60
    # check.is_true(caching_ok) # check this


if __name__ == "__main__":
    test_get_consensus_alignment_from_pairs()
