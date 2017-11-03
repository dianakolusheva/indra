from __future__ import absolute_import, print_function, unicode_literals
from builtins import dict, str
import logging
import requests
from sympy.physics import units
from indra.databases import chebi_client, uniprot_client
from indra.statements import Inhibition, Agent, Evidence
from collections import defaultdict

logger = logging.getLogger('chembl')


def get_inhibition(drug, target):
    chebi_id = drug.db_refs.get('CHEBI')
    mesh_id = drug.db_refs.get('MESH')
    if chebi_id:
        drug_chembl_id = chebi_client.get_chembl_id(chebi_id)
    elif mesh_id:
        drug_chembl_id = get_chembl_id(mesh_id)
    else:
        logger.error('Drug missing ChEBI or MESH grounding.')
        return None

    target_upid = target.db_refs.get('UP')
    if not target_upid:
        logger.error('Target missing UniProt grounding.')
        return None
    target_chembl_id = get_target_chemblid(target_upid)

    logger.info('Drug: %s, Target: %s' % (drug_chembl_id, target_chembl_id))
    query_dict = {'query': 'activity',
                  'params': {'molecule_chembl_id': drug_chembl_id,
                             'target_chembl_id': target_chembl_id,
                             'limit': 10000}}
    res = send_query(query_dict)
    evidence = []
    for assay in res['activities']:
        ev = get_evidence(assay)
        if not ev:
            continue
        evidence.append(ev)
    st = Inhibition(drug, target, evidence=evidence)
    return st


def get_drug_inhibition_stmts(drug):
    """Query ChEMBL for kinetics data given drug as Agent get back statements

    Parameters
    ----------
    drug : Agent
        Agent representing drug with MESH or CHEBI grounding
    Returns
    -------
    stmts : list of INDRA statements
        INDRA statements generated by querying ChEMBL for all kinetics data of
        a drug interacting with protein targets
    """
    chebi_id = drug.db_refs.get('CHEBI')
    mesh_id = drug.db_refs.get('MESH')
    if chebi_id:
        drug_chembl_id = chebi_client.get_chembl_id(chebi_id)
    elif mesh_id:
        drug_chembl_id = get_chembl_id(mesh_id)
    else:
        logger.error('Drug missing ChEBI or MESH grounding.')
        return None
    logger.info('Drug: %s' % (drug_chembl_id))
    query_dict = {'query': 'activity',
                  'params': {'molecule_chembl_id': drug_chembl_id,
                             'limit': 10000}
                  }
    res = send_query(query_dict)
    activities = res['activities']
    targ_act_dict = activities_by_target(activities)
    target_chembl_ids = [x for x in targ_act_dict]
    protein_targets = get_protein_targets_only(target_chembl_ids)
    filtered_targ_act_dict = {t: targ_act_dict[t]
                              for t in [x for x in protein_targets]}
    stmts = []
    for target_chembl_id in filtered_targ_act_dict:
        target_activity_ids = filtered_targ_act_dict[target_chembl_id]
        target_activites = [x for x in activities
                            if x['activity_id'] in target_activity_ids]
        target_upids = []
        targ_comp = protein_targets[target_chembl_id]['target_components']
        for t_c in targ_comp:
            target_upids.append(t_c['accession'])
        evidence = []
        for assay in target_activites:
            ev = get_evidence(assay)
            if not ev:
                continue
            evidence.append(ev)
        if len(evidence) > 0:
            for target_upid in target_upids:
                agent_name = uniprot_client.get_gene_name(target_upid)
                target_agent = Agent(agent_name, db_refs={'UP': target_upid})
                st = Inhibition(drug, target_agent, evidence=evidence)
                stmts.append(st)
    return stmts


def send_query(query_dict):
    """Query ChEMBL API

    Parameters
    ----------
    query_dict : dict
        'query' : string of the endpoint to query
        'params' : dict of params for the query
    Returns
    -------
    js : dict
        dict parsed from json that is unique to the submitted query

    Example
    -------
    >>> query_dict = {'query': 'target',
    ...               'params': {'target_chembl_id': 'CHEMBL5145',
    ...               'limit': 1}}
    >>> send_query(query_dict)
    """
    query = query_dict['query']
    params = query_dict['params']
    url = 'https://www.ebi.ac.uk/chembl/api/data/' + query + '.json'
    r = requests.get(url, params=params)
    r.raise_for_status()
    js = r.json()
    return js


def query_target(target_chembl_id):
    """Query ChEMBL API target by id

    Parameters
    ----------
    target_chembl_id : str
    Returns
    -------
    target : dict
        dict parsed from json that is unique for the target
    """
    query_dict = {'query': 'target',
                  'params': {'target_chembl_id': target_chembl_id,
                             'limit': 1}}
    res = send_query(query_dict)
    assert(res['page_meta']['total_count'] == 1)
    target = res['targets'][0]
    return target


def activities_by_target(activities):
    """Get back lists of activities in a dict keyed by ChEMBL target id

    Parameters
    ----------
    activities : list
        response from a query returning activities for a drug
    Returns
    -------
    targ_act_dict : dict
        dictionary keyed to ChEMBL target ids with lists of activity ids
    """
    targ_act_dict = defaultdict(lambda: [])
    for activity in activities:
        target_chembl_id = activity['target_chembl_id']
        activity_id = activity['activity_id']
        targ_act_dict[target_chembl_id].append(activity_id)
    for target_chembl_id in targ_act_dict:
        targ_act_dict[target_chembl_id] = \
            list(set(targ_act_dict[target_chembl_id]))
    return targ_act_dict


