*This project has been created as part of the 42 curriculum by zhamza.*

# Fly-in

## Description

Fly-in is an object-oriented Python 3.10+ project that simulates the movement of drones through a capacitated graph.

The goal is to move all drones from a start zone to an end zone while respecting zone capacities, connection capacities, blocked zones, priority zones, restricted zones, simultaneous turns, waiting when necessary, and the required simulation output format.

The project also includes a graphical visualization using Python `tkinter`.

The optimizer searches for a valid schedule with the minimum feasible number of turns.

No external graph library such as NetworkX is used.

## Requirements

Python 3.10 or newer is required.

```bash
python3 -m venv .venv
source .venv/bin/activate
make install
```

## Usage

```bash
make run
python3 main.py your_map.map
python3 main.py your_map.map --visual
python3 main.py your_map.map --stats
python3 main.py your_map.map --visual --stats
```

## Development commands

```bash
make test
make lint
make lint-strict
make debug
make clean
```

## Input format

```text
nb_drones: 5

start_hub: hub 0 0 [color=green]
end_hub: goal 10 10 [color=yellow]

hub: roof1 3 4 [zone=restricted color=red]
hub: roof2 6 2 [zone=normal color=blue]
hub: corridorA 4 3 [zone=priority color=green max_drones=2]
hub: tunnelB 7 4 [zone=normal color=red]
hub: obstacleX 5 5 [zone=blocked color=gray]

connection: hub-roof1
connection: hub-corridorA
connection: roof1-roof2
connection: roof2-goal
connection: corridorA-tunnelB [max_link_capacity=2]
connection: tunnelB-goal
```

## Zone types

- `normal`: movement cost 1 turn.
- `priority`: movement cost 1 turn and preferred when equally fast schedules are available.
- `restricted`: entering the zone takes 2 turns.
- `blocked`: inaccessible.

## Capacities

Normal zones have a default capacity of 1 drone. A custom zone capacity is defined with `max_drones`.

Connections have a default capacity of 1 drone. A custom connection capacity is defined with `max_link_capacity`.

The start and end zones have unlimited effective capacity.

## Project structure

```text
main.py        Program entry point and command-line handling.
parser.py      Parses and validates map files.
models.py      Contains the project data models.
graph.py       Stores zones, connections, start, and end zones.
flow.py        Implements the custom minimum-cost flow algorithm.
optimizer.py   Searches for a valid minimum-turn drone schedule.
simulator.py   Validates the schedule and generates simulation turns.
visualizer.py  Draws the graph and animates drone movements.
errors.py      Contains project-specific exceptions.
example.map    Example map used for demonstration.
test_flyin.py  Local development tests.
```

## Parser

`MapParser` validates the drone count, start and end zones, unique zone names, integer coordinates, metadata, zone types, positive capacities, connection endpoints, connection ordering, and duplicate connections.

A syntactically valid graph may still be disconnected. In that case, the parser succeeds but the solver reports that no route exists.

## Routing strategy

The optimizer computes weighted shortest-path information toward the end zone and then builds a time-expanded network.

Movement costs are:

```text
normal      = 1 turn
priority    = 1 turn
restricted  = 2 turns
blocked     = inaccessible
```

The time-expanded network represents drone movement, waiting, zone capacities, connection capacities, and restricted movement over time.

A custom minimum-cost maximum-flow implementation is used. The project does not use external graph libraries.

The optimizer searches for the minimum feasible turn count and converts the resulting integral flow into individual drone plans.

## Simulation rules

All drones start in the start zone.

All movements in the same turn are simultaneous.

A drone may move to an adjacent zone, start moving toward a restricted zone, or wait.

A zone vacated during a turn may be used by another drone arriving during that same turn.

A restricted movement takes two turns. During the intermediate turn, the drone is considered to be in flight on the connection.

Once a drone reaches the end zone, it is considered delivered and is no longer tracked.

The simulation finishes when every drone reaches the end zone.

## Simulation output format

Each simulation turn is represented by one line.

Normal movement:

```text
D<ID>-<zone>
```

Restricted movement while the drone is still in flight:

```text
D<ID>-<connection>
```

Example:

```text
D1-roof1 D2-corridorA
D1-roof2 D2-tunnelB
D1-goal D2-goal
```

Drones that do not move during a turn are omitted. Delivered drones are not printed again.

## Graphical visualization

The project includes a graphical visualizer implemented with Python `tkinter`.

The graphical view displays zones as circles, zone names, start and end zones, blocked zones, graph connections, connection arrows for visual clarity, drone identifiers, drone movement animations, the current turn, and the delivered drone count.

Zone positions use the `x` and `y` coordinates from the map.

The visualizer automatically adjusts the size of zones and drones according to the size of the map. Small maps use larger circles, while larger maps use smaller circles to reduce overlap.

The graph is automatically centered when the window size changes.

Press `SPACE` to advance exactly one turn. Each press animates the corresponding drone movements.

The graphical representation is additional to the mandatory textual simulation output.

## Drone display

Drones are displayed inside their current zone.

When multiple drones are allowed inside the same zone, they are distributed inside the zone circle so they do not completely overlap.

Delivered drones disappear from the graphical simulation.

## Example

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

Possible output:

```text
D1-a
D1-b D2-a
D1-e D2-b
D2-e
```

## Error handling

Invalid maps generate clear errors, including invalid drone count, missing start or end zone, duplicate zones, invalid coordinates, invalid zone type, invalid capacity, unknown connection endpoints, and duplicate connections.

A disconnected but syntactically valid graph is not a parser error.

```text
Error: no path exists between start_hub and end_hub
```

## Bonus / Challenger

The optimizer searches for the minimum feasible turn count.

The Fly-in subject defines the optional Challenger benchmark as **The Impossible Dream**, with 25 drones in 43 turns.

The implementation is designed to support large valid maps, and the graphical visualizer adapts its node and drone sizes for larger graphs.

The exact 43-turn result should only be claimed after testing the official Challenger map successfully.

```bash
python3 main.py the_impossible_dream.map --stats
```

## Complexity

Let `V` be the number of zones, `E` the number of connections, `T` the number of turns, and `D` the number of drones.

The time-expanded network contains approximately `O(TV)` nodes and `O(T(V + E))` edges.

Memory usage is approximately `O(T(V + E))`.

## Resources

Resources used to understand and develop the project include Python 3 documentation, Python typing documentation, `dataclasses`, `heapq`, `tkinter`, PEP 257, Dijkstra's shortest-path algorithm, minimum-cost maximum-flow, time-expanded networks, and the Fly-in 42 subject.

The Fly-in subject is the authoritative source for map syntax, zone behavior, capacities, movement rules, output format, and benchmark requirements.

## AI usage

AI assistance was used to help review the Fly-in subject, discuss the project architecture, identify parser and simulation edge cases, and review visualization ideas.

All generated code and explanations must be read, tested, and understood before peer evaluation.

The student should be able to explain map parsing, graph representation, zone types, capacities, shortest-path logic, time-expanded networks, minimum-cost flow, simultaneous movement, restricted movement, simulation validation, graphical visualization, and project complexity.
