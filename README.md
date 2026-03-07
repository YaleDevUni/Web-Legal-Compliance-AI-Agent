# Web Legal Compliance AI Agent

This project is an AI-powered agent designed to analyze web pages or source code for compliance with various Korean legal regulations. It utilizes a multi-agent RAG (Retrieval-Augmented Generation) architecture to provide detailed compliance reports.

## Key Features & Recent Improvements

The agent's pipeline has been recently updated with several key improvements to enhance accuracy and efficiency.

### 1. Dynamic Agent Orchestration

To avoid unnecessary checks and improve performance, the system now incorporates a purpose-identification step.

- **Purpose Identification:** The `Orchestrator` first uses an LLM to analyze the target code and determine the website's primary purpose (e.g., "E-commerce", "Blog", "Medical Institution").
- **Selective Execution:** Based on the identified purpose, the `Orchestrator` dynamically selects and runs only the relevant compliance agents. For example, the `ServiceAgent` (which handles e-commerce laws) is only executed if the website is identified as a commercial platform.

### 2. Flexible RAG Prompting

The core RAG prompt has been made more flexible to handle situations where retrieved legal documents have low relevance.

- Instead of being forced to make a judgment based on poor context, the LLM is now instructed to respond with `compliant` and an `UNKNOWN` article ID if the provided documents are not applicable. This reduces false positives and improves the reliability of the analysis.

### 3. Enhanced Logging

Detailed logging has been integrated into the agent pipeline to provide clear visibility into the system's internal operations.

- The logs now show the exact query used by each agent, the `top_k` documents retrieved from the vector store (before and after filtering), and the final compliance status.
- The full LLM prompt sent for analysis is now logged (previously it was truncated for brevity), making debugging and prompt engineering easier.

### 4. Multi-Violation Reporting

The system can now identify and report multiple legal violations within a single code snippet.

- Previously, only one violation could be reported per analysis, even if the code contained several distinct legal breaches (e.g., general personal information collection, sensitive information collection, and unique identification number handling).
- The LLM prompt and parsing logic have been updated to allow the AI to report all applicable violations, each as a separate compliance report, providing a more comprehensive and accurate analysis.

### 5. Contextual Chunk Aggregation

To prevent loss of relevant context, the system now aggregates multiple text chunks retrieved from the same legal article.

- Previously, if the retriever found several relevant chunks from the same article, only the first one was used, and the rest were discarded.
- The context-building logic has been updated to group all chunks by their article ID and concatenate their text, ensuring all retrieved information is passed to the LLM for a more thorough analysis.

### 6. Semantic Chunking for Legal Texts

A significant improvement has been made to how legal documents are processed and indexed.

- **Problem:** The previous generic character-based chunking strategy often split legal articles in ways that separated important contextual information (e.g., article titles from their content), leading to retrieval failures.
- **Solution:** The system now employs a semantic chunking approach:
    - The HTML parser (`src/collector/parser.py`) was modified to preserve the natural paragraph breaks in the legal text.
    - The chunking logic (`src/embedder/chunker.py`) now splits articles based on these semantic units (paragraphs/sections).
    - Crucially, the full article title (e.g., "개인정보 보호법 제23조(민감정보의 처리 제한)") is **prepended to every chunk** derived from that article. This ensures that even small chunks carry their essential legal context, drastically improving retrieval accuracy.
- **Impact:** This change is expected to significantly enhance the retriever's ability to find highly relevant legal articles, such as `PA_23` for sensitive information, thereby improving the overall quality and accuracy of the compliance analysis.
