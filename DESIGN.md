
## Action space

Making a cake in a kitchen maps nicely to a discrete action space: 
 `navigate_to`, `pick_up`, `place`, `pour`, `whisk`, `set_appliance`, `wait`.
represented as skills which could be fed neatly into Claude API as tool schema. 


## Q1. What does the agent need to know?
Full observability, not partial. Exploration is not the variable being studied; partial obs would shift difficulty toward map-building, which obscures the harness.

As an extension, surface only what's decision-relevant: *if the agent didn't know this, would it act differently?* If no, drop it. Walls (BFS handles them), exact coordinates (agent acts on adjacency), world tick `t` (nothing time-critical), and action history beyond the last 3 all get dropped this way.

## Q2. How do we represent state?
The world is the source of truth — a single `World` object that owns all state. Only `step()` mutates it. The renderer and observation builder read; they never write. This is what makes the harness testable without an LLM in the loop.

Modelled as a Pydantic class hierarchy: `Ingredient`, `Container`, `Appliance` inherit from a base `Entity` with a discriminated union on `kind`. Pydantic gives free validation and JSON round-tripping. Relationships are encoded as ID references (`egg.in_id = "bowl_1"`) rather than nested objects, because mutation is the common case and references compose cleanly.

Alternatives I considered and ruled out: **Entity-Component-System** (used in Unity, Unreal, DeepMind's Concordia for LLM-agent worlds — pays off in larger worlds with many entity types; over-engineering for one task), and **predicate-based** representations (STRIPS/PDDL — cleaner for symbolic planners, awkward for the hierarchical "bowl on counter, eggs in bowl" structure I need).

Agent state splits into a *physical* part (position, hands — lives inside `World` because transitions act on it) and a *cognitive* part (a writable scratchpad surfaced in every observation). Intentionally minimal vs richer cognitive architectures (BDI, Park et al.'s memory streams). For a ~30-step task, conversation history plus scratchpad is enough.

## Q3. How do we tell the LLM the state?
Q3 is constrained by Q2 — what can be expressed is bounded by what the world model captures. Within that constraint, the choices are format, voice, and what's static vs dynamic.

**Format:** natural language 

**Voice:** second-person ("You are at the counter...")

## References
(Note I am currently doing my final-year dissertation on agent simulation hence the following research papers were useful when thinking about design).
Yao et al. 2022 — *ReAct*. Park et al. 2023 - *Generative Agents*. Brockman et al. 2016 — *OpenAI Gym*. 

