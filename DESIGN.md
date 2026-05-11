
## Action space

Since humanoid's vision is household robots in 2031, I chose to make the agent bake a cake. Thus this defined the action space: 
 `navigate_to`, `pick_up`, `place`, `pour`, `whisk`, `set_appliance`, `wait`.
represented as skills which could be fed neatly into Claude API as tool schema. 


## Q1. What does the agent need to know?

Full observability, not partial. Exploration is not the variable being studied; partial obs would shift difficulty toward map-building, which obscures the harness. 

As an extension though, we can do filtering via *if the agent did not know this, would it act differently?* If no, drop it. (Formal name: **sufficient statistics**.)

## Q2. How do we represent state?

Pydantic class hierarchy. `Ingredient`, `Container`, `Appliance` inherit from `Entity` with a discriminated union on `kind`. Relationships as ID references (`egg.in_id = "bowl_1"`), not nested objects.

Agent state = physical (position, hands — in `World`) + cognitive (scratchpad — surfaced in observation). 

## Q3. How do we tell the LLM the state?

Natural language, light markdown, second-person, four sections: immediate state, kitchen layout, goal + scratchpad, recent actions. No JSON in the prompt. 

Static info (persona, action semantics) → system prompt + tool descriptions, once. Dynamic state → per-turn message.


## References
(Note I am currently doing my final-year dissertation on agent simulation hence the following research papers were useful when thinking about design).
Yao et al. 2022 — *ReAct*. Park et al. 2023 - *Generative Agents*. Brockman et al. 2016 — *OpenAI Gym*. 

