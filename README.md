# extent-ai-eval


## Running the project

Note: only tested on Ubuntu 24.04.2 LTS

### Install uv, if your system does not have it

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Clone the repository

```bash
git clone https://github.com/elihoole/extent-ai-eval && cd extent-ai-eval
```

### Setup the project

```bash
uv sync
```

### Run main.py, with correct PDF path

```bash
uv run main.py --file_path "financial_statement (1).pdf" --company_name_page_index 0 --financial_highlights_page_index 4
```

## Thinking process behind design choices

### Getting 'Company Name' and 'Financial Highlights' page numbers

Aside from the Ceylon Investments PLC annual report, I checked the annual reports for two other public limited companies: LOLC Finance and Dialog Axiata.

In all three reports, the following hold true:

1. There is a single 'Financial Highlights' page listing key performance metrics for the present report year and the previous year.

2. The first page (index 0) contains the company name.

So, the `run_pdf_extraction()` function is designed to take the following arguments:
- `company_name_page_index`
- `financial_highlights_page_index`

Values are passed at run time with defaults set to the provided PDF.

To test, Dialog Axiata PLC's annual report run:

```bash
uv run main.py --file_path "dialog-axiata-plc-annual-report-2024.pdf" --company_name_page_index 0 --financial_highlights_page_index 11
```

### Extraction process

Financail Highlights:
- I directly upload the financial highlights page image and directly extract the information. There is no intermediate text extraction step.

Company name:
- I use PyPDF2 to directly extract the company name from the first page. There is no LLM call for this.

Reasoning:

1. Tables encode textual and geometic information. When we extract tables using PyPDF2 etc. as text, we destroy geometric information. In my experience, directly extracting from table images using multimodal LLMs, almost without exception, yields better outputs. Also, PyPDF2 etc will fail with scanned PDFs.

2. Company name extraction from the first page is pretty straight forward, so makes sense to simply extract directly (scanned PDF issue exists, however). I did not implement regex clean up considering time.

### Output JSON:

```bash
{
    "report_year": 2024,
    "metrics": [
        {
            "metric": "Revenue",
            "change_percent": -5.8,
            "value_2024": 171170,
            "value_2023": 181722
        },
        // other metrics
    ],
    "metadata": {
        "currency": "Sri Lankan Rupees",
        "year_end_date": "December 31, 2024",
        "token_usage": {
            "input_tokens": 666,
            "output_tokens": 2008,
            "total_tokens": 6078
        },
        "company_name": "Dialog Axiata PLC  \nAnnual Report 2024"
    }
}
```

I committed a version that perfectly extracted the provided document: [(commit hash)](https://github.com/elihoole/extent-ai-eval/commit/47939a5f3367d4aa94b6933fa388b1a805875e2d)

I then ran the same code with Dialog Axiata PLC report and identified certain shortcomings:

1. value_2025 and value_2025 were hard coded in the schema.
2. Dialog's report did not include percentage change in the table.

I modified the prompt + validation schema and fixed (1) such that keys change dynamically based on the report. But although I updated the prompt to extract change_percentage as -0.0000 for tables without percentage change column, LLM is still hallucinating that information; so (2) is not fixed yet.

Possible fix:

- build a validation routine that uses value_year vals to calculate the percentage change and compare with extracted change_percent

### Scaling

Primary bottleneck:

-- present implementation requires foreknowlege of the 'Financial Highlights' page.

The dumb thing to do here, that should NEVER be done is:

-- sending every page to LLM and ask it to extract iff financial highlights and 'NA' if NOT.

Challenge is to identify the 'Financial Highlights' page from N pages.

Two reasonable paths:
1. Build a page classifier using regex
2. Identify Table of Contents, extract 'Financial Highlights' page and map to PDF page index

If both fail, I will try:
3. Build a binary text classifier that can do batch inferencing (100 pages at once)


To process 1000 docs:

Currently - it will take about 2.5 hours.
