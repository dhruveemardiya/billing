import pdfplumber

with pdfplumber.open("demo.pdf") as pdf:
    page = pdf.pages[1]
    for word in page.extract_words():
        if word["text"] in ("IMPORTANT", "Amount", "recovered", "13.06.2024."):
            print(word["text"], "x0=", round(word["x0"],1), "x1=", round(word["x1"],1),
                  "top=", round(word["top"],1), "bottom=", round(word["bottom"],1))