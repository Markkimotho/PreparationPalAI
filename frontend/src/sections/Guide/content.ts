// Compact product help. Long-form learner docs and engineering references live
// in separate MkDocs portals; implementation detail does not belong in this view.
export const USER_GUIDE_URL = 'https://markkimotho.github.io/PreparationPalAI/';
export const CONTRIBUTOR_GUIDE_URL = `${USER_GUIDE_URL}contribute/`;

export interface GuideSection {
  id: string;
  title: string;
  group: 'Getting started' | 'Core features' | 'Help';
  body: string;
}

export const GUIDE: GuideSection[] = [
  {
    id: 'overview', title: 'Overview', group: 'Getting started',
    body: `# PreparationPalAI

Turn a topic or your notes into deliberate practice for exams, interviews, and
everyday learning. Start small: one topic, a handful of questions, and one idea
you want to understand better.

The full [user guide](${USER_GUIDE_URL}) has walkthroughs and study playbooks.
This in-app guide is a quick reference for the controls you use while studying.`,
  },
  {
    id: 'first-session', title: 'Your first session', group: 'Getting started',
    body: `## Your first session

1. Open **Preparation Coach** and choose **Learn & recap**.
2. Enter a narrow topic, such as Newton’s second law and units.
3. Choose a short session and a suitable difficulty, then select **Start preparation**.
4. Answer before reading the reference, and record your confidence honestly.
5. Review the results and pick one concept to revisit.

You can start without documents; the coach labels that as general model knowledge.
For course-specific practice, add relevant notes first.

[Read the full walkthrough](${USER_GUIDE_URL}start/first-session/).`,
  },
  {
    id: 'coach', title: 'Preparation Coach', group: 'Core features',
    body: `## Preparation Coach

- **Learn & recap:** build understanding and respond to targeted practice after mistakes.
- **Exam practice:** try a mixed assessment with an optional timer.
- **Technical interview:** explain your reasoning and respond to a follow-up.
- **Weak-area review:** revisit topics that scored poorly in saved sessions.

Written feedback can separate reasoning, accuracy, and clarity. Compare uncertain
feedback with your notes. Saved sessions and results appear under **Your recent sessions**.

An exam timer continues when you leave the page. Unanswered questions count as zero.
Changing the model picker does not change the model used by an existing coach session.

[Coach guide](${USER_GUIDE_URL}features/coach/).`,
  },
  {
    id: 'knowledge-base', title: 'Knowledge base', group: 'Core features',
    body: `## Knowledge base

Open **Knowledge base** in the top bar to upload PDFs or images, index a web topic,
and check the sources available to study from. Wait for indexing to complete.

**Recent ingestion jobs** shows saved upload/search work. You can retry a failed
job when your role permits it. By default, uploads accept up to three files of
20 MiB each. Clear scans and readable text produce more useful material.

Clearing the knowledge base removes workspace material, not just this conversation.
In a shared workspace, other authorised people may use the same material.

[Material guide](${USER_GUIDE_URL}features/material/).`,
  },
  {
    id: 'quiz-prep', title: 'Quiz Prep', group: 'Core features',
    body: `## Quiz Prep

Generate a quiz from indexed material. Choose a topic, question type, difficulty,
and exam type, then answer one question at a time. Review feedback before moving on.

Use **Retake same quiz** to check understanding of the feedback, or **New quiz**
for another set. Current Quiz Prep state can be lost when you leave or refresh;
use Preparation Coach when you want saved assessment sessions.

[Quiz guide](${USER_GUIDE_URL}features/quizzes/).`,
  },
  {
    id: 'study-agent', title: 'Study Agent', group: 'Core features',
    body: `## Study Agent

Ask the tutor to explain a concept, quiz you, check an answer, or search for study
material. State the subject, level, and kind of help you want.

Try: “Ask me one thermodynamics question at a time and challenge my assumptions.”

The agent needs a model that supports its tools. A model that chats well may not
handle agent actions well. Use **New session** when changing topics. Chats are
not saved coach assessments, and web searches contact external services.

[Tutor guide](${USER_GUIDE_URL}features/tutor/).`,
  },
  {
    id: 'regular-chat', title: 'Regular Chat', group: 'Core features',
    body: `## Regular Chat

Ask focused questions about indexed material. Read the source labels and page
references, then compare important claims with the passage itself. A citation
makes an answer checkable; it does not guarantee correctness.

You can leave the default conversation mode selected. Moving away, refreshing,
or changing modes can change the available chat context.

[Document chat guide](${USER_GUIDE_URL}features/chat/).`,
  },
  {
    id: 'flashcards', title: 'Flashcards', group: 'Core features',
    body: `## Flashcards

Create a deck manually or generate one from indexed material. Keep each card focused
on one idea. Try to answer before flipping, then choose **Again** or **Got it**.

**Space** flips a card; **←** marks Again; **→ / Enter** advances. Native controls
keep their usual keyboard action when focused. The score is your self-assessment
for that run. Review generated cards for accuracy and set your own review schedule.

Deleting a card or deck has no in-app undo.

[Flashcard guide](${USER_GUIDE_URL}features/flashcards/).`,
  },
  {
    id: 'programming', title: 'Programming Assistant', group: 'Core features',
    body: `## Programming Assistant

Ask about code, debugging, algorithms, or implementation trade-offs. Include the
language, expected behaviour, and relevant error. Do not paste credentials.

Enable **Use my documents** to bring indexed notes into the discussion. The assistant
proposes and explains code; it does not run it. Test suggestions in your own environment.

[Programming guide](${USER_GUIDE_URL}features/code/).`,
  },
  {
    id: 'models', title: 'Models and availability', group: 'Help',
    body: `## Models and availability

Start with an installed model. **Model info** explains known or unverified capabilities.
Use **Pull** to download an available model when permitted; shared installations
require an administrator for downloads. Wait for it to be ready before studying.

GLM and DeepSeek are configurable catalogue choices. Availability and resource needs
depend on the exact model tag. Each study section remembers its own selection.

If a response is slow, try fewer questions or a smaller installed model. If Ollama
is offline, restore the connection or contact the workspace administrator.

[Model guide](${USER_GUIDE_URL}features/models/).`,
  },
  {
    id: 'help', title: 'Help and privacy', group: 'Help',
    body: `## Help and privacy

Protected workspaces use an access key that stays in the current tab’s memory.
Refreshing signs you out. People authorised for the same workspace can share material;
your browser’s learner profile is not a private account inside that workspace.

Model answers and scores can be wrong. Check important claims, assumptions, units,
and source passages before relying on them. This is practice feedback, not an
official marking scheme or a guarantee of exam or interview outcomes.

[Troubleshooting](${USER_GUIDE_URL}help/troubleshooting/) ·
[Privacy and workspaces](${USER_GUIDE_URL}help/privacy/)

Want to improve or host the project? The separate
[contributor handbook](${CONTRIBUTOR_GUIDE_URL}) covers development and operations.`,
  },
];
