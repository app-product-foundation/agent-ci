## Focus: correctness and design

Look for correctness bugs first: wrong results, broken edge cases, error handling that loses or
hides failures, races, data loss, and behaviour that contradicts the pull request's own
description or its Issue.

Then look for design problems that the change introduces or makes worse:

- Anemic domain models: business rules that belong to a domain object but live in services,
  handlers or UI code, and domain state that can be put into an invalid combination from outside.
- Layering: dependencies that point the wrong way between the layers the product rules describe
  (for example domain code importing infrastructure, or UI reaching past its application layer).
- DRY: logic, constants or validation duplicated where one change would now have to be made in
  several places.
- Atomic Design or other component layers, when the product rules define them: components placed
  in the wrong layer, or lower layers depending on higher ones.

Report a design problem only when you can point at the concrete cost it causes, such as two copies
that will drift or a rule that can be bypassed.
