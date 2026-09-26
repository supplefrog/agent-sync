# Help-page authoring

1. Understand the reader's task and inspect the current product source or supplied evidence for uncertain behavior.
2. Start with the result. Put prerequisites before steps, commands within the step that uses them, and any data-loss warning immediately before the risky action.
3. Use numbered steps for a sequence. Include the expected result and troubleshooting that helps a reader recover from a likely problem. Do not invent empty headings to fill the template.
4. Preserve literal UI labels and command names. Follow sentence case for ordinary English headings; preserve documented translation-glossary exceptions.
5. Check the changed behavior and a relevant nearby case. From the project root run `python scripts/check_docs.py` for local document-link checks. Report its actual result and any remaining product uncertainty.
