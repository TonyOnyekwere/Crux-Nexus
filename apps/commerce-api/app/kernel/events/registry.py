from app.kernel.events.types import DomainEvent

REGISTERED_EVENTS: frozenset[str] = frozenset(event.value for event in DomainEvent)


def is_registered_event(event_type: str) -> bool:
    return event_type in REGISTERED_EVENTS


def assert_registered_event(event_type: str) -> None:
    if not is_registered_event(event_type):
        raise ValueError(f"Unregistered event type: {event_type}")
