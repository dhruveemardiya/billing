from pypdf import PdfReader

reader = PdfReader('f:/BILLING/project/demo.pdf')
p0 = reader.pages[0]
contents = p0.get_contents()
print("Contents type:", type(contents))
if contents:
    data = contents.get_data()
    print("Content length:", len(data))
    # print first 500 characters
    print("Snippet:", data[:300])
