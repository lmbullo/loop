import sys, collections
def main(p):
    c = collections.Counter()
    for line in open(p):
        parts = line.split()
        if parts[1] == "ERROR":
            c[parts[2]] += 1
    for k, v in c.items():
        print(v, k)
main(sys.argv[1])
