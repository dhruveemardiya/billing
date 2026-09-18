from pypdf import PdfReader
from pypdf.generic import ContentStream

reader = PdfReader('f:/BILLING/project/demo.pdf')
p0 = reader.pages[0]
contents = p0.get_contents()
if contents:
    stream = ContentStream(contents, reader)
    print("Total ops on page 0:", len(stream.operations))
    # Check ops that draw paths in the donut area
    donut_ops = []
    for i, (operands, op) in enumerate(stream.operations):
        op_str = op.decode() if isinstance(op, bytes) else op
        nums = [float(x) for x in operands if isinstance(x, (int, float))]
        # Check if coordinates fall within donut region (x around 370-520, y around 350-480)
        # Note in PDF coordinates, page_height is 842, so y is 842 - top
        # top 380 to 520 means y is 842 - 520 = 322 to 842 - 380 = 462
        if any(350 <= n <= 530 for n in nums):
            donut_ops.append((i, op_str, operands))
    print(f"Ops with coords 350-530: {len(donut_ops)}")
    # Print sample of donut ops
    for op in donut_ops[:30]:
        print(op)
    # Check if there are images or XObjects
    if "/Resources" in p0 and "/XObject" in p0["/Resources"]:
        print("XObjects on page 0:", list(p0["/Resources"]["/XObject"].keys()))
