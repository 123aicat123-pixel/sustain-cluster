"""Dependency-free, batch-level NSGA-II minimizer for research controls.

Algorithm: uniform/heuristic initialization, binary crowded tournament,
one-point crossover, per-gene mutation, fast non-dominated sorting, normalized
crowding distance and elitist (mu+lambda) replacement. The optimizer sees
only *surrogate* objectives supplied by its caller, never the simulator future.
All three returned objective values are minimized. Fixed seeded RNG.

This implementation is for online batch assignment, NOT offline optimization
of the entire known workload; number of surrogate evaluations is tracked.
"""
from __future__ import annotations

import math
import random


def dominates(left, right):
    if len(left) != len(right):
        raise ValueError("objectives must have matching dimensions")
    if any(not math.isfinite(float(x)) for x in (*left, *right)):
        raise ValueError("objectives must be finite")
    return all(a <= b for a, b in zip(left, right)) and any(
        a < b for a, b in zip(left, right)
    )


def non_dominated_sort(scores):
    """Return fronts of population indices in NSGA-II Pareto order."""
    n = len(scores)
    dominated = [[] for _ in range(n)]
    count = [0] * n
    for i in range(n):
        for j in range(i + 1, n):
            if dominates(scores[i], scores[j]):
                dominated[i].append(j)
                count[j] += 1
            elif dominates(scores[j], scores[i]):
                dominated[j].append(i)
                count[i] += 1
    front = [i for i in range(n) if count[i] == 0]
    fronts = []
    while front:
        fronts.append(front)
        nxt = []
        for i in front:
            for j in dominated[i]:
                count[j] -= 1
                if count[j] == 0:
                    nxt.append(j)
        front = nxt
    if sum(len(x) for x in fronts) != n:
        raise AssertionError("non-dominated sorting lost an individual")
    return fronts


def crowding(front, scores):
    """Crowding distance indexed by individual (only for the given front)."""
    d = {i: 0.0 for i in front}
    if len(front) <= 2:
        return {i: math.inf for i in front}
    for objective in range(len(scores[0])):
        ordered = sorted(front, key=lambda i: (scores[i][objective], i))
        low = scores[ordered[0]][objective]
        high = scores[ordered[-1]][objective]
        if high == low:
            continue
        d[ordered[0]] = math.inf
        d[ordered[-1]] = math.inf
        for k in range(1, len(ordered) - 1):
            if math.isfinite(d[ordered[k]]):
                d[ordered[k]] += (
                    scores[ordered[k + 1]][objective]
                    - scores[ordered[k - 1]][objective]
                ) / (high - low)
    return d


def environmental_selection(population, scores, size):
    if size < 1 or size > len(population):
        raise ValueError("invalid surviving population size")
    selected = []
    for front in non_dominated_sort(scores):
        if len(selected) + len(front) <= size:
            selected.extend(front)
        else:
            dist = crowding(front, scores)
            selected.extend(
                sorted(front, key=lambda i: (-dist[i], i))[:size - len(selected)]
            )
            break
    return [population[i] for i in selected]


def _knee(population, scores, weights):
    """Pick a documented weighted normalized Pareto-front compromise."""
    indices = non_dominated_sort(scores)[0]
    lows = [min(scores[i][j] for i in indices) for j in range(len(weights))]
    highs = [max(scores[i][j] for i in indices) for j in range(len(weights))]
    def key(i):
        norm = [
            (scores[i][j] - lows[j]) / (highs[j] - lows[j])
            if highs[j] > lows[j] else 0.0 for j in range(len(weights))
        ]
        return (sum(w * x for w, x in zip(weights, norm)), tuple(scores[i]), tuple(population[i]))
    return min(indices, key=key), len(indices)


def nsga2_optimize(choices, evaluate, *, population_size=16,
                   generations=8, mutation_rate=None, rng=None,
                   seeds=(), weights=(0.2, 0.2, 0.6)):
    """Optimize per-task DC-ID chromosome; return (chromosome, metrics).

    `choices`: nonempty list of nonempty candidate DC-ID sequences.
    `seeds`: optional deterministic heuristic chromosomes (same dimensions).
    `evaluate`: pure function returning cost, carbon, tardiness surrogate.
    """
    if not choices or any(not c for c in choices):
        raise ValueError("at least one task and one candidate DC per task required")
    if population_size < 4 or generations < 1:
        raise ValueError("NSGA-II requires population >= 4 and generations >= 1")
    if len(weights) != 3 or any(w < 0 for w in weights) or not sum(weights):
        raise ValueError("three nonnegative compromise weights required")
    n = len(choices)
    rng = rng or random.Random(0)
    if mutation_rate is None:
        mutation_rate = 1.0 / n
    if not 0 <= mutation_rate <= 1:
        raise ValueError("mutation rate must lie in [0,1]")
    valid = [set(c) for c in choices]
    population = []
    for chrom in seeds:
        row = tuple(chrom)
        if len(row) != n or any(g not in valid[i] for i, g in enumerate(row)):
            raise ValueError("invalid seeded chromosome")
        if len(population) < population_size:
            population.append(row)
    while len(population) < population_size:
        population.append(tuple(rng.choice(c) for c in choices))
    cache = {}
    requests = 0
    def fitness(row):
        nonlocal requests
        requests += 1
        if row not in cache:
            value = tuple(float(x) for x in evaluate(row))
            if len(value) != len(weights) or any(not math.isfinite(x) for x in value):
                raise ValueError("surrogate must return three finite objectives")
            cache[row] = value
        return cache[row]

    for _ in range(generations):
        scores = [fitness(row) for row in population]
        fronts = non_dominated_sort(scores)
        ranks = [None] * population_size
        crowd = [0.0] * population_size
        for rank, front in enumerate(fronts):
            distance = crowding(front, scores)
            for i in front:
                ranks[i] = rank
                crowd[i] = distance[i]
        def tournament():
            a, b = rng.randrange(population_size), rng.randrange(population_size)
            def key(i):
                return (ranks[i], -crowd[i], i)
            return population[min((a, b), key=key)]
        offspring = []
        while len(offspring) < population_size:
            first, second = tournament(), tournament()
            if n > 1:
                cut = rng.randrange(1, n)
                child = first[:cut] + second[cut:]
            else:
                child = first
            child = tuple(
                rng.choice(choices[i]) if rng.random() < mutation_rate else gene
                for i, gene in enumerate(child)
            )
            offspring.append(child)
        merged = population + offspring
        merged_scores = [fitness(row) for row in merged]
        population = environmental_selection(merged, merged_scores, population_size)

    final_scores = [fitness(row) for row in population]
    selected, front_size = _knee(population, final_scores, weights)
    # Export only the cached, already-scored final Pareto front. No new
    # objective evaluations, random draws or search-budget changes.
    front_indices = non_dominated_sort(final_scores)[0]
    front_records = [
        {"chromosome": list(population[i]), "surrogate": list(final_scores[i])}
        for i in front_indices
    ]
    return list(population[selected]), {
        "population": population_size, "generations": generations,
        "surrogate_evaluations": len(cache),
        "evaluation_requests": requests,
        "pareto_front_size": front_size,
        "selected_surrogate": list(final_scores[selected]),
        "final_front_records": front_records,
    }
