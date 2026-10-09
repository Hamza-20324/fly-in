*This project has been created as part of the 42 curriculum by zhamza.*

# Fly-in

## Description

Fly-in is an object-oriented Python 3.10+ simulation that routes a fleet of drones
from one start zone to one end zone through a capacitated graph.  The implementation
respects zone types, zone occupancy, connection capacity, simultaneous turns,
restricted two-turn movements, blocked zones, strategic waiting, and the exact
step-by-step terminal output required by the subject.

Correctness is treated independently from optimization.  The routing engine builds a
time-expanded flow network and searches for the smallest horizon that can deliver the
whole fleet.  A min-cost tie-breaker reduces unnecessary waiting and prefers priority
zones when equally fast schedules are available.

No external graph library is used.

## Instructions

Python 3.10 or newer is required.

Create an isolated environment and install development tools:

```bash
python3 -m venv .venv
source .venv/bin/activate
make install
```

Run the provided example:

```bash
make run
```

Run another map:

```bash
make run MAP=your_map.txt
```

Request colored visual state output:

```bash
make run MAP=your_map.txt ARGS="--visual"
```

Print the optimized turn count to stderr while keeping stdout in the required format:

```bash
make run MAP=your_map.txt ARGS="--stats"
```

Development checks:

```bash
make test
make lint
make lint-strict   # optional stronger mypy mode
```

Debug with Python's built-in debugger:

```bash
make debug MAP=your_map.txt
```

## Input format

A map begins with a positive drone count, then zones and bidirectional connections:

```text
nb_drones: 5
start_hub: hub 0 0 [color=green]
end_hub: goal 10 10 [color=yellow]
hub: roof1 3 4 [zone=restricted color=red]
hub: corridorA 4 3 [zone=priority max_drones=2]
connection: hub-roof1
connection: hub-corridorA [max_link_capacity=2]
connection: roof1-goal
connection: corridorA-goal
```

Supported zone types are `normal`, `blocked`, `restricted`, and `priority`.
Regular zone capacity defaults to 1; start and end capacity is unlimited.
Connection capacity defaults to 1.

## Algorithm and implementation strategy

### 1. Strict parser

`MapParser` validates the first drone declaration, unique zone names, integer
coordinates, metadata syntax and values, zone types, positive capacities, one start,
one end, connection ordering, and duplicate bidirectional connections.  Parse errors
include their line and cause.  A syntactically valid but disconnected map is reported
separately as an unsolvable graph.

### 2. Weighted lower bound

A custom Dijkstra pass computes the shortest possible travel time to the end.  Entering
normal/priority zones costs one turn, entering restricted zones costs two, and blocked
zones cannot be entered.  This supplies the lower bound for the schedule search.

### 3. Time-expanded min-cost flow

For a candidate horizon `T`, each usable zone is copied at every integer time from 0 to
T.  Every zone layer is split into an input/output pair so `max_drones` is represented
as a node capacity.  Start and end use the fleet size as their effective capacity.

Waiting advances one layer.  A normal or priority movement advances one turn.  A
movement into a restricted zone advances two turns, representing the mandatory turn in
flight.  Connection edges carry `max_link_capacity`.  A custom successive-shortest-path
min-cost max-flow implementation sends all drones through this temporal network.

The optimizer first finds a feasible upper horizon and then binary-searches the minimum
feasible horizon.  Waiting has a higher tie-break cost and entering a priority zone has
a lower one, so equal-turn solutions prefer productive movement and priority zones.

### 4. Integral flow decomposition

All capacities are integers, therefore the computed flow is integral.  It is decomposed
into one plan per drone.  Restricted moves generate a connection output on their first
turn and the destination-zone output on the following turn.

### 5. Independent validation

Before any result is printed, `Simulator` validates every drone route again: adjacency,
blocked zones, movement durations, delivery termination, zone occupancy at every turn,
and shared connection use.  This second pass is intentionally separate from the
optimizer so scheduling bugs fail loudly instead of producing invalid output.

### Complexity

Let `V` be zones, `E` connections, `T` the final turn count, and `D` drones.  The
expanded network has `O(TV)` nodes and `O(T(V + E))` edges.  The min-cost flow sends at
most `D` augmentations in the typical unit-bottleneck case; each shortest residual path
uses a heap.  Memory is `O(T(V + E))`.  Paths/schedules are computed once for a horizon
and reused for output; drones are not independently re-running Dijkstra.

## Movement semantics

All movements in one turn are simultaneous.  A zone vacated during a turn can be used
by another arrival in that same turn.  A restricted move occupies the connection during
its intermediate turn and must arrive on the next turn; it cannot wait on the
connection.  Delivered drones disappear from future simulation state.

## Visual representation

`--visual` renders every zone after each turn and lists drones currently in transit.
Known color names use ANSI terminal colors; other valid single-word color values are
shown with emphasized text.  This view is deliberately optional so normal stdout can
remain exactly compatible with the required simulation format.

## Example input and expected output

Input:

```text
nb_drones: 2
start_hub: s 0 0
hub: a 1 0
hub: b 2 0
end_hub: e 3 0
connection: s-a
connection: a-b
connection: b-e
```

One optimal output is:

```text
D1-a
D1-b D2-a
D1-e D2-b
D2-e
```

Each line is one turn.  Waiting drones are omitted.  A drone is no longer tracked after
it reaches `end_hub`.

## Bonus / Challenger

The optimizer is designed to search for the minimum feasible turn count and therefore
also targets the optional Challenger objective.  The subject's official bonus is to
solve **The Impossible Dream** with 25 drones in **43 turns**. The repository includes
`impossible_dream.map`, and the test suite verifies that the general optimizer reaches
the required 43-turn optimum. `challenger_synthetic.map` is kept only as a small
regression map for the 19 + 24 throughput formula.

The synthetic map is **not** the official Challenger map.  The official subject map was
not bundled into this repository; when it is available, run it with the same command
and verify the reported turn count:

```bash
make run MAP=the_impossible_dream.map ARGS="--stats"
```

## Resources

Classic references used for the concepts implemented here:

- Python 3 documentation: data classes, `heapq`, typing, exceptions, context managers.
- PEP 257 for docstring conventions.
- Dijkstra's shortest-path algorithm.
- Time-expanded networks and minimum-cost maximum-flow as standard graph-optimization
  techniques.
- The Fly-in v2.0 42 subject is the authoritative source for map syntax, movement rules,
  capacities, output format, and benchmark targets.

### AI usage

AI assistance was used to help review the Fly-in subject, enumerate parser and movement
edge cases, discuss architecture, and review/test implementation ideas.  The generated
code and explanations must still be read, tested, and understood by the student before
peer evaluation.  In particular, the student should be able to explain the parser,
time-expanded network, flow algorithm, simultaneous-capacity rules, restricted movement,
and complexity without relying on AI during the defense.
# fly-in
# fly-in
