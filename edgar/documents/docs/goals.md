# Goals

- We want to read the text, tables and ixbrl data from SEC filings in a way that preserves the greatest semantic meaning of the content. 
- This should work for the human channel - Read the HTML and render for a human to read - and for the AI channel - parse the HTML and produce text and data that an LLM can reason over.
- This should work at the full document level, and at the section level - breaking the document into sections that can be processed independently.
- For some filing types (10-K, 10-Q, 8-K) we want to identify the sections by their standard names.
- For others we want to capture sections semantically - headings, paragraphs, lists, tables, etc.
- We don't need necessarily to capture data for dataframes. Getting tables in the right structure for rendering to text so that they can be used in AI context is more important
- I would say AI context is the primary goal, with human context being secondary.
- To make context efficient being able to break the document into sections or tables that can be processed independently is important. We don't need to provide this semantic divisibility in the library by should support down stream functions that can do so
- We want to be able to search the document for text, regex, and semantically.
- We want to be able to render the document to text, markdown, and rich console output
- The HTML rewrite should be better than the old parser in every way - speed, accuracy, features, usability
- I - the maintainer - is the final judge of better. I need to see the result e.g. print the full document text and tables and I will say if it is better or not.



## HTML Parsing
- Read the entre HTML document without dropping semantically meaningful content
- Can drop non-meaningful content (scripts, styles, formatting)

## Table Parsing

- Tables that contain meaningful data are extracted
- Tables meant for layout are ignored unless they help with understanding the document or in rendering
- Accurate table rendering so that when the document is printed the tables look correct
- Tables can b