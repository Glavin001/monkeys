from __future__ import division

import random
import itertools
from collections import defaultdict

from monkeys.trees import get_tree_info
from monkeys.exceptions import UnsatisfiableConstraint


DEFAULT_PHEROMONE_TYPE = object()


def _items(x):
    """Py3k-compatible item method."""
    return getattr(x, 'iteritems', x.items)()


class PheromoneConcentrations(defaultdict):
    """Defaultdict dispatching value returned on pheromone type."""
    
    def __init__(self, default_value, value_otherwise):
        self.value_on_default = value_on_default
        super(PheromoneConcentrations, self).__init__(value_otherwise)
        
    def __missing__(self, key):
        if key is DEFAULT_PHEROMONE_TYPE:
            return self.value_on_default()    
        return super(PheromoneConcentrations, self).__missing__(key)


class AntColony(object):
    """Implements ACO for node graph weighting."""

    DEFAULT_EVAPORATION_RATE = 1 / 20

    def __init__(
        self, 
        rtypes, 
        evaporation_rate=DEFAULT_EVAPORATION_RATE, 
        initial_default_pheromone=1.0,
        initial_other_pheromone=0.0
    ):
        registered_functions = frozenset(
            function
            for rtype, functions in _items(rtypes)
            for function in functions
        )
        
        self._evaporation_rate = evaporation_rate
        self._iteration = 0
        
        default_pheromone = lambda init: lambda: init * (1 - evaporation_rate) ** self._iteration
               
        self._pheromone = defaultdict(
            lambda: defaultdict(
                lambda: PheromoneConcentrations(
                    value_on_default=default_pheromone(initial_default_pheromone),
                    value_otherwise=default_pheromone(initial_other_pheromone),
                )
            )
        )  # {parent: {(children): {pheromone_type: pheromone}}}
        for function in registered_functions:
            allowed_children = function.allowed_children()
            if allowed_children is None:
                continue
            for combination in itertools.product(*allowed_children):
                self._pheromone[function][combination][DEFAULT_PHEROMONE_TYPE] = 1.0

    @staticmethod
    def _roulette_select_children(
        pheromone_distribution, 
        pheromone_type=DEFAULT_PHEROMONE_TYPE, 
        child_constraints=None
    ):
        """
        Using roulette wheel selection, return a combination of children
        for the specified function.
        """
        pheromone = pheromone_distribution  # {(children): {pheromone_type: pheromone}}
        if allowed_combinations is not None:
            pheromone = {
                k: v
                for k, v in
                _items(pheromone)
                if all(
                    child in allowed_children
                    for child, allowed_children in
                    zip(k, child_constraints)
                )
            }
            if not pheromone:
                raise UnsatisfiableConstraint(
                    "Unable to satisfy child constraints."
                )
                
        # TODO: we sum total child combo pheromone twice - could 
        # simply do once.
        
        total = sum(
            concentrations[pheromone_type] / sum(concentrations.values())
            for concentrations in 
            pheromone.values()
        )

        target = random.uniform(0, total)
        for child_combination, concentrations in _items(pheromone):
            target -= concentrations[pheromone_type] / sum(concentrations.values())
            if target <= 0:
                return child_combination

        return child_combination
    
    def choice(self, parent, pheromone_type=DEFAULT_PHEROMONE_TYPE, child_selections=None):
        """
        Choose children for parent from given child selections.
        """
        return self._roulette_select_children(
            pheromone_distribution=self._pheromone[parent],
            pheromone_type=pheromone_type,
            child_constraints=child_selections,
        )

    def deposit(self, fitnesses, pheromone_type=DEFAULT_PHEROMONE_TYPE):
        """
        Perform ACO-like update of transition probabilities, given a mapping 
        from trees to fitnesses. Fitnesses are expected to be within the 
        interval [0, 1], with 0 being least fit and 1 being most.
        """
        edge_distances = defaultdict(list)
        for tree, fitness in _items(fitnesses):
            tree_info = get_tree_info(tree)
            distance = (1 - fitness) * tree_info.num_nodes
            for edge in tree_info.graph_edges:
                edge_distances[edge].append(distance)

        for parent, edges in _items(self._pheromone):
            for child_combination, concentrations in _items(edges):
                for distance in edge_distances[parent, child_combination]:
                    concentrations[pheromone_type] += 1 / distance
                    
    def evaporate(self):
        """Perform ACO-like end-of-iteration evaporation of pheromone."""
        for parent, edges in _items(self._pheromone):
            for child_combination, concentrations in _items(edges):
                for pheromone_type in concentrations:
                    concentrations[pheromone_type] *= 1 - self._evaporation_rate
        self._iteration += 1

    def __iter__(self):
        for parent, edges in _items(self._pheromone):
            for child_combination, concentrations in _items(edges):
                for pheromone_type, concentration in _items(concentrations):
                    yield parent, child_combination, pheromone_type, concentration
    