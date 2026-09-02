import type { RepresentationType } from "../representationTypes"

export type EducationalSubject = "computer_science" | "biology" | "physics" | "mathematics" | "economics" | "history" | "psychology"
export type PassageStyle = "textbook" | "lecture_note" | "highlight" | "paragraph" | "list" | "equation" | "definition"

export type RouterExample = {
  id: string
  expected: RepresentationType
  text: string
  subject: EducationalSubject
  style: PassageStyle
  ambiguous?: boolean
  acceptableTypes?: RepresentationType[]
  ambiguityNote?: string
}

type Row = [text: string, subject: EducationalSubject, style: PassageStyle]

const labeled = (expected: RepresentationType, rows: Row[]): RouterExample[] => rows.map(([text, subject, style], index) => ({
  id: `${expected}-${String(index + 1).padStart(2, "0")}`,
  expected,
  text,
  subject,
  style
}))

const nonAmbiguousExamples: RouterExample[] = [
  ...labeled("process", [
    ["First the operating system loads the program into memory. Next it initializes the process, and finally it transfers control to the entry point.", "computer_science", "textbook"],
    ["1. Copy the DNA segment.\n2. Separate the strands.\n3. Extend each strand with complementary nucleotides.", "biology", "list"],
    ["A star forms when a cloud collapses. After the core heats, fusion begins; afterward radiation pressure stabilizes the star.", "physics", "paragraph"],
    ["Differentiate the function, substitute the boundary value, then solve for the integration constant.", "mathematics", "lecture_note"],
    ["Households first reduce discretionary spending. Firms then cut production, and finally unemployment rises.", "economics", "paragraph"],
    ["The bill passed the lower chamber → moved to the senate → received executive approval.", "history", "highlight"],
    ["Encoding is followed by storage, which is followed by retrieval when the memory is needed.", "psychology", "definition"],
    ["Before the CPU executes an instruction, it fetches and decodes it. Once decoding is complete, execution begins.", "computer_science", "textbook"],
    ["Step 1: establish a baseline\nStep 2: apply the treatment\nStep 3: measure the response", "biology", "list"],
    ["The process begins with observation and ends after the hypothesis has been tested against evidence.", "physics", "lecture_note"],
    ["Start with the recurrence relation. Subsequently expand two terms, collect like factors, and report the closed form.", "mathematics", "lecture_note"],
    ["During mitosis, chromosomes condense, align at the equator, separate toward opposite poles, and the cell divides.", "biology", "textbook"],
    ["An action potential rises as sodium channels open. It peaks, repolarizes as potassium exits, and returns to resting potential.", "biology", "paragraph"],
    ["To train the model: shuffle the observations; divide them into batches; update the parameters for each batch; repeat until convergence.", "computer_science", "lecture_note"],
    ["The historian gathers primary sources, checks their provenance, places them in context, and constructs an interpretation.", "history", "textbook"],
    ["Registration, sensory storage, short-term maintenance, and long-term consolidation describe the path of remembered information.", "psychology", "highlight"]
  ]),
  ...labeled("comparison", [
    ["A direct-mapped cache permits one location per block, whereas a four-way cache permits four possible locations.", "computer_science", "textbook"],
    ["Unlike prokaryotic cells, eukaryotic cells enclose their DNA inside a nucleus.", "biology", "highlight"],
    ["Mass is invariant, while weight changes with the local gravitational field.", "physics", "definition"],
    ["Both permutations and combinations count selections, but only permutations treat order as significant.", "mathematics", "textbook"],
    ["Compared with a monopoly, perfect competition has more sellers and less pricing power.", "economics", "paragraph"],
    ["The northern colonies developed around commerce; the southern colonies relied more heavily on plantation agriculture.", "history", "textbook"],
    ["Working memory has lower capacity than long-term memory but provides faster access to active information.", "psychology", "paragraph"],
    ["TCP emphasizes reliable ordered delivery. UDP favors low overhead and tolerates missing packets.", "computer_science", "lecture_note"],
    ["Mitosis: two genetically similar cells. Meiosis: four genetically varied cells.", "biology", "lecture_note"],
    ["Series circuits share current across components; parallel circuits instead share voltage across branches.", "physics", "textbook"],
    ["The median resists extreme values better than the mean.", "mathematics", "highlight"],
    ["Expansionary fiscal policy increases public spending, in contrast to contractionary policy, which reduces it.", "economics", "textbook"],
    ["Classical conditioning links two stimuli, while operant conditioning links behavior with consequences.", "psychology", "definition"],
    ["Primary sources provide direct contemporary evidence. Secondary sources interpret that evidence later.", "history", "lecture_note"],
    ["Binary search needs sorted input and grows logarithmically; linear search accepts unsorted input and grows linearly.", "computer_science", "paragraph"],
    ["Similarities include membrane-bound organelles and DNA; differences include cell walls, chloroplasts, and vacuole size.", "biology", "lecture_note"]
  ]),
  ...labeled("causal", [
    ["A buffer overflow overwrites adjacent memory, causing the program to crash or transfer control unexpectedly.", "computer_science", "textbook"],
    ["Smoking damages lung tissue, which leads to reduced lung function.", "biology", "paragraph"],
    ["Because the net force is nonzero, the object accelerates in the direction of that force.", "physics", "textbook"],
    ["Multiplying both sides by a negative number reverses the inequality sign.", "mathematics", "lecture_note"],
    ["Demand increased while supply stayed fixed, so the market price rose.", "economics", "paragraph"],
    ["Crop failures intensified food shortages; consequently, bread prices climbed and public unrest spread.", "history", "textbook"],
    ["Repeated retrieval strengthens access to a memory, making later recall more likely.", "psychology", "paragraph"],
    ["Packet loss triggers retransmission and therefore increases latency.", "computer_science", "highlight"],
    ["The antibiotic kills susceptible bacteria. Resistant individuals survive and leave more offspring, producing a resistant population.", "biology", "paragraph"],
    ["Heating the gas raises molecular speed. The more frequent wall collisions create greater pressure.", "physics", "textbook"],
    ["An increase in the interest rate discourages borrowing and results in lower investment spending.", "economics", "textbook"],
    ["The printing press lowered the cost of reproducing texts, enabling ideas to circulate more widely.", "history", "paragraph"],
    ["Sleep deprivation impairs attention because neural systems have insufficient time to recover.", "psychology", "textbook"],
    ["Removing the base case makes the recursive function call itself indefinitely.", "computer_science", "highlight"],
    ["Water enters the guard cells, so they swell and the stomatal pore opens.", "biology", "lecture_note"],
    ["A larger sample reduces sampling variability; as a result, the estimate is usually more precise.", "mathematics", "textbook"]
  ]),
  ...labeled("concept_map", [
    ["An operating system coordinates processes, memory, files, and devices; scheduling connects process demand with processor time.", "computer_science", "paragraph"],
    ["Photosynthesis involves chlorophyll, sunlight, carbon dioxide, water, glucose, and oxygen, all linked through energy conversion.", "biology", "textbook"],
    ["Electric fields interact with charges, while voltage relates potential energy to charge and connects to current through resistance.", "physics", "paragraph"],
    ["A derivative links slope, rate of change, tangent lines, and local approximation.", "mathematics", "definition"],
    ["Inflation is associated with purchasing power, interest rates, wages, and expectations, and each relationship influences the others.", "economics", "textbook"],
    ["Industrialization connected urbanization, factory labor, transportation, capital, and changing family life.", "history", "paragraph"],
    ["Attention interacts with perception and working memory, while executive control coordinates these systems around a goal.", "psychology", "textbook"],
    ["Authentication depends on identity, credentials, sessions, and authorization; these concepts are related but perform distinct roles.", "computer_science", "lecture_note"],
    ["The immune response links antigens to antibodies, B cells, T cells, and memory cells through signaling pathways.", "biology", "textbook"],
    ["Momentum connects mass and velocity and is related to impulse through change over time.", "physics", "definition"],
    ["Functions, limits, continuity, and derivatives form an interconnected foundation for calculus.", "mathematics", "lecture_note"],
    ["Markets bring together buyers, sellers, prices, information, and incentives.", "economics", "definition"],
    ["The Cold War involved ideology, nuclear deterrence, proxy conflicts, alliances, and economic competition.", "history", "textbook"],
    ["A schema organizes concepts and is associated with expectations, memory retrieval, and interpretation.", "psychology", "definition"],
    ["In a graph, vertices connect through edges; paths, cycles, and components describe relationships across the network.", "computer_science", "textbook"],
    ["Homeostasis emerges from receptors, control centers, effectors, feedback, and changing internal conditions working together.", "biology", "paragraph"]
  ]),
  ...labeled("hierarchy", [
    ["Computer memory consists of registers, cache, main memory, and secondary storage.", "computer_science", "textbook"],
    ["Animals are divided into vertebrates and invertebrates; vertebrates include mammals, birds, reptiles, amphibians, and fish.", "biology", "textbook"],
    ["The electromagnetic spectrum contains radio waves, microwaves, infrared, visible light, ultraviolet, X-rays, and gamma rays.", "physics", "textbook"],
    ["Numbers can be classified as natural, integer, rational, irrational, real, or complex.", "mathematics", "lecture_note"],
    ["There are three broad market structures: competitive markets, oligopolies, and monopolies.", "economics", "textbook"],
    ["The estate system placed clergy in the First Estate, nobility in the Second, and commoners in the Third.", "history", "paragraph"],
    ["Long-term memory has two main divisions: explicit memory and implicit memory.", "psychology", "definition"],
    ["Network protocols occupy layers: application, transport, internet, and link.", "computer_science", "lecture_note"],
    ["Cellular organization:\n- tissue\n  - epithelial\n  - connective\n- organ\n- organ system", "biology", "list"],
    ["Matter is composed of atoms; atoms contain a nucleus and electrons; the nucleus contains protons and neutrons.", "physics", "textbook"],
    ["Quadrilaterals include parallelograms, trapezoids, and kites. Parallelograms include rectangles, rhombi, and squares.", "mathematics", "paragraph"],
    ["Government spending includes defense, infrastructure, education, health, and transfers.", "economics", "lecture_note"],
    ["Sources:\n- primary\n- secondary\n- tertiary", "history", "list"],
    ["Motivation theories fall into biological, behavioral, cognitive, and humanistic categories.", "psychology", "lecture_note"],
    ["A compiler pipeline has major components: lexer, parser, semantic analyzer, optimizer, and code generator.", "computer_science", "definition"],
    ["The nervous system comprises the central and peripheral systems, with the peripheral system branching into somatic and autonomic divisions.", "biology", "textbook"]
  ]),
  ...labeled("quantitative", [
    ["Average memory access time = hit time + miss rate × miss penalty.", "computer_science", "equation"],
    ["Population growth rate equals births minus deaths, divided by the starting population.", "biology", "definition"],
    ["Velocity is distance divided by time.", "physics", "definition"],
    ["For a circle, A = πr², so doubling r multiplies the area by four.", "mathematics", "equation"],
    ["Real interest rate ≈ nominal interest rate − inflation rate.", "economics", "equation"],
    ["The urban population grew from 2 million to 5 million, a 150% increase.", "history", "paragraph"],
    ["A z-score is the observation minus the mean, divided by the standard deviation.", "psychology", "definition"],
    ["The algorithm performs n(n − 1) / 2 comparisons.", "computer_science", "equation"],
    ["Heart rate was 72 beats per minute before exercise and 128 beats per minute afterward.", "biology", "paragraph"],
    ["Kinetic energy equals one half times mass times velocity squared.", "physics", "definition"],
    ["The slope between (2, 3) and (6, 11) is (11 − 3) / (6 − 2) = 2.", "mathematics", "equation"],
    ["If price rises by 10% and quantity demanded falls by 20%, elasticity has magnitude 2.", "economics", "paragraph"],
    ["The army expanded from 40,000 soldiers in 1800 to 75,000 in 1810.", "history", "paragraph"],
    ["Participants recalled 18 of 24 words, giving an accuracy of 75%.", "psychology", "paragraph"],
    ["Throughput is completed requests per second; 600 requests over 20 seconds gives 30 requests per second.", "computer_science", "definition"],
    ["The probability of two independent events is P(A and B) = P(A) × P(B).", "mathematics", "equation"]
  ]),
  ...labeled("plain_text", [
    ["Cache memory is a small, fast memory located close to the processor.", "computer_science", "definition"],
    ["The hippocampus is a curved structure in the medial temporal lobe.", "psychology", "definition"],
    ["Chlorophyll is the green pigment found in plant chloroplasts.", "biology", "definition"],
    ["Inertia describes an object's resistance to changes in motion.", "physics", "definition"],
    ["A prime number has exactly two positive divisors.", "mathematics", "definition"],
    ["Scarcity means that available resources cannot satisfy every possible want.", "economics", "definition"],
    ["The Renaissance was a period of cultural activity in Europe.", "history", "definition"],
    ["A pointer stores the address of another location in memory.", "computer_science", "textbook"],
    ["Mitochondria have an inner membrane folded into structures called cristae.", "biology", "textbook"],
    ["Light behaves as electromagnetic radiation.", "physics", "highlight"],
    ["An axiom is a statement accepted without proof.", "mathematics", "definition"],
    ["Opportunity cost is the value of the best alternative forgone.", "economics", "definition"],
    ["The treaty was signed in Paris in 1783.", "history", "highlight"],
    ["The amygdala participates in emotional processing.", "psychology", "highlight"],
    ["Python uses indentation to delimit blocks of code.", "computer_science", "textbook"],
    ["Most neurons have a cell body, dendrites, and an axon.", "psychology", "textbook"]
  ])
]

