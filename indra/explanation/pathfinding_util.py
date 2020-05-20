import logging
from copy import deepcopy

import networkx as nx

logger = logging.getLogger(__name__)


def signed_edges_to_signed_nodes(graph, prune_nodes=True,
                                 edge_signs={'pos': 0, 'neg': 1},
                                 copy_edge_data=False):
    """Convert a graph with signed edges to a graph with signed nodes.

    Each pair of nodes linked by an edge in an input graph are represented
    as four nodes and two edges in the new graph. For example, an edge (a,
    b, 0), where a and b are nodes and 0 is a sign of an edge (positive),
    will be represented as edges ((a, 0), (b, 0)) and ((a, 1), (b, 1)),
    where (a, 0), (a, 1), (b, 0), (b, 1) are signed nodes. An edge (a, b,
    1) with sign 1 (negative) will be represented as edges ((a, 0), (b,
    1)) and ((a, 1), (b, 0)).

    Parameters
    ----------
    graph : networkx.MultiDiGraph
        Graph with signed edges to convert. Can have multiple edges between
        a pair of nodes.
    prune_nodes : Optional[bool]
        If True, iteratively prunes negative (with sign 1) nodes without
        predecessors.
    edge_signs : dict
        A dictionary representing the signing policy of incoming graph. The
        dictionary should have strings 'pos' and 'neg' as keys and integers
        as values.
    copy_edge_data : bool|set(keys)
        Option for copying edge data as well from graph. If False (default),
        no edge data is copied (except sign). If True, all edge data is
        copied. If a set of keys is provided, only the keys appearing in the
        set will be copied, assuming the key is part of a nested dictionary.

    Returns
    -------
    signed_nodes_graph : networkx.DiGraph
    """
    signed_nodes_graph = nx.DiGraph()
    nodes = []
    for node, node_data in graph.nodes(data=True):
        nodes.append(((node, 0), node_data))
        nodes.append(((node, 1), node_data))
    signed_nodes_graph.add_nodes_from(nodes)
    edges = []
    for u, v, edge_data in graph.edges(data=True):
        copy_dict = deepcopy(edge_data)
        edge_sign = copy_dict.pop('sign', None)
        if edge_sign is None:
            continue
        edge_dict = copy_dict if copy_edge_data == True else \
            ({k: v for k, v in copy_dict.items() if k in copy_edge_data} if
             isinstance(copy_edge_data, set) else {})
        if edge_sign == edge_signs['pos']:
            edges.append(((u, 0), (v, 0), edge_dict))
            edges.append(((u, 1), (v, 1), edge_dict))
        elif edge_sign == edge_signs['neg']:
            edges.append(((u, 0), (v, 1), edge_dict))
            edges.append(((u, 1), (v, 0), edge_dict))
    signed_nodes_graph.add_edges_from(edges)
    if prune_nodes:
        signed_nodes_graph = prune_signed_nodes(signed_nodes_graph)
    return signed_nodes_graph


def prune_signed_nodes(graph):
    """Prune nodes with sign (1) if they do not have predecessors."""
    nodes_to_prune = [node for node, in_deg
                      in graph.in_degree()
                      if in_deg == 0 and node[1] == 1]
    while nodes_to_prune:
        graph.remove_nodes_from(nodes_to_prune)
        # Make a list of nodes whose in degree is now 0
        nodes_to_prune = [node for node, in_deg
                          in graph.in_degree()
                          if in_deg == 0 and node[1] == 1]
    return graph


def path_sign_to_signed_nodes(source, target, edge_sign):
    """Translates a signed edge or path to valid signed nodes

    Pairs with a negative source node are filtered out.

    Paramters
    ---------
    source : str|int
        The source node
    target : str|int
        The target node
    edge_sign : int
        The sign of the edge

    Returns
    -------
    sign_tuple : (a, sign), (b, sign)
        Tuple of tuples of the valid combination of signed nodes
    """
    # Sign definitions: + == 0, - == 1
    # + path -> (a+, b+)
    # - path -> (a+, b-)
    # (a-, b-) and (a-, b+) are also technically valid but not in this context
    try:
        if int(edge_sign) == 0:
            return (source, 0), (target, 0)
        else:
            return (source, 1), (target, 0)
    except ValueError:
        logger.warning('Invalid sign %s when translating edge sign to int'
                       % edge_sign)
        return (None, None), (None, None)


def signed_nodes_to_signed_edge(source, target):
    """Create the triple (node, node, sign) from a pair of signed nodes

    Assuming source, target forms an edge of signed nodes:
    edge = (a, sign), (b, sign), return the corresponding signed edge triple
    """
    # Sign definitions: + == 0, - == 1
    # + edge/path -> (a+, b+) and (a-, b-)
    # - edge/path -> (a-, b+) and (a+, b-)
    source_name, source_sign = source
    target_name, target_sign = target
    try:
        if int(source_sign) == int(target_sign):
            return source_name, target_name, 0
        else:
            return source_name, target_name, 1
    except ValueError:
        logger.warning('Error translating signed nodes to signed edge using '
                       '(%s, %s)' % (source, target))
        return None, None, None
