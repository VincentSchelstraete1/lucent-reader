# PDF ingestion manual evaluation

Use one copy of this worksheet for each PDF. Preserve the raw output when reporting an issue; do not normalize it first.

## File

- Test category: simple / educational / messy
- Filename:
- Approximate pages and file size:
- Source/application that produced the PDF:
- Scanned images or selectable text:

## Result

- Upload accepted: yes / no
- Extraction completed: yes / no
- Error shown, if any:
- Extracted character count:
- Physical page count matches PDF: yes / no
- Extracted image count:

## Output inspection

| Area | Good / partial / poor | Notes and exact examples |
|---|---|---|
| Heading preservation | | |
| Paragraph ordering | | |
| Lists and indentation | | |
| Equations and symbols | | |
| Tables and cell ordering | | |
| Figures and captions | | |
| Repeated headers/footers | | |
| Page boundaries | | |
| Multi-column ordering | | |
| Missing content | | |
| Duplicated content | | |
| Strange Markdown artifacts | | |
| Physical page association | | |
| Raw block order and bounding boxes | | |
| Extracted figures/images | | |
| Image-to-page association | | |
| Conservative caption association | | |

Compare each physical page's raw text and block list against the global
MarkItDown output. Record observed differences without correcting either form.

## Summary

- Most serious extraction problem:
- Output that normalization could safely address later:
- Information apparently lost during extraction:
- Would this raw output be usable for the next pipeline stage? yes / no / uncertain