def get_protein_targets_only(target_chembl_ids):
    """Given list of ChEMBL target ids, return dict of SINGLE PROTEIN targets

    Parameters
    ----------
    target_chembl_ids : list
        list of chembl_ids as strings
    Returns
    -------
    protein_targets : dict
        dictionary keyed to ChEMBL target ids with lists of activity ids
    """
    protein_targets = {}
    for target_chembl_id in target_chembl_ids:
        target = query_target(target_chembl_id)
        if 'SINGLE PROTEIN' in target['target_type']:
            protein_targets[target_chembl_id] = target
    return protein_targets


def get_evidence(assay):
    """Given an activity, return an INDRA Evidence object.

    Parameters
    ----------
    assay : dict
        an activity from the activities list returned by a query to the API
    Returns
    -------
    ev : :py:class:`Evidence`
        an :py:class:`Evidence` object containing the kinetics of the
    """
    kin = get_kinetics(assay)
    source_id = assay.get('assay_chembl_id')
    if not kin:
        return None
    annotations = {'kinetics': kin}
    chembl_doc_id = str(assay.get('document_chembl_id'))
    pmid = get_pmid(chembl_doc_id)
    ev = Evidence(source_api='chembl', pmid=pmid, source_id=source_id,
                  annotations=annotations)
    return ev


def get_kinetics(assay):
    """Given an activity, return its kinetics values.

    Parameters
    ----------
    assay : dict
        an activity from the activities list returned by a query to the API
    Returns
    -------
    kin : dict
        dictionary of values with units keyed to value types 'IC50', 'EC50',
        'INH', 'Potency', 'Kd'
    """
    try:
        val = float(assay.get('standard_value'))
    except TypeError:
        logger.warning('Invalid assay value: %s' % assay.get('standard_value'))
        return None
    unit = assay.get('standard_units')
    if unit == 'nM':
        unit_sym = 1e-9 * units.mol / units.liter
    elif unit == 'uM':
        unit_sym = 1e-6 * units.mol / units.liter
    else:
        logger.warning('Unhandled unit: %s' % unit)
        return None
    param_type = assay.get('standard_type')
    if param_type not in ['IC50', 'EC50', 'INH', 'Potency', 'Kd']:
        logger.warning('Unhandled parameter type: %s' % param_type)
        logger.info(str(assay))
        return None
    kin = {param_type: val * unit_sym}
    return kin


def get_pmid(doc_id):
    """Get PMID from document_chembl_id

    Parameters
    ----------
    doc_id : str
    Returns
    -------
    pmid : str
    """
    url_pmid = 'https://www.ebi.ac.uk/chembl/api/data/document.json'
    params = {'document_chembl_id': doc_id}
    res = requests.get(url_pmid, params=params)
    js = res.json()
    pmid = str(js['documents'][0]['pubmed_id'])
    return pmid


def get_target_chemblid(target_upid):
    """Get ChEMBL ID from UniProt upid

    Parameters
    ----------
    target_upid : str
    Returns
    -------
    target_chembl_id : str
    """
    url = 'https://www.ebi.ac.uk/chembl/api/data/target.json'
    params = {'target_components__accession': target_upid}
    r = requests.get(url, params=params)
    r.raise_for_status()
    js = r.json()
    target_chemblid = js['targets'][0]['target_chembl_id']
    return target_chemblid


def get_mesh_id(nlm_mesh):
    """Get MESH ID from NLM MESH

    Parameters
    ----------
    nlm_mesh : str
    Returns
    -------
    mesh_id : str
    """
    url_nlm2mesh = 'http://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi'
    params = {'db': 'mesh', 'term': nlm_mesh, 'retmode': 'JSON'}
    r = requests.get(url_nlm2mesh, params=params)
    res = r.json()
    mesh_id = res['esearchresult']['idlist'][0]
    return mesh_id


def get_pcid(mesh_id):
    """Get PC ID from MESH ID

    Parameters
    ----------
    mesh : str
    Returns
    -------
    pcid : str
    """
    url_mesh2pcid = 'http://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi'
    params = {'dbfrom': 'mesh', 'id': mesh_id,
              'db': 'pccompound', 'retmode': 'JSON'}
    r = requests.get(url_mesh2pcid, params=params)
    res = r.json()
    pcid = res['linksets'][0]['linksetdbs'][0]['links'][0]
    return pcid


def get_chembl_id(nlm_mesh):
    """Get ChEMBL ID from NLM MESH

    Parameters
    ----------
    nlm_mesh : str
    Returns
    -------
    chembl_id : str
    """
    mesh_id = get_mesh_id(nlm_mesh)
    pcid = get_pcid(mesh_id)
    url_mesh2pcid = 'https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/' + \
                    'cid/%s/synonyms/JSON' % pcid
    r = requests.get(url_mesh2pcid)
    res = r.json()
    synonyms = res['InformationList']['Information'][0]['Synonym']
    chembl_id = [syn for syn in synonyms
                 if 'CHEMBL' in syn and 'SCHEMBL' not in syn][0]
    return chembl_id
