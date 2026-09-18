from pypdf import PdfReader
from pypdf.generic import ContentStream

reader = PdfReader('f:/BILLING/project/demo.pdf')
p0 = reader.pages[0]
contents = p0.get_contents()
stream = ContentStream(contents, reader)
for i in range(705, 795):
    operands, op = stream.operations[i]
    op_str = op.decode() if isinstance(op, bytes) else op
    print(f"{i}: {op_str} {operands}")
