# Application UI

Applies to the study workspace, public app landing page, and documentation portals.
MkDocs has its own theme and token definitions in `docs_theme/`, while sharing the
app’s typography and restrained palette. Learner and engineering documentation
remain separate portals with independent navigation and search.

The app is a study workbench: choose a topic, practise, read feedback, and revisit
missed concepts. Keep that task ahead of promotional copy or decoration.

- Use the palette in `frontend/src/styles/theme.css`: white content, warm neutral
  panels, charcoal text, and ink blue for selection and the primary action.
  Routes share one palette. Status colours convey actual state.
- Use locally hosted Source Sans 3 for body text and controls, Manrope for headings.
  Use the shared type scale. Avoid slogans, uppercase eyebrows, and decorative labels.
- Every dropdown uses `Select`. Preserve keyboard operation, visible focus,
  Escape dismissal, touch targets, and selected-option feedback. Avoid native selects.
- Keep secondary details out of the toolbar layout. Model information uses a labelled
  dialog with native focus containment, Escape dismissal, and focus restoration.
- Start from existing controls and states. Do not invent testimonials, usage counts,
  screenshots, or progress percentages. The landing image is captured from the real app.
- Show a clear recovery action on failure and keep the learner’s inputs. Do not show
  raw model responses or exception dumps in an error message.
- Check 320px phones as well as desktop. Menus must fit; labels and primary actions
  must remain readable. Honour reduced motion and avoid decorative route transitions.
- Documentation keeps the existing science study card as its visual identity.
  Preserve the equation, note, and orbit composition; keep labels readable and avoid
  adding repeated promotional cards or calls to action around it.

These decisions follow the [Hallmark](https://www.usehallmark.com/) principles of
restrained colour, task-led app screens, real product evidence, and deliberate controls.
