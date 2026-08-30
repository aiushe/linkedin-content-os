from types import SimpleNamespace

from agent.review import STALE_REVIEW_MESSAGE, resume_if_paused


class EndedGraph:
    def __init__(self):
        self.invocations: list[tuple[object, dict]] = []

    def get_state(self, run_config):
        return SimpleNamespace(next=())

    def invoke(self, command, *, config):
        self.invocations.append((command, config))


def test_resume_on_non_interrupted_thread_is_reported_without_invoking_graph():
    graph = EndedGraph()
    run_config = {"configurable": {"thread_id": "ended"}}

    message = resume_if_paused(graph, run_config, command="approve")

    assert message == STALE_REVIEW_MESSAGE
    assert graph.invocations == []
