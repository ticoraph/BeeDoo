import pytest

from beedoo.state import State, StateMachine


def test_normal_conversation_cycle():
    machine = StateMachine()
    for state in (State.ECOUTE, State.REFLEXION, State.PAROLE, State.ECOUTE, State.VEILLE):
        machine.go(state)
    assert machine.state == State.VEILLE


def test_forbidden_transition_raises_and_keeps_state():
    machine = StateMachine()
    with pytest.raises(ValueError):
        machine.go(State.REFLEXION)
    assert machine.state == State.VEILLE


def test_any_state_can_return_to_veille():
    for path in ([State.ECOUTE], [State.ECOUTE, State.REFLEXION], [State.ECOUTE, State.REFLEXION, State.PAROLE]):
        machine = StateMachine()
        for state in path:
            machine.go(state)
        machine.go(State.VEILLE)
        assert machine.state == State.VEILLE


def test_listener_called_once_per_change():
    machine = StateMachine()
    seen = []
    machine.on_change(lambda old, new: seen.append((old, new)))
    machine.go(State.ECOUTE)
    machine.go(State.ECOUTE)  # même état : rien
    assert seen == [(State.VEILLE, State.ECOUTE)]
