# Reading UI — comprehension and wayfinding

Adapted from Impeccable's Read mode (Apache-2.0), pinned in `../SOURCES.md`.
Self-contained: no comp generator, launcher or surface-brief files are required.

## Reader's question first

Identify whether the page is reference documentation, a guide, an article, a log
or a changelog. Its reading order follows that purpose. Keep familiar navigation,
current location, meaningful headings and a clear route back/forward. A document
should read as a document, not a marketing poster or an ornamental control panel.

## Frame versus reading column

Let the approved visual identity inform the navigation, title, margins, callouts,
code and table treatment. Keep the body calm with real contrast and comfortable
line measure. About 60–75 Latin characters is a prose starting point, not a fixed
Chinese character count. Test the actual locale and script. Monospace belongs to
code and identifiers, not every heading or body paragraph.

Metadata (path, version, author, update time, read-only state) orients without
competing with the document title. Avoid repeating the same title in multiple
chrome layers. Render stored text safely with existing semantics; a style change
must not make markup executable or change document meaning.

## Hard content and narrow layouts

Use the real longest paths, code, table, note or diagram to judge the layout, not
only a short paragraph. Allow long tokens to wrap where appropriate, preserve code
meaning and let essential wide code/tables scroll within their region when needed.
Keep the page itself reflowable. Do not clip essential text to make a screenshot neat.

A directory can remain visible on wide layouts and collapse explicitly on narrow
ones, provided the reader can reopen it and current selection remains clear.
Sticky navigation must not obscure focused content or headings. Long directories
must remain operable; do not trap the reader in nested scroll regions by default.

## Evidence

Confirm the reader can find a document, recognize location, read the hardest content
and return to navigation with keyboard and pointer. Inspect empty tree, missing
document and read failure/retry states. Check narrow layout and enlarged text;
verify safe text rendering is retained. The first viewport should answer or frame
the reader's question rather than spend its height on decorative panels.
