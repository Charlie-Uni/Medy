"""Skills (baseline 5.6, M2-11/12): the Registry is the only way to run a Skill. It checks scopes (INV-AUTH-03),
validates the input against the registered schema, records the skill version in the run's version set, runs the
handler under the node policy (timeout, bounded retries only when idempotent) and passes every output through
safety layer 3. Skill modules keep their handlers private; `catalog.default_registry()` wires the delivered ones."""
