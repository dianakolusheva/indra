import pickle
import pandas
from indra.statements import Phosphorylation, Agent, Evidence
from indra.preassembler import Preassembler
from indra.preassembler.hierarchy_manager import hierarchies
from indra.preassembler.grounding_mapper import GroundingMapper
from indra.preassembler.grounding_mapper import gm as grounding_map
from indra.preassembler.sitemapper import SiteMapper, default_site_map

def phosphosite_to_indra():
    fname = 'phosphosite_kin_sub_2016.csv'
    df = pandas.DataFrame.from_csv(fname, index_col=None)
    df = df[df['KIN_ORGANISM']=='human']
    dt = df[df['SUB_ORGANISM']=='human']
    stmts = []
    for _, row in df.iterrows():
        enz_name = row['GENE']
        enz_up = row['KIN_ACC_ID']
        sub_name = row['SUB_GENE']
        sub_up = row['SUB_ACC_ID']
        if not enz_name or not sub_name or \
            isinstance(enz_name, float) or isinstance(sub_name, float):
            continue
        enz = Agent(enz_name, db_refs={'UP': enz_up})
        sub = Agent(sub_name, db_refs={'UP': sub_up})
        site = row['SUB_MOD_RSD']
        if site[0] in ('S', 'T', 'Y'):
            residue = site[0]
            position = site[1:]
        else:
            residue = None
            position = None
        ev = Evidence('phosphosite')
        st = Phosphorylation(enz, sub, residue, position, ev)
        stmts.append(st)
    print '%d human-human phosphorylations in Phosphosite' % len(stmts)
    with open('phosphosite_indra.pkl', 'wb') as fh:
        pickle.dump(stmts, fh)
    return stmts

def rasmachine_extract_phos():
    with open('model.pkl', 'rb') as fh:
        model = pickle.load(fh)

    stmts = []
    for pmid, pmid_stmts in model.iteritems():
        for stmt in pmid_stmts:
            if isinstance(stmt, Phosphorylation):
                stmts.append(stmt)
    print '%d phosphorylations in RAS Machine' % len(stmts)

    stmts = [s for s in stmts if s.enz is not None]
    print '%d phosphorylations with enzyme in RAS Machine' % len(stmts)

    stmts_grounded = filter_grounded(stmts)
    print '%d grounded phosphorylations in RAS Machine' % len(stmts_grounded)

    stmts_enzkinase = filter_enzkinase(stmts_grounded)
    print '%d phosphorylations with kinase enzyme in RAS Machine' % len(stmts_enzkinase)

    sm = SiteMapper(default_site_map)
    stmts_valid, _ = sm.map_sites(stmts_enzkinase)
    print '%d valid-sequence phosphorylations in RAS Machine' % len(stmts_valid)

    pa = Preassembler(hierarchies, stmts_valid)
    stmts_unique = pa.combine_duplicates()
    print '%d unique phosphorylations in RAS Machine' % len(stmts_unique)

    stmts_unique = pa.combine_related()
    print '%d top-level phosphorylations in RAS Machine' % len(stmts_unique)

    with open('rasmachine_mapped_unique_phos.pkl', 'wb') as fh:
        pickle.dump(stmts_unique, fh)

    # Filter RAS Machine statements for direct and not hypothesis
    stmts = filter_direct(stmts_unique)
    print '%d direct phosphorylations in RAS Machine' % len(stmts)
    stmts = filter_non_hypothesis(stmts)
    print '%d non-hypothesis phosphorylations in RAS Machine' % len(stmts)

    with open('rasmachine_filtered_phos.pkl', 'wb') as fh:
        pickle.dump(stmts, fh)

    return stmts

def filter_belief(stmts):
    # As a proxy here, we just look for > 1 evidence
    believed_stmts = []
    for stmt in stmts:
        if len(stmt.evidence) > 1:
            believed_stmts.append(stmt)
    return believed_stmts

def filter_direct(stmts):
    direct_stmts = []
    for stmt in stmts:
        if get_is_direct(stmt):
            direct_stmts.append(stmt)
    return direct_stmts

def filter_non_hypothesis(stmts):
    non_hyp_stmts = []
    for stmt in stmts:
        if get_is_not_hypothesis(stmt):
            non_hyp_stmts.append(stmt)
    return non_hyp_stmts

