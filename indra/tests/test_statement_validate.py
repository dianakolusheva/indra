from nose.tools import assert_raises
from indra.statements import Evidence
from indra.statements.validate import *


def test_db_refs_validate():
    assert validate_db_refs({'HGNC': '1234'})
    assert not validate_db_refs({'XXX': '1234'})
    assert not validate_db_refs({'HGNC': 'ABCD1'})

    assert validate_ns('UP')
    assert not validate_ns('XXX')
    assert validate_id('MESH', 'D123456')
    assert not validate_id('CHEBI', '12345')

    assert_valid_id('NXPFA', '1234')
    assert_valid_id('TEXT', 'hello')
    assert_raises(InvalidIdentifier, assert_valid_id,
                  'XXX', 'ABCD1')


def test_text_refs_validate():
    assert_raises(InvalidTextRefs, assert_valid_text_refs,
                  {'pmid': '123'})
    assert_raises(InvalidTextRefs, assert_valid_text_refs,
                  {'PMID': 'api123'})
    assert_raises(InvalidTextRefs, assert_valid_text_refs,
                  {'DOI': 'https://xyz'})
    assert_raises(InvalidTextRefs, assert_valid_text_refs,
                  {'PMCID': '12345'})
    assert_valid_text_refs({'PMID': '12345'})
    assert_valid_text_refs({'PMCID': 'PMC12345'})
    assert_valid_text_refs({'DOI': '10.15252/msb.20177651'})


def test_pmid_text_refs_validate():
    assert_valid_pmid_text_refs(Evidence(pmid=None))
    assert_valid_pmid_text_refs(Evidence(pmid='1234'))
    assert_valid_pmid_text_refs(Evidence(pmid='1234',
                                         text_refs={'PMID': '1234'}))
    assert_raises(InvalidTextRefs, assert_valid_pmid_text_refs,
                  Evidence(pmid='1234', text_refs={'PMID': '12345'}))
    assert_raises(InvalidTextRefs, assert_valid_pmid_text_refs,
                  Evidence(pmid=None, text_refs={'PMID': '123'}))
