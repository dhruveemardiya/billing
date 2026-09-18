import os, glob, tempfile

d = os.path.join(tempfile.gettempdir(), "electricity_bill_generator", "output")
matches = []
for root, dirs, files in os.walk(d):
    for f in files:
        if "7432005324" in f:
            matches.append(os.path.join(root, f))

print(f"Found {len(matches)} matches:")
for m in sorted(matches):
    print(" ", m)
