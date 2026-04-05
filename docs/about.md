---
description: About Dwight Gunning, the creator and maintainer of EdgarTools
---

# About the Creator

Dwight Gunning is a software engineer based in Ontario, Canada. He builds EdgarTools and works at the intersection of financial data, Python, and AI. Before open source, he spent 20 years building systems for banks, pension funds, and financial regulators.

## The Project

EdgarTools exists because SEC EDGAR data is public but not easy to use. The raw APIs, inconsistent filing formats, and deeply nested XBRL structures make programmatic access harder than it should be. EdgarTools wraps all of that behind a clean Python API -- three lines of code instead of a hundred.

The library has been in active development since December 2022 and is used by financial analysts, researchers, and developers working with SEC data.

## Technical Background

### Financial Systems

Most of the design decisions in EdgarTools come from direct experience building systems inside financial institutions. Over a decade of work across Canadian capital markets shaped a practical understanding of how financial data gets produced, consumed, and misused:

- **CIBC** (2004--2010) -- Advisory applications for the Investors Edge self-directed investment platform and retail banking systems. Six years working with the kind of investor-facing data that SEC filings represent.
- **Citibank Canada** (2010--2012) -- Led a team of six engineers on derivatives valuation and trade reconciliation platforms for front office trading. Real-time accuracy requirements.
- **Bank of Montreal** (2012) -- Performance testing for the InvestorLine AdviceDirect online investment advisory platform.
- **CPP Investments** (2015--2016) -- Data engineering for quantitative trading operations at one of Canada's largest institutional investors. Batch processing of trade data, database migrations, test-driven development with full coverage standards.
- **TD Securities** (2016--2017) -- Data pipeline architecture for the Market Risk Insight platform. ETL programs loading trade and risk data into SQL Server data warehouses.

This is why EdgarTools handles XBRL financial statements, 13F institutional holdings, insider transactions, and fund portfolios the way it does. The data models reflect how practitioners actually think about this data, not how the SEC happens to serialize it.

### AI and Machine Learning

At FINRA (Financial Industry Regulatory Authority, 2017--2025), the work shifted to AI research and development applied to financial regulation:

- Led R&D in GenAI and emerging technologies on AWS infrastructure (Bedrock, EKS), including hallucination detection, multi-agent orchestration, and RAG/Graph RAG architectures with vector search (ChromaDB, FAISS) and graph analysis (NetworkX, Neo4J).
- Won the 2025 FINRA Createathon with **MARTIE** (Multi-Agent Regulatory Temporal Interactive Engine) -- an agentic AI system using the Agno multi-agent framework and NetworkX to autonomously construct regulatory timelines from heterogeneous data sources.
- Won the 2023 FINRA Createathon with **Reg Copilot** -- a RAG-based chatbot using LlamaIndex and ChromaDB to deliver accurate, attributable responses from regulatory documents.
- Evaluated and deployed production GenAI frameworks (CrewAI, PydanticAI, LangChain, LlamaIndex, Google ADK, Agno) for agentic AI applications.
- Administered FINRA's Python Community of Practice and GenAI Community of Practice, driving adoption and best practices across the organization.

This background is directly behind EdgarTools' MCP server integration, AI-ready text extraction, and the skills framework that helps LLMs work effectively with SEC data.

### Infrastructure and Performance

- **IBM Canada** (2012--2015) -- Worked on the SmartCloud Enterprise cloud platform, building distributed infrastructure services during a critical period of enterprise cloud adoption.
- EdgarTools uses lxml, PyArrow, and intelligent caching to handle 30+ years of SEC filing data (back to 1994) with reasonable performance. The architecture choices -- lazy loading, efficient XML parsing, local storage options, S3-compatible cloud storage -- come from years of building data-intensive systems.

### Economics Foundation

Before engineering, there was economics. A BSc in Economics and an MSc in Management Information Systems from the University of the West Indies, followed by six years as an Economist at the Planning Institute of Jamaica building GDP and inflation forecasting models in Fortran and Excel VBA. The quantitative thinking and comfort with financial data started there.

One early career highlight: at Fiscal Services Limited in Jamaica (2001--2003), led development of one of the world's first production applications using the Spring Framework and Hibernate ORM -- both released just months earlier. That willingness to adopt emerging technology early has been a consistent thread.

## Career Timeline

| Period | Role | Organization |
|--------|------|-------------|
| 2022--Present | Creator & Maintainer | EdgarTools (Open Source) |
| 2017--2025 | AI R&D Engineer | FINRA |
| 2016--2017 | Senior Java Developer | TD Securities |
| 2015--2016 | Senior Java Developer | CPP Investments |
| 2012--2015 | Senior Cloud Engineer | IBM Canada |
| 2012 | Senior Technical Specialist | Bank of Montreal |
| 2010--2012 | Java Team Lead | Citibank Canada |
| 2004--2010 | Senior Developer | CIBC |
| 2001--2003 | Java Team Lead | Fiscal Services Ltd (Jamaica) |
| 1995--2001 | Economist | Planning Institute of Jamaica |

## Education

**Master of Science in Management Information Systems**
University of the West Indies, 2000--2001

**Bachelor of Science in Economics**
University of the West Indies, 1992--1995

## Recognition

- FINRA Createathon Winner, 2025 -- MARTIE (Multi-Agent Regulatory Temporal Interactive Engine)
- FINRA Createathon Winner, 2023 -- Reg Copilot
- Administrator, FINRA Python Community of Practice
- Administrator, FINRA GenAI Community of Practice

## Connect

- **GitHub**: [github.com/dgunning](https://github.com/dgunning)
- **LinkedIn**: [linkedin.com/in/dwight-gunning](https://www.linkedin.com/in/dwight-gunning/)
- **Email**: [dgunning@gmail.com](mailto:dgunning@gmail.com)

If you find EdgarTools useful, consider supporting its development:

<a href="https://www.buymeacoffee.com/edgartools" target="_blank">
  <img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 40px !important;width: 144px !important;" >
</a>
