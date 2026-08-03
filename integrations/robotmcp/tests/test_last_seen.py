"""Tests off-SAP de la compaction de perceptions identiques consécutives
(``sap_robotmcp._last_seen``), convention #5 du CLAUDE.md."""
from sap_robotmcp._last_seen import LastSeenCompactor


def test_first_call_for_a_session_is_never_marked_unchanged():
    c = LastSeenCompactor()
    assert c.compact("s1", "# screen X") is False


def test_repeating_the_same_value_is_marked_unchanged():
    c = LastSeenCompactor()
    c.compact("s1", "# screen X")
    assert c.compact("s1", "# screen X") is True


def test_a_different_value_is_not_marked_unchanged():
    c = LastSeenCompactor()
    c.compact("s1", "# screen X")
    assert c.compact("s1", "# screen Y") is False


def test_sessions_are_tracked_independently():
    c = LastSeenCompactor()
    c.compact("s1", "# screen X")
    # s2 n'a jamais rien vu -> pas "unchanged" même si la valeur coïncide avec s1.
    assert c.compact("s2", "# screen X") is False


def test_reset_forgets_a_single_session():
    c = LastSeenCompactor()
    c.compact("s1", "# screen X")
    c.compact("s2", "# screen X")
    c.reset("s1")
    assert c.compact("s1", "# screen X") is False   # s1 oubliée -> pas "unchanged"
    assert c.compact("s2", "# screen X") is True     # s2 intacte -> toujours "unchanged"


def test_reset_without_argument_forgets_every_session():
    c = LastSeenCompactor()
    c.compact("s1", "# screen X")
    c.reset()
    assert c.compact("s1", "# screen X") is False


def test_swap_returns_the_previous_value_and_stores_the_new_one():
    c = LastSeenCompactor()
    assert c.swap("s1", "# screen X") is None       # premier appel : rien avant
    assert c.swap("s1", "# screen Y") == "# screen X"
    assert c.swap("s1", "# screen Z") == "# screen Y"


def test_swap_tracks_sessions_independently():
    c = LastSeenCompactor()
    c.swap("s1", "# screen X")
    assert c.swap("s2", "# screen X") is None
