from .model_checker import stmt_from_rule
from indra.sources.indra_db_rest.api import get_statements_by_hash


def stmts_from_path(path, model, stmts):
    """Return source Statements corresponding to a path in a model.

    Parameters
    ----------
    path : list[tuple[str, int]]
        A list of tuples where the first element of the tuple is the
        name of a rule, and the second is the associated polarity along
        a path.
    model : pysb.core.Model
        A PySB model which contains the rules along the path.
    stmts : list[indra.statements.Statement]
        A list of INDRA Statements from which the model was assembled.

    Returns
    -------
    path_stmts : list[indra.statements.Statement]
        The Statements from which the rules along the path were obtained.
    """
    path_stmts = []
    for path_rule, sign in path:
        for rule in model.rules:
            if rule.name == path_rule:
                stmt = stmt_from_rule(path_rule, model, stmts)
                assert stmt is not None
                path_stmts.append(stmt)
    return path_stmts


def stmts_from_indranet_path(path, model, signed):
    """Return source Statements corresponding to a path in an IndraNet model.

    Parameters
    ----------
    path : list[tuple[str, int]]
        A list of tuples where the first element of the tuple is the
        name of an agent, and the second is the associated polarity along
        a path.
    model : nx.Digraph or nx.MultiDiGraph
        An IndraNet model flattened into an unsigned DiGraph or signed
        MultiDiGraph.
    signed : bool
        Whether the model and path are signed.

    Returns
    -------
    path_stmts : list[[indra.statements.Statement]]
        A list of lists of INDRA statements explaining the path (each inner
        corresponds to one step in the path because the flattened model can
        have multiple statements per edge).
    """
    steps = []
    for i in range(len(path[:-1])):
        source = path[i]
        target = path[i+1]
        if signed:
            if source[1] == target[1]:
                sign = 0
            else:
                sign = 1
            stmt_data = model[source[0]][target[0]][sign]['statements']
        else:
            stmt_data = model[source[0]][target[0]]['statements']
        hashes = [stmt['stmt_hash'] for stmt in stmt_data]
        stmts = get_statements_by_hash(hashes)
        steps.append(stmts)
    return steps