const ambiguous = (
  expected: RepresentationType,
  index: number,
  acceptableTypes: RepresentationType[],
  ambiguityNote: string,
  row: Row
): RouterExample => ({
  id: `ambiguous-${expected}-${index}`,
  expected,
  acceptableTypes,
  ambiguityNote,
  ambiguous: true,
  text: row[0],
  subject: row[1],
  style: row[2]
})

const ambiguousExamples: RouterExample[] = [
  ambiguous("process", 1, ["process", "causal"], "A causal chain is also narrated as a sequence.", ["A cache miss occurs, so the processor accesses memory, then waits for the block before resuming execution.", "computer_science", "paragraph"]),
  ambiguous("process", 2, ["process", "comparison"], "The contrast is expressed through ordered behavior.", ["Unlike main memory, cache first checks its tags and then returns the matching block.", "computer_science", "paragraph"]),
  ambiguous("comparison", 1, ["comparison", "quantitative"], "The main point is a numeric comparison.", ["Method A solves 80% of cases in 2 seconds, whereas method B solves 95% in 5 seconds.", "mathematics", "paragraph"]),
  ambiguous("comparison", 2, ["comparison", "hierarchy"], "Two categories are contrasted after being named.", ["Memory has volatile and nonvolatile forms: volatile memory loses data, while nonvolatile memory retains it.", "computer_science", "textbook"]),
  ambiguous("causal", 1, ["causal", "concept_map"], "A concept relationship is explicitly causal.", ["Stress is connected to sleep because elevated arousal delays sleep onset.", "psychology", "paragraph"]),
  ambiguous("causal", 2, ["causal", "quantitative"], "An equation and its causal interpretation are equally useful.", ["Since F = ma, increasing force while mass stays fixed produces greater acceleration.", "physics", "textbook"]),
  ambiguous("concept_map", 1, ["concept_map", "hierarchy"], "A system of parts also forms a relationship network.", ["An ecosystem contains producers, consumers, and decomposers linked by flows of matter and energy.", "biology", "textbook"]),
  ambiguous("concept_map", 2, ["concept_map", "plain_text"], "This short definition states one meaningful relation but may not warrant a map.", ["Syntax is related to sentence structure.", "psychology", "definition"]),
  ambiguous("hierarchy", 1, ["hierarchy", "quantitative"], "Categories are distinguished primarily by numeric ranges.", ["Earthquakes are grouped as minor below magnitude 4, moderate from 4 to 6, and major above 6.", "physics", "textbook"]),
  ambiguous("hierarchy", 2, ["hierarchy", "concept_map"], "Nested concepts and cross-links both matter.", ["Memory includes sensory, working, and long-term systems, and attention connects sensory input with working memory.", "psychology", "paragraph"]),
  ambiguous("quantitative", 1, ["quantitative", "causal"], "Quantities express a causal economic response.", ["A 1% rise in interest rates leads to a 3% fall in investment in this model.", "economics", "paragraph"]),
  ambiguous("quantitative", 2, ["quantitative", "process"], "Measurements are embedded in an experimental sequence.", ["First heat the sample to 80 °C, then cool it to 20 °C over 5 minutes.", "physics", "lecture_note"]),
  ambiguous("plain_text", 1, ["plain_text", "hierarchy"], "A definition names several anatomical parts without explaining a taxonomy.", ["A neuron has a soma, dendrites, and an axon.", "biology", "definition"]),
  ambiguous("plain_text", 2, ["plain_text", "quantitative"], "A date is factual context rather than a numeric relationship.", ["The constitution took effect in 1789.", "history", "highlight"])
]

