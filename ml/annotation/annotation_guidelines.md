# UI element annotation guidelines

- Draw tight, consistent boxes around the visible control, not its surrounding container.
- Label text separately from its input; do not include the label in an input box.
- Include placeholder text inside the control box. Annotate disabled but visible controls normally.
- Do not annotate hidden, clipped, or fully occluded controls. For overlaps, annotate each independently visible control.
- Use the smallest semantic class: `password_input` instead of `text_input`, `search_box` instead of a generic input.
- Annotate desktop, mobile, light/dark themes, wireframes, and real screenshots across varied resolutions and styles.
- Split related screens by application into one dataset split to prevent leakage.
- Review label consistency and invalid/zero-area boxes before training.
