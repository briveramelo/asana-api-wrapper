- python 3.13
- Don't use `__future__` imports or other natural language upgrades like `List` or `Dict` typing imports

- Follow Clean Architecture and SOLID programming practice
- variable names should all be clear, not abbreviated
- Clarity in naming is of utmost importance
- Follow single responsibility principle for files
- If a file has multiple responsibilities, suggest a task to split the extra contents into another existing file where it belongs or into a new file
- all function names should be verb phrases
- all variables should be nouns
- if you propose using a new library, state this suggestion upfront along with the `poetry add package-name` command for reference
- use `poetry install --no-root`

- don't run tests as web connectivity is disabled for you
- if you see repeat patterns or repeat code, consolidate into a helper function
