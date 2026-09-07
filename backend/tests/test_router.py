import pytest

from app.routing.router import route_representation

# Line-for-line port of web/src/learning/routing/representationRouter.test.ts's
# positive-example assertions - the strongest available parity check short of
# shelling out to node, since it exercises the exact same input/output pairs
# the TS suite already locks in.
POSITIVE_EXAMPLES = {
    "process": [
        "The client sends SYN. Then the server responds with SYN-ACK. Finally the client sends ACK.",
        "First collect the sample. Next heat it gently. Finally record the result.",
        "1. Open the valve\n2. Start the pump\n3. Close the valve",
        "The process begins with intake, followed by validation, followed by storage.",
        "Request → validation → processing → response",
    ],
    "comparison": [
        "A direct-mapped cache allows one possible location, whereas a four-way set-associative cache allows four.",
        "Unlike RAM, storage retains information without power.",
        "The similarities and differences between TCP and UDP determine which protocol fits.",
        "A fiber connection is faster than a copper connection.",
        "Both mitosis and meiosis divide cells, but they produce different outcomes.",
    ],
    "causal": [
        "Smoking causes damage to lung tissue, which leads to reduced lung function.",
        "Because demand increased while supply remained fixed, prices rose.",
        "Insulin causes cells to increase glucose uptake, which leads to lower blood glucose.",
        "Heavy rain blocked the drains; therefore the road flooded.",
        "The mutation results in less protein and consequently the pathway slows.",
    ],
    "concept_map": [
        "Photosynthesis involves chlorophyll, sunlight, carbon dioxide, water, glucose, and oxygen, which are related through several biological mechanisms.",
        "Attention is associated with working memory and connected to learning.",
        "The API depends on authentication, interacts with session storage, and is linked to authorization.",
        "Ecology connects populations, communities, ecosystems, and climate, which are related through energy flows.",
        "Language is connected to cognition and associated with culture.",
    ],
    "hierarchy": [
        "Computer memory consists of registers, cache, main memory, and secondary storage.",
        "There are three main types of cache misses: compulsory, capacity, and conflict.",
        "The nervous system is composed of the brain, spinal cord, and peripheral nerves.",
        "The platform includes accounts, projects, settings, and reports.",
        "Animals are divided into vertebrates, invertebrates, and other major groups.",
    ],
    "quantitative": [
        "Average memory access time = hit time + miss rate × miss penalty.",
        "Velocity is distance divided by time.",
        "Force = mass × acceleration.",
        "The ratio of successful requests to total requests determines reliability.",
        "Latency rose from 12 ms to 18 ms, an increase of 50%.",
    ],
    "plain_text": [
        "Cache memory is a small, fast memory located close to the processor.",
        "The hippocampus is a structure located in the medial temporal lobe.",
        "A compiler translates source code for a computer.",
        "Coral reefs support a wide variety of marine life.",
        "The library is quiet during the afternoon.",
    ],
}


@pytest.mark.parametrize(
    "expected_type,text",
    [(expected, text) for expected, texts in POSITIVE_EXAMPLES.items() for text in texts],
)
def test_routes_to_expected_type(expected_type, text):
    result = route_representation(text)
    assert result.type == expected_type
    assert 0 <= result.confidence <= 1
    assert result.reasons
    for score in result.scores.values():
        assert 0 <= score <= 1


@pytest.mark.parametrize(
    "marker_type,text",
    [
        ("process", "First principles are useful in physics."),
        ("comparison", "The heading contains the word versus."),
        ("causal", "The glossary defines the term because."),
        ("concept_map", "The cable is connected to port A."),
        ("hierarchy", "The guide includes a short introduction."),
        ("quantitative", "The well-known state-of-the-art cache is fast."),
    ],
)
def test_isolated_marker_does_not_win(marker_type, text):
    assert route_representation(text).type != marker_type


def test_chooses_process_for_procedural_comparison_while_retaining_comparison():
    result = route_representation(
        "Unlike main memory, the cache first checks whether the requested block is present and then returns the data."
    )
    assert result.type == "process"
    assert result.scores["process"] > result.scores["comparison"] > 0


def test_chooses_causal_for_cause_followed_by_one_transition():
    result = route_representation("Because a cache miss occurs, the processor then accesses main memory.")
    assert result.type == "causal"
    assert result.scores["causal"] > result.scores["process"] > 0


def test_chooses_hierarchy_for_categorized_quantities_while_retaining_quantitative():
    result = route_representation("There are three types of storage: cache at 2 ms, memory at 20 ms, and disk at 8 ms.")
    assert result.type == "hierarchy"
    assert result.scores["hierarchy"] > result.scores["quantitative"] > 0


def test_keeps_every_competing_score_in_the_result():
    result = route_representation("First compare A versus B, then choose one because it is faster.")
    assert result.scores["process"] > 0
    assert result.scores["comparison"] > 0
    assert result.scores["causal"] > 0
    assert len(result.scores) == 7


def test_uses_plain_text_for_empty_input():
    assert route_representation("").type == "plain_text"


@pytest.mark.parametrize("text", POSITIVE_EXAMPLES["plain_text"])
def test_returns_identical_output_every_time(text):
    assert route_representation(text) == route_representation(text)
