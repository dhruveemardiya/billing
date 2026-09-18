from pypdf import PdfReader
from pypdf.generic import ContentStream

reader = PdfReader('f:/BILLING/project/demo.pdf')
p0 = reader.pages[0]
contents = p0.get_contents()
stream = ContentStream(contents, reader)
print("Total ops on page 0:", len(stream.operations))
# find ops near 440, 448 (in pdf coords y is 842 - 448 = 394)
ops_around_donut = []
for i, (operands, op) in enumerate(stream.operations):
    op_str = op.decode() if isinstance(op, bytes) else op
    nums = [float(x) for x in operands if isinstance(x, (int, float))]
    # x around 380-500, y around 340-450
    if any(380 <= n <= 500 for n in nums) and any(330 <= n <= 450 for n in nums):
        ops_around_donut.append((i, op_str, operands))

print(f"Total ops around donut: {len(ops_around_donut)}")
print("Sample ops:")
for op in ops_around_donut[:25]:
    print(op)
print("Last 15 ops:")
for op in ops_around_donut[-15:]:
    print(op)