export const ROUTER_DATASET: RouterExample[] = [...nonAmbiguousExamples, ...ambiguousExamples]

export type DatasetPartition = "development" | "holdout"
export const DATASET_SPLIT_SEED = "lucent-router-evaluation-v1"

const stableHash = (value: string) => {
  let hash = 2166136261
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index)
    hash = Math.imul(hash, 16777619)
  }
  return hash >>> 0
}

export function splitRouterDataset(examples = ROUTER_DATASET): Record<DatasetPartition, RouterExample[]> {
  const groups = new Map<string, RouterExample[]>()
  for (const example of examples) {
    const key = `${example.ambiguous ? "ambiguous" : "strict"}:${example.expected}`
    groups.set(key, [...(groups.get(key) ?? []), example])
  }

  const development: RouterExample[] = []
  const holdout: RouterExample[] = []
  for (const group of groups.values()) {
    const ordered = [...group].sort((left, right) => {
      const difference = stableHash(`${DATASET_SPLIT_SEED}:${left.id}`) - stableHash(`${DATASET_SPLIT_SEED}:${right.id}`)
      return difference || left.id.localeCompare(right.id)
    })
    const holdoutCount = Math.max(1, Math.round(ordered.length * 0.25))
    holdout.push(...ordered.slice(0, holdoutCount))
    development.push(...ordered.slice(holdoutCount))
  }

  return {
    development: development.sort((a, b) => a.id.localeCompare(b.id)),
    holdout: holdout.sort((a, b) => a.id.localeCompare(b.id))
  }
}
