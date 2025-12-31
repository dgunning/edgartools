from edgar import Company, set_identity

from quant.markdown import extract_markdown


def main() -> None:
    set_identity("Quant LLM test user@example.com")

    company = Company("MSFT")
    filings = company.get_filings(form="10-K")
    filing = filings.latest()
    if filing is None:
        raise RuntimeError("No SNAP 10-K filings found.")

    markdown = extract_markdown(
        filing,
        item=["Item 1", "Item 7"],
        statement=["IncomeStatement", "BalanceSheet"],
        notes=True,
        show_dimension=False,
        show_filtered_data=True,
    )

    output_path = "quant/test/snap_llm_markdown.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(markdown)

    print(f"Wrote LLM markdown to {output_path}")


if __name__ == "__main__":
    main()
