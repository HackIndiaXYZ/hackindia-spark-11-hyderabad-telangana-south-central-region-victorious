"""Project Victorious API.

An AI-native Software Engineering Organization: specialized engineering agents
coordinated by an Executive AI over a shared organizational memory, with full
artifact traceability and human approval gates.

Layering (dependencies point inward only):

    api  ->  orchestration  ->  agents  ->  memory  ->  domain
    core ->  (cross-cutting: config, logging, DI, errors, health)

``domain`` is pure: it imports nothing from the layers above it and no third-party
framework. ``tests/test_architecture.py`` enforces this mechanically.
"""

__version__ = "0.1.0"