def filter_grounded(stmts):
    gm = GroundingMapper(grounding_map)
    stmts_mapped = gm.map_agents(stmts, do_rename=True)

    stmts_grounded = []
    for stmt in stmts_mapped:
        all_grounded = True
        for agent in stmt.agent_list():
            if agent is not None:
                if set(agent.db_refs.keys()) == set(['TEXT']):
                    all_grounded = False
                    break
        if all_grounded:
            stmts_grounded.append(stmt)
    return stmts_grounded

def filter_enzkinase(stmts):
    kinase_activities = get_kinase_activities()
    stmts_enzkinase = []
    for stmt in stmts:
        is_kinase = False
        for kin in kinase_activities:
            if stmt.enz.entity_matches(kin.agent):
                is_kinase = True
                break
            if kin.agent.refinement_of(stmt.enz, hierarchies):
                is_kinase = True
                break
        if is_kinase:
            stmts_enzkinase.append(stmt)
    return stmts_enzkinase

def compare_overlap(stmts_pred, stmts_ref):
    # Ras Machine statements that are in Phosphosite
    found_stmts = []
    not_found_stmts = []
    for i, stmt_pred in enumerate(stmts_pred):
        found = False
        for stmt_ref in stmts_ref:
            if stmt_pred.matches(stmt_ref) or \
                stmt_ref.refinement_of(stmt_pred, hierarchies):
                    found = True
                    break
        if found:
            found_stmts.append(stmt_pred)
        else:
            not_found_stmts.append(stmt_pred)
    return not_found_stmts, found_stmts


def get_kinase_activities():
    kinase_file = '../../indra/resources/kinases.tsv'
    kinases = []
    with open(kinase_file, 'rt') as fh:
        lines = [l.strip() for l in fh.readlines()]
        for lin in lines:
            up_id, hgnc_name = lin.split('\t')
            agent = Agent(hgnc_name, db_refs={'UP': up_id})
            kinases.append(agent)
    kin_activities = []
    from indra.statements import HasActivity
    for kin in kinases:
        stmt = HasActivity(kin, 'kinase', True)
        kin_activities.append(stmt)
    return kin_activities

def get_is_direct(stmt):
    '''Returns true if there is evidence that the statement is a direct
    interaction. If any of the evidences associated with the statement
    indicates a direct interatcion then we assume the interaction
    is direct. If there is no evidence for the interaction being indirect
    then we default to direct.'''
    any_indirect = False
    for ev in stmt.evidence:
        if ev.epistemics.get('direct') is True:
            return True
        elif ev.epistemics.get('direct') is False:
            # This guarantees that we have seen at least
            # some evidence that the statement is indirect
            any_indirect = True
    if any_indirect:
        return False
    return True

def get_is_not_hypothesis(stmt):
    hyps = [ev.epistemics.get('hypothesis') for ev in stmt.evidence]
    for hyp in hyps:
        if hyp is not True:
            return True
    return False

if __name__ == '__main__':
    use_pkl = False
    if use_pkl:
        rm_file = 'rasmachine_filtered_phos.pkl'
        with open(rm_file, 'rb') as fh:
            rm_stmts = pickle.load(fh)

        ps_file = 'phosphosite_indra.pkl'
        with open(ps_file, 'rb') as fh:
            ps_stmts = pickle.load(fh)
    else:
        print 'Extract phosphorylations from Phosphosite'
        ps_stmts = phosphosite_to_indra()
        print 'Extract phosphorylations from the RAS Machine'
        rm_stmts = rasmachine_extract_phos()

    not_found_stmts, found_stmts = compare_overlap(rm_stmts, ps_stmts)
    print '%d phosphorylations found in Phosphosite' % len(found_stmts)
    print '%d phosphorylations not found in Phosphosite' % len(not_found_stmts)

    rm_stmts = filter_belief(rm_stmts)
    print '%d > 1 evidence phosphorylations in RAS Machine' % len(rm_stmts)

    not_found_stmts, found_stmts = compare_overlap(rm_stmts, ps_stmts)
    print '%d phosphorylations found in Phosphosite' % len(found_stmts)
    print '%d phosphorylations not found in Phosphosite' % len(not_found_stmts)

    with open('not_found.tsv', 'wt') as fh:
        for i, st in enumerate(not_found_stmts):
            for ev in st.evidence:
                if ev.epistemics.get('direct'):
                    fh.write('%d\t%s\t \t%s\t%s\n' % \
                            (i, st, ev.text, ev.pmid))
