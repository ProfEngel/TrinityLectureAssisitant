from brain import TrinityBrain


def test_skill_detection_errors_are_non_fatal():
    brain = TrinityBrain.__new__(TrinityBrain)

    class BrokenSkill:
        __name__ = "broken_skill"

        @staticmethod
        def can_handle(_query):
            raise PermissionError("blocked")

    assert brain._skill_can_handle(BrokenSkill, "Hallo Trinity") is False


def test_context_skill_detection_errors_are_non_fatal():
    brain = TrinityBrain.__new__(TrinityBrain)

    class BrokenContextSkill:
        __name__ = "broken_context_skill"

        @staticmethod
        def can_handle(_query):
            return False

        @staticmethod
        def can_handle_with_context(_query, _context):
            raise PermissionError("blocked")

    assert brain._skill_can_handle(BrokenContextSkill, "Hallo Trinity", {}) is False
